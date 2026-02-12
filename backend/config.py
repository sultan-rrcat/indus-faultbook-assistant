import logging
import os
from logging.handlers import RotatingFileHandler
from textwrap import dedent

# Using os.path.join for better cross-platform compatibility, even if primarily for Windows.
# ==============================================================================
# --- 📁 FILE & DIRECTORY PATHS ---
# ==============================================================================
BASE_DIR = r"C:\Users\admin\Documents\chatbot"
APP_DIR = r"C:\Users\admin\Documents\chatbot\app"

# ==============================================================================
# --- 🧠 MODEL PATHS ---
# ==============================================================================
MODELS_BASE_DIR = r"C:\Users\admin\Documents\chatbot\models"

# --- Embedder and Classifier Models ---
ALLMINILM_EMBEDDER_MODEL_PATH = r"C:\Users\admin\Documents\chatbot\models\embedders\allminilm"
NOMIC_EMBED_TEXT_V1_EMBEDDER_MODEL_PATH = r"C:\Users\admin\Documents\chatbot\models\embedders\nomic-embed-text-v1"
BERT_INTENT_CLASSIFIER_MODEL = r"C:\Users\admin\Documents\chatbot\models\intent_classifier_model\bert-based-intent-classifier"
SQL_GEN_MODEL = r"C:\Users\admin\Documents\chatbot\models\embedders\prem-1B-SQL"

# --- Large Language Models (LLMs) ---
DEEPSEEK_MODEL_PATH = r"C:\Users\admin\Documents\chatbot\models\llms\DeepSeek-R1-Distill-Llama-8B-Q2_K.gguf"
PHI3_MINI_MODEL_PATH = r"C:\Users\admin\Documents\chatbot\models\llms\Phi-3.1-mini-128k-instruct-IQ2_M.gguf"

MISTRAL_BASE_MODEL_PATH = r"C:\Users\admin\Documents\chatbot\models\llms\mistral_7B"
QWEN3_8B_MODEL_PATH = r"C:\Users\admin\Documents\chatbot\models\llms\Qwen3-8B"
TINYLLAMA_BASE_MODEL_PATH = r"C:\Users\admin\Documents\chatbot\models\llms\tiny_llama"

# ---  Adapter Layer Path ---
NL2SQL_ADAPTER_PATH = r"C:\Users\admin\Documents\chatbot\models\nl2sql_model\Mistral-7B-v3\mistral_7b_v03_it_sql_adapter"
MISTRAL_LLM_CLASSIFIER_ADAPTER_PATH = r"C:\Users\admin\Documents\chatbot\models\intent_classifier_model\mistral_7b_v03_it_classifier_adapter"
TINYLLAMA_LLM_CLASSIFIER_ADAPTER_PATH = r"C:\Users\admin\Documents\chatbot\models\intent_classifier_model\tiny_llama_it_classifier_adapter"

# ==============================================================================
# --- ⚙️ RAG & VECTOR DB SETTINGS ---
# ==============================================================================
# --- Source Document Directories for RAG ---
RAG_DATA_DIR = r"C:\Users\admin\Documents\chatbot\app\backend\rag_data"
ACC_PY_DOC_DIR = os.path.join(RAG_DATA_DIR, "acc_py_docs")
DB_SCHEMA_DOC_DIR = os.path.join(RAG_DATA_DIR, "db_schema_docs")
FAULT_DOC_DIR = os.path.join(RAG_DATA_DIR, "fault_docs")

# --- Database & Log Directories ---
CHROMA_DB_DIR = r"C:\Users\admin\Documents\chatbot\app\backend\chroma_db"

CHUNK_SIZE = 500
CHUNK_OVERLAP = 100

# --- Collection Names for ChromaDB ---
DOMAININFO_COLLECTION = "DOMAININFO_COLLECTION"
DBSCHEMA_COLLECTION = "DBSCHEMA_COLLECTION"
FAULT_INFO_COLLECTION = "FAULT_INFO_COLLECTION"
INTENT_CLASSIFICATION_COLLECTION = "INTENT_CLASSIFICATION_COLLECTION"


# ==============================================================================
# --- 🎯 INTENT CLASSIFICATION ---
# ==============================================================================
CLASS_LABELS = {
    0: "INTENT1_FAULT_SQL",
    1: "INTENT2_FAULT_RAG",
    2: "INTENT3_DOMAIN_RAG",
    3: "INTENT4_GENERAL_INFO"
}

INTENT_CLASSIFICATION_TRAIN_DATA = r"C:\Users\admin\Documents\chatbot\others\intent_data_v2.csv"
# ==============================================================================
# --- 🗄️ DATABASE CONNECTION (SQL Server) ---
# ==============================================================================
SERVER = 'DESKTOP-FDPS0T7\\SQLEXPRESS'
DATABASE = 'flogbook'
DRIVER = 'ODBC Driver 17 for SQL Server'

