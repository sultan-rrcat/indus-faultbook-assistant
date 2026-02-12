import config
import logging
import os
import json
import pandas as pd
import numbers
from fastapi import FastAPI, Request, HTTPException, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from textwrap import dedent
import time
import psutil
import subprocess
from threading import Thread
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer, BitsAndBytesConfig
import asyncio
from typing import Optional, Dict, Any
import uuid
from sqlalchemy import create_engine, text
from datetime import datetime, timezone

from NL2SQL import NL2SQL
from intent_classifier import IntentClassifier
from rag_setup import RagSetup
import date_parser

from smart_zero_handler import SmartZeroResultsHandler
zero_handler = None

# --- Pydantic Models ---
class ChatMessage(BaseModel):
    message: str
    streaming_enabled: bool = True  # default true if not provided
    current_mode: str = 'automatic'

class FrontendLog(BaseModel):
    type: str
    error_message: Optional[str] = None
    stack: Optional[str] = None
    user_prompt: Optional[str] = None
    user_agent: Optional[str] = None
    message: Optional[str] = None
    source: Optional[str] = None
    lineno: Optional[int] = None
    colno: Optional[int] = None
    error_stack: Optional[str] = None
    reason: Optional[str] = None

# --- FastAPI App Initialization ---
app = FastAPI(
    title="Chatbot API",
    description="AI-powered chatbot with NL2SQL and RAG capabilities",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory=config.APP_STATIC_FOLDER), name="static")
templates = Jinja2Templates(directory=config.APP_TEMPLATE_FOLDER)

# --- Logging Setup ---
config.setup_logging()
logger = logging.getLogger(__name__)
logger.info("Logging has been successfully set up.")

# --- Global Variables for Models and Services ---
qwen_base_model = None
mistral_tokenizer = None
qwen_tokenizer = None
device = None
classifier_obj = None
rag_obj = None
nl2sql_obj = None

engine = create_engine(config.SQLALCHEMY_CHATBOT_CONNECTION_STRING)

# --- Session Management ---
sessions: Dict[str, Dict[str, Any]] = {}

def get_session(request: Request) -> str:
    session_id = request.headers.get("x-session-id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing session_id")
    return session_id


def ensure_message_alternation(messages):
    # Remove consecutive 'system' or 'user' roles
    cleaned_messages = []
    last_role = None
    for msg in messages:
        if msg["role"] == last_role and msg["role"] in ["system", "user"]:
            continue  # skip duplicate system/user
        cleaned_messages.append(msg)
        last_role = msg["role"]

    # Ensure the alternation pattern
    roles_sequence = [msg["role"] for msg in cleaned_messages if msg["role"] != "system"]
    if len(roles_sequence) > 0 and roles_sequence[0] != "user":
        raise ValueError("First message after system must be from 'user'.")
    for idx in range(1, len(roles_sequence)):
        if roles_sequence[idx] == roles_sequence[idx - 1]:
            raise ValueError(f"Invalid alternation in messages at position {idx}: {roles_sequence}")

    return cleaned_messages

def get_history_from_db(session_id, limit=10):
    if not session_id:
        return []
    query = text("""
                SELECT user_prompt, chatbot_response
                FROM messages
                WHERE session_id = :session_id
                ORDER BY turn_number DESC
                OFFSET 0 ROWS FETCH NEXT :limit ROWS ONLY
                 """)
    
    connection = engine.connect()
    try:
        results = connection.execute(query, {"session_id":session_id, "limit":limit}).fetchall()
        history = []

        for row in reversed(results):
            if row.user_prompt:
                history.append({"role":"user","content": row.user_prompt})
            if row.chatbot_response:
                history.append({"role":"user","content": row.chatbot_response}) #this must be user cannot be 'assistant'

        logger.info(f"Reconstructed history with {len(history)} messages for session_id: {session_id}")
        return history
    except Exception as e:
        logger.error(f"Could not retrieve history from DB for session {session_id}: {e}")
        return []
    finally:
        connection.close()

def clean_rewritten_query(query: str) -> str:
    return query.strip().strip('"').strip("'").replace('</s>', '').strip()

