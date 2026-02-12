import config
import logging
from sqlalchemy import create_engine
from langchain_core.prompts import PromptTemplate
import sqlglot
import re
import pandas as pd
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
import torch
from peft import PeftModel
import gc

config.setup_logging()
logger = logging.getLogger(__name__)
logger.info("logging started...")

class NL2SQL:
    def __init__(self, base_model, tokenizer):
        nl2sql_model =  PeftModel.from_pretrained(base_model, config.NL2SQL_ADAPTER_PATH)
        self.nl2sql_model = nl2sql_model
        self.tokenizer = tokenizer
        self.engine = create_engine(config.SQLALCHEMY_CONNECTION_STRING)
        self.df = None

    def generate_query_using_llm(self, user_query, max_new_tokens=256):
        try:
            # This should match the format you used for training, including any system prompt
            # If you trained with an explicit system prompt, include it here:
            system_prompt = """You are a helpful assistant that translates natural language queries into SQL queries for a SQL server database.
        The database contains a table named 'fault_bookv3' with the following relevant columns:
            
        - fault_id (BIGINT, NOT NULL) : unique ID for each fault
        - fault_time (DATETIME, NOT NULL) : timestamp when the fault occurred
        - fault_duration (VARCHAR(25), NOT NULL) : how long the fault persisted
        - system_name (VARCHAR(50)) : high-level system category
        - device_name (VARCHAR(50)) : specific device/part of the system
        - fault_description (VARCHAR(2000)) : detailed description of the fault
        - persons_involved (VARCHAR(200)) : names of people involved in solving the fault
        - action_taken (VARCHAR(500)) : steps taken to resolve the fault
        - faulty_system (VARCHAR(200)) : more granular device info (often NULL)
        - human_error (VARCHAR(200)) : values are 'yes', 'no', or NULL
        - document_name (VARCHAR(50)) : document name if a report was created
        - fda_entry (VARCHAR(3), NOT NULL) : values are 'yes' or 'no'
        - logged_by (VARCHAR(25)) : who logged the fault
        - log_time (DATETIME) : when the fault was logged
        - first_observation (VARCHAR(4000), NOT NULL) : initial observation of failure
        - beam_affected (VARCHAR(3), NOT NULL) : values are 'yes' or 'no'
            
        Always provide only the SQL query as your response, without any additional text.
        """
            # - Whenever applicable, add 'ORDER BY fault_id DESC' at the end of the query to return the most recent faults first.

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ]
            
            input_ids = self.tokenizer.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=True, # Crucial: tells the model it's starting a new assistant turn
                return_tensors="pt"
            )

            if torch.cuda.is_available() :
                device = "cuda"
            else:
                device = "cpu"

            input_ids = input_ids.to(device)

            outputs = self.nl2sql_model.generate(
                input_ids=input_ids,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                # temperature=0.7,
                # top_p=0.9,
                eos_token_id=self.tokenizer.eos_token_id,
                pad_token_id=self.tokenizer.pad_token_id,
            )

            # Decode only the newly generated part (after the input)
            generated_text = self.tokenizer.decode(outputs[0][input_ids.shape[1]:], skip_special_tokens=True)
            logger.info(f"Generated Query: {generated_text}")

            # del self.nl2sql_model
            # self.nl2sql_model = None  # clear attribute explicitly
            # gc.collect()
            # torch.cuda.empty_cache()
            # torch.cuda.ipc_collect()

            return generated_text

            # Try this for more deterministic answer
            outputs = self.nl2sql_model.generate(
                input_ids,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                num_beams=5,
                num_return_sequences=5,
            )
            
            generated_queries = []
            for i in range(outputs.shape[0]):
                output_ids = outputs[i]
                # Skip the prompt tokens if outputs contain prompt + generated
                generated_text = self.tokenizer.decode(
                    output_ids[input_ids.shape[1]:],
                    skip_special_tokens=True
                )
                generated_queries.append(generated_text.strip())
                print(generated_text.strip())
                logger.info(f"Genereated Queries: {generated_text.strip()}")
            return generated_queries
        except Exception as e:
            logger.info(f"Generating query using LLM failed due to Error: {e}")
            return None

    def extract_sql(self, text):
        # Remove markdown blocks
        if "```sql" in text:
            sql = re.findall(r"```sql\s*(.*?)```", text, re.DOTALL)
            if sql:
                return sql[0].strip()
        # Remove "Here is the SQL query:" and capture the SQL
        pattern = r"(SELECT|WITH|INSERT|UPDATE|DELETE).*"
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(0).strip()
        # If none found, return the original text as fallback
        return text.strip()

    def validate_sql_syntax(self, sql_text):
        clean_sql = self.extract_sql(sql_text['result'] if isinstance(sql_text, dict) else sql_text)
        logger.info(f"Cleaned Query: {clean_sql}")
        try:
            parsed = sqlglot.parse_one(clean_sql, read='tsql')  # Use 'tsql' for SQL Server
            logger.info("SQL syntax is valid.")
            return True, None
        except sqlglot.errors.ParseError as e:
            logger.info(f"SQL syntax error: {e}")
            return False, str(e)

    def execute_query(self, sql_query):
        try:
            with self.engine.connect() as connection:
                self.df = pd.read_sql_query(sql_query, connection)
            
            logger.info("Data fetched successfully from server...")
            logger.info(f"Here's the top 3 rows from the fetched data: {self.df.head(3)}")
            return self.df
        except Exception as e:
            logger.info(f"❌ Error fetching data from SQL Server: {e}")
        pass

if __name__ == "__main__":
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16
    )
    tokenizer = AutoTokenizer.from_pretrained(config.MISTRAL_MODEL_PATH)
    model = AutoModelForCausalLM.from_pretrained(
        config.MISTRAL_MODEL_PATH,
        quantization_config = bnb_config if torch.cuda.is_available() else None,
        device_map = "auto"
    )

    obj = NL2SQL(model, tokenizer)
    prompt = "Show recent faults where water leakage was observed?"
    sql_text = obj.generate_query_using_llm(prompt)
    print(f"Generated Query: {sql_text}")
    clean_sql = obj.extract_sql(sql_text)
    print(f"Clean SQL: {clean_sql}")
    validation_status, _ = obj.validate_sql_syntax(clean_sql)
    print(f"Validated: {validation_status}")
    if validation_status:
        result = obj.execute_query(clean_sql)
        print(result)
    else:
        print("Invalid SQL Query, Check Logs...")