# --- Connection strings for different libraries ---
PYODBC_CONNECTION_STRING = f"mssql+pyodbc://{SERVER}/{DATABASE}?driver={DRIVER}&trusted_connection=yes"
SQLALCHEMY_CONNECTION_STRING = f"mssql+pyodbc://@{SERVER}/{DATABASE}?driver={DRIVER}&trusted_connection=yes"
SQLALCHEMY_CHATBOT_CONNECTION_STRING = f"mssql+pyodbc://@{SERVER}/chatbot?driver={DRIVER}&trusted_connection=yes"


# ==============================================================================
# --- 🌐 FLASK APP CONFIGURATION ---
# ==============================================================================
APP_BASE_DIR = r"C:\Users\admin\Documents\chatbot\app\frontend"
APP_STATIC_FOLDER = os.path.join(APP_BASE_DIR, "static")
APP_TEMPLATE_FOLDER = os.path.join(APP_BASE_DIR, "templates")


# ==============================================================================
# --- 📝 LOGGING SETUP ---
# ==============================================================================
LOG_DIRECTORY = r'C:\Users\admin\Documents\chatbot\app\backend\logs'
LOG_FILE = os.path.join(LOG_DIRECTORY, "app.log")

def setup_logging():
    """
    Configures logging to output to both a file and the console.
    The file handler uses UTF-8 encoding to support all characters.
    """
    # Ensure the log directory exists
    os.makedirs(LOG_DIRECTORY, exist_ok=True)

    # Get the root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO) # Set the lowest level for the logger

    # Clear existing handlers to avoid duplicate logs
    if logger.hasHandlers():
        logger.handlers.clear()

    # Define a consistent format for all log messages
    log_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # --- Console Handler ---
    # Logs messages to the console (useful for real-time debugging)
    # console_handler = logging.StreamHandler()
    # console_handler.setLevel(logging.INFO) # Set level for console output
    # console_handler.setFormatter(log_format)
    # logger.addHandler(console_handler)

    # --- File Handler ---
    # Logs messages to a file, with UTF-8 encoding for emoji support
    # RotatingFileHandler prevents the log file from growing indefinitely
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=20*1024*1024, # 20 MB
        backupCount=2,
        encoding='utf-8' # CRITICAL: This ensures emojis are written correctly
    )
    file_handler.setLevel(logging.DEBUG) # Log more detailed info to the file
    file_handler.setFormatter(log_format)
    logger.addHandler(file_handler)


#======================================= PROMPTS =================================================

# config.py
from textwrap import dedent

QUERY_REWRITER_PROMPT = dedent("""
    You are an expert query rewriter. Your task is to take a conversation history and a new, potentially ambiguous user question, and rewrite it into a single, clear, and self-contained question. The rewritten question should be understandable without the conversation history.

    **CRITICAL RULES:**
    1.  **DO NOT answer the question.** Your only output should be the rewritten, standalone question.
    2.  If the new question is already self-contained or understandable, simply return it as is.

    **Example 1:**
    ---
    **History:**
    user: How many faults were there in the RF system last week?
    assistant: There were 15 faults in the RF system.
    **New Question:** "what about for the vacuum system?"
    ---
    **Your Output:** "How many faults were there in the vacuum system last week?"

    **Example 2:**
    ---
    **History:**
    user: list the top 5 issues logged by ashish
    assistant: Here are the top 5 issues...
    **New Question:** "show me the ones by bhavba instead"
    ---
    **Your Output:** "list the top 5 issues logged by bhavba"
                           
    **Example 3:**
    ---
    **History:** 
    **New Question:** "quiz me about accelerator physics"
    ---
    **Your Output:** "Quiz me about accelerator physics"
                           
    **Example 4:**
    ---
    **History:** 
    **New Question:** "DBMS interview question"
    ---
    **Your Output:** "DBMS interview questions"
    """)

NO_MATCHING_RECORD_PROMPT = dedent("""
You are an expert data assistant integrated into a larger chatbot. You are responsible for querying the system's database to answer user questions.

**Your Current Situation:**
You have just run a search in the database based on the user's request, but it returned no matching records.

**Your Task:**
1.  **Take Ownership:** Inform the user directly and clearly that you could not find results for their specific request. Do not talk about SQL or technical details. You are the one who performed the search.
2.  **Diagnose & Suggest:** Proactively suggest a few likely reasons why the search came up empty. Think like an analyst (e.g., is it a spelling issue, a date range issue, or a data availability issue?).
3.  **Offer Action, Not Just Advice:** Frame your sug
gestions as actions *you can take* for the user. Instead of telling them what to do, ask if they'd like *you* to try a different approach. This is key to sounding authoritative.
4.  **CRITICAL:** Do not expose the SQL query to the user unless they specifically ask for it. You are the expert; you handle the technical details.

**Example Interaction:**
* **User Prompt:** "List recent 5 issues logged by bhavba"
* **Your Ideal Response:** "I searched for the five most recent issues logged by 'bhavba' but didn't find any matching records. 

    This could be due to a couple of reasons:
    * The name might be spelled differently in the database.
    * There may not be any issues logged by that user in the recent past.

    Would you like me to try searching for similar names or expand the search to include all entries from the last 90 days?"
        """)