def rewrite_query_with_history(model, tokenizer, history, new_query):
    if not history:
        return new_query
    
    history_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history])
    
    system_prompt = config.QUERY_REWRITER_PROMPT
    user_content = f"**History:**\n{history_str}\n\n**New Question:** \"{new_query}\"\n\n**Your Output:**"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]
    
    try:
        device = next(model.parameters()).device
        
        # Use Qwen's chat template
        input_ids = tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_tensors="pt",
            enable_thinking=False
        ).to(device)
        
        outputs = model.generate(
            input_ids=input_ids,
            max_new_tokens=256,
            temperature=0.1,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
            cache_implementation="static"
        )
        
        rewritten_query = tokenizer.decode(outputs[0][input_ids.shape[1]:], skip_special_tokens=True).strip()
        rewritten_query = clean_rewritten_query(rewritten_query)
        logger.info(f"Original Query: '{new_query}' -> Rewritten Query: '{rewritten_query}'")
        return rewritten_query
    except Exception as e:
        logger.error(f"Error during query rewriting: {e}")
        return new_query  # Fallback to the original query on error

def store_chats_in_db(session_id, user_message, rewritten_user_message, intent_result, chatbot_response, sql_query_to_send, context, sources_data):
    logger.info("in the store chats in db function")
    connection = engine.connect()
    try:
        row = connection.execute(text("SELECT MAX(turn_number) from messages where session_id = :session_id"), {"session_id": session_id}).fetchone()
        current_turn_val = row[0] if row and row[0] is not None else 0
        next_turn = current_turn_val + 1
        connection.commit()
    except Exception as e:
        logger.error(f"Error fetching turn number from database: {e}")
    finally:
        connection.close()

    timestamp = datetime.now()

    classified_intent = intent_result.get("classified_intent")
    mistral_intent    = intent_result.get("mistral_intent")
    tinyllama_intent  = intent_result.get("tinyllama_intent")
    bert_intent       = intent_result.get("bert_intent")

    generated_sql = sql_query_to_send if sql_query_to_send else None
    rag_chunks = context if context else None
    sources_data_json = json.dumps(sources_data)

    
    insert_sql = text("""
    INSERT INTO messages (
        session_id,
        turn_number,
        timestamp,
        user_prompt,
        rewritten_user_prompt,
        classified_intent,
        mistral_intent,
        tinyllama_intent,
        bert_intent,
        chatbot_response,
        generated_sql,
        unique_sources,
        rag_chunks
    )
    OUTPUT INSERTED.message_id
    VALUES (
        :session_id,
        :turn_number,
        :timestamp,
        :user_prompt,
        :rewritten_user_prompt,
        :classified_intent,
        :mistral_intent,
        :tinyllama_intent,
        :bert_intent,
        :chatbot_response,
        :generated_sql,
        :unique_sources,
        :rag_chunks
    )
""")
    connection = engine.connect()
    try:
        result = connection.execute(insert_sql, {
            "session_id": session_id,
            "turn_number": next_turn,
            "timestamp": timestamp,
            "user_prompt": user_message,
            "rewritten_user_prompt": rewritten_user_message,
            "classified_intent": classified_intent,
            "mistral_intent": mistral_intent,
            "tinyllama_intent": tinyllama_intent,
            "bert_intent": bert_intent,
            "chatbot_response": chatbot_response,
            "generated_sql": generated_sql,
            "unique_sources": sources_data_json,
            "rag_chunks": rag_chunks
        })
        inserted_row = result.fetchone()
        connection.commit()
        message_id = None

        if inserted_row:
            message_id = str(inserted_row[0])
            logger.info(f"Inserted message_id: {message_id}")
        else:
            logger.message("No message_id returned after insert.")
            message_id=None
        return message_id
    except Exception as e:
        logger.info(f"Error executing query: {e}")
        return None
    finally:
        connection.close()

# --- Inference Logic ---
# --- Helper to get tensor input_ids robustly ---
def prepare_input_ids(tokenizer, messages, device):
    """
    Return (input_ids_tensor, prompt_length)
    Works if tokenizer.apply_chat_template returns a tensor or dict.
    """
    if not messages:
        raise ValueError("No messages provided to prepare_input_ids")

    inputs = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_tensors="pt",
        enable_thinking=False
    )

    # If it's a dict, extract input_ids and move to device
    if isinstance(inputs, dict):
        input_ids = inputs.get("input_ids")
        if input_ids is None:
            raise ValueError("apply_chat_template returned dict without 'input_ids'")
        input_ids = input_ids.to(device)
    else:
        # assume tensor-like
        input_ids = inputs.to(device)

    prompt_len = input_ids.shape[1]  # batch dim assumed 1
    return input_ids, prompt_len

# --- Stream (token-by-token) generator (adjusted to use explicit input_ids) ---
async def stream_inference_generator(messages):
    start_time = time.time()
    token_count = 0
    current_process = psutil.Process(os.getpid())

    # build input_ids robustly
    try:
        input_ids, prompt_len = prepare_input_ids(qwen_tokenizer, messages, device)
    except Exception as e:
        logger.error("Error preparing inputs for streaming", exc_info=True)
        yield f"data: {json.dumps({'error': 'Failed to prepare inputs for streaming'})}\n\n"
        return

    streamer = TextIteratorStreamer(qwen_tokenizer, skip_prompt=True, skip_special_tokens=True)

    try:
        generation_kwargs = dict(
            input_ids=input_ids,
            streamer=streamer,
            max_new_tokens=512,
            do_sample=True,
            temperature=0.9,
            top_p=0.95,
            pad_token_id=qwen_tokenizer.eos_token_id
        )

        # start generation in thread (non-blocking)
        thread = Thread(target=qwen_base_model.generate, kwargs=generation_kwargs)
        thread.start()

        for token in streamer:
            token_count += 1
            # token is string from TextIteratorStreamer
            yield f"data: {json.dumps({'chunk': token})}\n\n"
            await asyncio.sleep(0.001)

        thread.join()
        # stats...
        total_time = time.time() - start_time
        logger.info(f"Streaming done: tokens={token_count} time={total_time:.2f}s")

    except Exception:
        logger.exception("Error during Transformers streaming")
        yield f"data: {json.dumps({'error': 'Error generating response.'})}\n\n"

# --- Non-streaming generator: runs generate in thread using asyncio.to_thread ---

async def inference_generator(messages):
    """
    Async generator that yields a single 'chunk' with the full generated text.
    Runs the blocking model.generate in a thread to avoid blocking the event loop.
    """
    start_time = time.time()
    current_process = psutil.Process(os.getpid())

    try:
        input_ids, prompt_len = prepare_input_ids(qwen_tokenizer, messages, device)

        generation_kwargs = dict(
            input_ids=input_ids,
            max_new_tokens=512,
            do_sample=True,
            temperature=0.9,
            top_p=0.95,
            pad_token_id=qwen_tokenizer.eos_token_id
        )

        # Run blocking generate in a thread
        def blocking_generate():
            return qwen_base_model.generate(**generation_kwargs)

        output_ids = await asyncio.to_thread(blocking_generate)

        # decode only the new tokens after prompt
        generated_text = qwen_tokenizer.decode(
            output_ids[0][prompt_len:], skip_special_tokens=True
        ).strip()

        yield f"data: {json.dumps({'chunk': generated_text})}\n\n"

        total_time = time.time() - start_time
        logger.info(f"Non-stream generation done: {len(generated_text.split())} words in {total_time:.2f}s")

    except Exception:
        logger.exception("Error during non-streaming generation")
        yield f"data: {json.dumps({'error': 'Error generating response.'})}\n\n"