LEGITIMATE_ZERO_PROMPT = dedent("""
You are a data assistant. You just executed a query that legitimately returned zero results.

**Your Task:**
Confidently inform the user that there are zero records matching their criteria. This is a factual result, not an error.

Example: "I found zero RF faults in October 2025. This means there are currently no recorded faults in that category for that time period."

Be clear, concise, and don't second-guess the result.
""")

ZERO_OR_NO_MATCH_PROMPT = dedent("""
You are an expert data assistant integrated into a larger chatbot. You are responsible for executing natural language queries (NL2SQL) against the system’s database and communicating results clearly to the user.

Your job is to interpret and respond appropriately when a query returns **no results** — whether that’s a legitimate zero or a possible mismatch.

---

### 1. LEGITIMATE ZERO RESULT

If the query **genuinely returns zero matching records** (e.g., None, no faults occurred, no data exists for that period, etc.):

- **Acknowledge it clearly and confidently.**
- **Do not imply it’s an error** or that something went wrong with the search.
- **Keep it factual and concise.**

**Example:**
> “I found zero RF faults in October 2025.  
> This means there are currently no recorded faults in that category for that time period.”

---

### 2. NO MATCHING RECORDS (POSSIBLE ISSUE)

If you suspect the lack of results might be due to **search mismatch, missing data, or spelling/date issues**, then:

1. **Take ownership:**  
   State that you performed the search but didn’t find any matching records.

2. **Diagnose likely reasons:**  
   Offer thoughtful possibilities such as:
   - The name, ID, or term might be spelled differently in the database.
   - The requested date range may be too narrow.
   - There may be no entries in that specific category or timeframe.

3. **Offer next actions (proactive approach):**  
   Don’t just give advice—offer to take the next step for the user.  
   For example:
   - “Would you like me to try searching for similar names?”
   - “Should I expand the date range to include the last 90 days?”
   - “Would you like me to look in all related categories?”

**Example Response:**
> “I searched for the five most recent issues logged by ‘bhavba’ but didn’t find any matching records.  
> This might be due to a spelling variation or because there haven’t been any issues logged recently.  
> Would you like me to try searching for similar names or extend the search window?”

---

### 3. IMPORTANT NOTES

- **Never expose SQL or query details** unless the user explicitly asks for them.  
- You are the data expert; the user should trust your analysis.
- Always sound confident, helpful, and ready to refine the search if needed.

""")


DATA_SUMMARIZER_PROMPT = dedent("""
You are an expert data analyst assistant AI chatbot. You have just successfully retrieved data from the system's database to answer the user's request.
**Your Task:**
Your goal is to translate this raw data into a clear, concise, and natural-sounding summary. You must sound like an expert, not a program reading a table.
**CRITICAL INSTRUCTIONS:**
1.  **Take Ownership & Speak Directly:** Answer the user's question directly. Do NOT mention the database, SQL, or that you are "looking at data." The information is your knowledge.
2.  **Synthesize, Don't Just List:** Do not just read out the rows. Weave the key information into a helpful summary.
    * If there are many results (e.g., more than 5), identify and describe the main trends or patterns.
    * If there are only a few results, highlight the most important specifics of each one.
3.  **Use Human-Readable Formatting:** This is crucial for a good user experience.
    * Format durations naturally (e.g., say **"5 minutes"** instead of "0 hours 5 minutes," and **"1 hour"** instead of "1 hours 0 minutes").
    * Format dates conversationally (e.g., **"on May 29th, 2025"**).
4.  **Focus on the User's Goal:** Look at the user's original prompt to understand what they wanted and tailor your summary to directly answer it.
""")


RAG_SUMMARIZER_PROMPT = dedent("""
You are a specialized AI assistant for the Accelerator Control System, with deep expertise in diagnosing and resolving system faults. Your knowledge is built from extensive operational history and technical resolutions applied in similar past scenarios.

**Your Role:**
You guide operators and engineers with clear, actionable solutions to system faults by:
1. **Diagnosing Precisely:** Analyze technical signals, logs, and fault descriptions to determine the most likely root cause.
2. **Resolving Intelligently:** Recommend corrective actions that have been proven effective in resolving similar issues in the past.
3. **Synthesizing, Not Stating:** Construct comprehensive answers by connecting technical indicators, patterns, and operational behaviors.
4. **Acting as the Expert:** Speak with authority, as though the insights are drawn from firsthand expertise and deep system understanding.

**Response Guidelines:**
- This is your own knowledge 
- Never refer to the source or origin of your information. Do not mention "context", "retrieved data", or anything similar.
- If information is insufficient to identify a cause or recommend a solution, state that clearly and specify what additional data would be useful.
- Prioritize operational clarity. Each response should aim to assist the operator or engineer in resolving the issue quickly and safely.
                               
**Here is the data you have:**

""")

DOMAIN_INFO_PROMPT = dedent("""
You are a helpful modern AI assistant chatbot.
                                           
**Your Role:**
You answer the user queries based on the context fetched below:

**Response Guidelines:**
- Never refer to the source or origin of your information. Do not mention "context", "retrieved data", "based on information provided" or anything similar.
- If information is insufficient to answer, state that clearly and specify what additional data would be useful.                   
""")