async def prepare_pipeline(user_message, rewritten_user_message, current_mode, conversation_history):
    """Shared pipeline logic for building messages, intent, context, sources, and SQL."""
    messages = []
    context = ""
    unique_sources = []
    system_prompt = ""
    sql_query_to_send = None
    intent_result = None

    # --- Intent Classification (NOW PARALLEL!) ---
    if current_mode == 'automatic' or current_mode == 'indus-faults':
        # Use the async version for parallel execution
        intent_result = await classifier_obj.classify_query_async(rewritten_user_message)
        logger.info(f"Mode:{current_mode}\nIntent Result:{intent_result}")
        
        if current_mode == 'indus-faults' and intent_result["classified_intent"] == config.CLASS_LABELS[3]:
            intent = config.CLASS_LABELS[1]  # Search on RAG
        else:
            intent = intent_result["classified_intent"]
    elif current_mode == 'general':
        intent = config.CLASS_LABELS[3]
    elif current_mode == 'rrcat-info':
        intent = config.CLASS_LABELS[2]
    else:
        logger.error("Invalid current_mode")
        raise HTTPException(status_code=400, detail="Invalid current_mode")

    # --- SQL / RAG / context handling ---
    if intent == config.CLASS_LABELS[0]:
        sql_text = nl2sql_obj.generate_query_using_llm(rewritten_user_message)
        if sql_text:
            clean_sql = nl2sql_obj.extract_sql(sql_text)
            validation_status, _ = nl2sql_obj.validate_sql_syntax(clean_sql)
            if validation_status:
                try:
                    df_result = nl2sql_obj.execute_query(clean_sql)
                    num_rows = len(df_result)
                    sql_query_to_send = clean_sql

                    def is_zero_count_result(df: pd.DataFrame) -> bool:
                        if len(df) == 1 and df.shape[1] == 1:
                            value = df.iloc[0, 0]
                            return isinstance(value, numbers.Number) and value == 0
                        return False

                    if num_rows == 0 or (num_rows == 1 and is_zero_count_result(df_result)):
                        # system_prompt = config.NO_MATCHING_RECORD_PROMPT
                        system_prompt = config.ZERO_OR_NO_MATCH_PROMPT
                        messages.append({"role": "system", "content": system_prompt})
                        messages.append({
                            "role": "user",
                            "content": f"Based on my user prompt, you found no results. Now, guide me to a solution.\n\nUser Prompt: {rewritten_user_message}"
                        })

                    # logger.info(f"num_rows: {num_rows}\nis_zero_count_result:{is_zero_count_result(df_result)}")

                    # if num_rows == 0 or (num_rows == 1 and is_zero_count_result(df_result)):
                    #     logger.info(f"hiii")
                    #     # Analyze why we got zero results
                    #     analysis = zero_handler.analyze_zero_results(
                    #         rewritten_user_message, 
                    #         clean_sql, 
                    #         df_result
                    #     )
                        
                    #     logger.info(f"Zero results analysis: {analysis}")
                        
                    #     # Use the appropriate prompt based on analysis
                    #     system_prompt = analysis['suggested_prompt']
                        
                    #     # Add diagnostic context if available
                    #     diagnostic_context = ""
                    #     if not analysis['is_legitimate_zero']:
                    #         issues = analysis['diagnostic_info'].get('issues', [])
                    #         if issues:
                    #             diagnostic_context = f"\n\n**Diagnostic Info:** {json.dumps(issues, indent=2)}"
                        
                    #     messages.append({"role": "system", "content": system_prompt})
                    #     messages.append({
                    #         "role": "user",
                    #         "content": f"User Query: {rewritten_user_message}\n\nSQL Generated: {clean_sql}\n\nResult: 0 records{diagnostic_context}"
                    #     })
                        
                    #     # Optionally store the confidence in your DB for analytics
                    #     # This helps you tune the handler over time
                    #     if 'confidence' in analysis:
                    #         logger.info(f"Zero-result confidence: {analysis['confidence']}")

                    elif(num_rows > 19):
                        system_prompt = f"""
                        You are an advanced data summarizer chatbot. You just created and executed an SQL query based on a user prompt, 
                        and found {num_rows} records. Showing all of them at once could overwhelm the response. 

                        You should inform the user about the {num_rows} records found, and then guide them with intelligent follow-up 
                        options to refine or simplify the results. For example, you can ask:

                        1. Would you like me to show only the top results (e.g., first 10 or 20 rows)?
                        2. Do you want me to display only specific fields/columns instead of the full records?
                        3. Would you like to filter the results further (e.g., by timeframe, category, or condition)?
                        4. Or do you want me to generate a preview sample so you can decide how to narrow it down?

                        Always encourage the user to refine their request in a way that makes the data more digestible and actionable.
                        """
                        messages.append({"role": "system", "content": system_prompt})
                        messages.append({
                            "role": "user",
                            "content": f"Based on my prompt, you found too many records. Now, ask me some intelligent question for your better response.\n\n My Prompt: {rewritten_user_message}"
                        })

                    else:
                        cols_to_check = ["fault_description", "first_observation", "action_taken"]
                        preview_rows = df_result.head(3) if num_rows > 9 and any(col in df_result.columns for col in cols_to_check) else df_result
                        system_prompt = config.DATA_SUMMARIZER_PROMPT
                        messages.append({"role": "system", "content": system_prompt})
                        messages.append({
                            "role": "user",
                            "content": f"Here is the user's request and the data you retrieved. Please summarize the data according to your instructions.\n\nUser's Request: {rewritten_user_message}\n\nData:\n{preview_rows.to_string()}"
                        })
                except Exception as e:
                    logger.info(f"Error: {e}")
                    intent = config.CLASS_LABELS[1]  # fallback
            else:
                intent = config.CLASS_LABELS[1]
        else:
            intent = config.CLASS_LABELS[1]

    if intent == config.CLASS_LABELS[1]:
        try:
            context, unique_sources = rag_obj.retrieve_from_collection(config.FAULT_INFO_COLLECTION, rewritten_user_message)
            system_prompt = config.RAG_SUMMARIZER_PROMPT+context
            messages.append({"role": "system", "content": system_prompt})
            # user_content_with_context = f"Use the following past fault related historical data to answer the user's question.\n\Historical Data:\n{context}\n\nUser Question:\n{rewritten_user_message}"
            messages.append({"role": "user", "content": f'User Question:\n{rewritten_user_message}'})
        except Exception as e:
            logger.error(f"Error retrieving from FAULT_INFO collection: {e}")
            messages.append({"role": "user", "content": rewritten_user_message})

    elif intent == config.CLASS_LABELS[2]:
        try:
            context, unique_sources = rag_obj.retrieve_from_collection(config.DOMAININFO_COLLECTION, rewritten_user_message)
            system_prompt = config.DOMAIN_INFO_PROMPT
            messages.append({"role": "system", "content": system_prompt})
            user_content_with_context = f"Context:\n{context}\n\nQuestion:\n{rewritten_user_message}"
            messages.append({"role": "user", "content": user_content_with_context})
        except Exception as e:
            logger.error(f"Error retrieving from DOMAININFO collection: {e}")
            messages.append({"role": "user", "content": rewritten_user_message})
    else:
        messages.append({"role": "user", "content": rewritten_user_message})

    # --- Ensure valid alternation ---
    safe_messages = ensure_message_alternation(messages) if messages else [{"role": "user", "content": rewritten_user_message}]

    return {
        "messages": safe_messages,
        "intent_result": intent_result or {"classified_intent": intent},
        "sql_query": sql_query_to_send,
        "context": context,
        "unique_sources": unique_sources,
    }


# --- FastAPI Routes ---

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Renders the main chat interface and starts a session."""
    return templates.TemplateResponse("index.html", {"request": request})
@app.post("/stream_chat")
async def stream_chat(chat_message: ChatMessage, request: Request):
    user_message = chat_message.message
    streaming_enabled = chat_message.streaming_enabled
    current_mode = chat_message.current_mode

    raw_body = await request.body()
    session_id = request.headers.get("x-session-id")
    conversation_history = get_history_from_db(session_id)

    rewritten_user_message = rewrite_query_with_history(
        qwen_base_model, qwen_tokenizer, conversation_history, user_message
    )
    conversation_history.append({"role": "user", "content": user_message})

    logger.info(f"User message: {user_message}")
    logger.info(f"Rewritten User Message: {rewritten_user_message}")
    logger.info(f"Current Mode: {current_mode}")
    logger.info(f"Conversation History: {conversation_history}")

    pipeline_data = await prepare_pipeline(user_message, rewritten_user_message, current_mode, conversation_history)

    if streaming_enabled:
        async def stream_gen():
            chatbot_response = ""  # initialize locally
            async for chunk in stream_inference_generator(pipeline_data["messages"]):
                yield chunk
                # accumulate chunk text
                try:
                    chunk_json = json.loads(chunk[len("data: "):])
                    if "chunk" in chunk_json:
                        chatbot_response += chunk_json["chunk"]
                except:
                    continue
            if pipeline_data["sql_query"]:
                yield f"data: {json.dumps({'sql_query': pipeline_data['sql_query']})}\n\n"
            if pipeline_data["unique_sources"]:
                yield f"data: {json.dumps({'sources': [f'{i+1}. {src}' for i, src in enumerate(pipeline_data['unique_sources'])]})}\n\n"

            # Log after streaming is done
            inserted_message_id = store_chats_in_db(
                session_id,
                user_message,
                rewritten_user_message,
                pipeline_data["intent_result"],
                chatbot_response,
                pipeline_data["sql_query"],
                pipeline_data["context"],
                {"sources": pipeline_data["unique_sources"]}
            )
            if inserted_message_id:
                yield f"data: {json.dumps({'message_id': str(inserted_message_id)})}\n\n"
            else:
                yield f"data: {json.dumps({'message_id': None, 'warning': 'db_save_failed'})}\n\n"
            
            yield f"data: {json.dumps({'status': 'DONE'})}\n\n"

        return StreamingResponse(stream_gen(), media_type="text/event-stream")
    else:
        chatbot_response = ""
        async for chunk_data in inference_generator(pipeline_data["messages"]):
            try:
                chunk_json = json.loads(chunk_data[len("data: "):])
                if "chunk" in chunk_json:
                    chatbot_response += chunk_json["chunk"]
            except:
                continue

    # Log into the database
    inserted_message_id = store_chats_in_db(
        session_id,
        user_message,
        rewritten_user_message,
        pipeline_data["intent_result"],
        chatbot_response,
        pipeline_data["sql_query"],
        pipeline_data["context"],
        {"sources": pipeline_data["unique_sources"]}
    )

    return {
        "response": chatbot_response,
        "sql_query": pipeline_data["sql_query"],
        "sources": [f"{i+1}. {src}" for i, src in enumerate(pipeline_data["unique_sources"])],
        "message_id": inserted_message_id
    }


@app.get("/suggestions")
async def suggestions():
    suggestions_path = r'C:\Users\admin\Documents\chatbot\app\frontend\static\data\suggestions.json'
    return FileResponse(suggestions_path)

class Feedback(BaseModel):
    message_id: str
    session_id: str
    feedback_type: str
    comment: str | None = None

from sqlalchemy import text

@app.post("/feedback")
def save_feedback(data: Feedback):
    logger.info(f"Feedback: {data}")

    if data.feedback_type not in ("like", "dislike"):
        raise HTTPException(status_code=400, detail="Invalid feedback type.")

    try:
        with engine.begin() as conn:  # automatically handles commit/rollback
            conn.execute(
                text("""
                    INSERT INTO dbo.feedback (message_id, session_id, feedback_type, comment, timestamp)
                    VALUES (:message_id, :session_id, :feedback_type, :comment, SYSDATETIMEOFFSET())
                """),
                {
                    "message_id": data.message_id,
                    "session_id": data.session_id,
                    "feedback_type": data.feedback_type,
                    "comment": data.comment,
                }
            )
        return {"status": "success", "feedback_type": data.feedback_type}
    except Exception as e:
        logger.error(f"An error occurred while saving feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/start_session")
async def start_session():
    session_id = str(uuid.uuid4())
    start_time = datetime.now()

    insert_sql = text("""
        INSERT INTO sessions (session_id, start_time)
        VALUES (:session_id, :start_time)
    """)
    connection = engine.connect()
    try:
        connection.execute(insert_sql, {
                "session_id": session_id,
                "start_time": start_time
        })
        connection.commit()
        return {"status": "success", "session_id": session_id}
    except Exception as e:
        logger.error(f"Error executing SQL on SQL Server: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        connection.close()

@app.post("/end_session")
async def end_session(request: Request):
    session_id = request.headers.get("x-session-id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing session_id")


    end_time = datetime.now()

    update_sql = text("""
    UPDATE sessions
    set end_time = :end_time
    WHERE session_id = :session_id
    """)
    connection = engine.connect()
    try:
        connection.execute(update_sql, {
                "end_time":end_time,
                "session_id":session_id
            })

        connection.commit()
        return {"status": "success", "session_id": session_id, "end_time": str(end_time)}
    
    except Exception as e:
        logger.error(f"Error updating end_time for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        connection.close()

@app.post("/frontend_log")
async def frontend_log(log_data: FrontendLog):
    logger.info(f"===[FRONTEND LOG]=== {log_data.dict()}")
    return {"status": "logged"}

# --- Application Initialization ---
def initialize_services():
    """Initializes the LLM, mistral_tokenizer, qwen_tokenizer and other services."""
    global qwen_base_model, mistral_tokenizer, qwen_tokenizer, device, classifier_obj, rag_obj, nl2sql_obj, zero_handler
    logger.info("Starting service initialization...")

    try:
        # --- Device Setup ---
        if torch.cuda.is_available():
            device = torch.device("cuda")
            logger.info(f"Using GPU: {torch.cuda.get_device_name(0)}")
        else:
            device = torch.device("cpu")
            logger.info("Using CPU")

        # --- Quantization Configuration (Optional but Recommended) ---
        # Use 4-bit quantization to reduce memory footprint
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True, 
            bnb_4bit_compute_dtype=torch.bfloat16,
            llm_int8_enable_fp32_cpu_offload=True
        )
        
        logger.info(f"Loading mistral_tokenizer for model: {config.MISTRAL_BASE_MODEL_PATH}")
        mistral_tokenizer = AutoTokenizer.from_pretrained(config.MISTRAL_BASE_MODEL_PATH)
        mistral_tokenizer.pad_token = mistral_tokenizer.eos_token
        qwen_tokenizer = AutoTokenizer.from_pretrained(
            config.QWEN3_8B_MODEL_PATH,
            local_files_only = True
        )
        qwen_tokenizer.pad_token = qwen_tokenizer.eos_token


        tinyllama_tokenizer = AutoTokenizer.from_pretrained(config.TINYLLAMA_BASE_MODEL_PATH)
        tinyllama_tokenizer.pad_token = tinyllama_tokenizer.eos_token

        logger.info(f"Loading model: {config.MISTRAL_BASE_MODEL_PATH}. This may take a while...")

        # For NL2SQL:
        base_model_nl2sql = AutoModelForCausalLM.from_pretrained(
            config.MISTRAL_BASE_MODEL_PATH,
            quantization_config=bnb_config,
            device_map="auto"
        )

        # For Summarization and general use:
        # qwen_base_model = AutoModelForCausalLM.from_pretrained(
        #     config.MISTRAL_BASE_MODEL_PATH,
        #     quantization_config=bnb_config,
        #     device_map="auto"
        # )

        qwen_base_model = AutoModelForCausalLM.from_pretrained(
            config.QWEN3_8B_MODEL_PATH,
            quantization_config=bnb_config,
            device_map="auto",
            local_files_only = True
        )

        qwen_base_model.gradient_checkpointing_enable()
        qwen_base_model.config.use_cache = False

        tinyllama_base_model = AutoModelForCausalLM.from_pretrained(
            config.TINYLLAMA_BASE_MODEL_PATH,
            quantization_config = bnb_config,
            device_map = "auto"            
        )

        logger.info(f"LLM Model: {config.QWEN3_8B_MODEL_PATH} Initialized Successfully.")

    except Exception as e:
        logger.critical("Failed to initialize LLM model.", exc_info=True)
        exit(1)

    try:
        classifier_obj = IntentClassifier(qwen_base_model, qwen_tokenizer, tinyllama_base_model, tinyllama_tokenizer)
        logger.info("Intent Classifier Initialized Successfully.")
    except Exception as e:
        logger.critical("Failed to initialize intent classifier.", exc_info=True)
        exit(1)

    try:
        nl2sql_obj = NL2SQL(base_model_nl2sql, mistral_tokenizer)
        logger.info("NL2SQL Model Initialized Successfully.")
    except Exception as e:
        logger.critical("Failed to initialize NL2SQL Model.", exc_info=True)
        exit(1)

    try:
        rag_obj = RagSetup()
        logger.info("RAG Setup Initialized Successfully.")
    except Exception as e:
        logger.critical("Failed to initialize RAG setup.", exc_info=True)
        exit(1)

    try:
        zero_handler = SmartZeroResultsHandler(nl2sql_obj, logger)
        logger.info("Smart Zero Results Handler Initialized Successfully.")
    except Exception as e:
        logger.critical("Failed to initialize zero handler.", exc_info=True)
        exit(1)

    logger.info("All services initialized successfully.")

# --- Startup and Shutdown Events ---
@app.on_event("startup")
async def startup_event():
    initialize_services()

# Add shutdown handler for the classifier:
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutting down...")
    if classifier_obj:
        classifier_obj.shutdown()  # Clean up thread pool

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000, log_level="info")