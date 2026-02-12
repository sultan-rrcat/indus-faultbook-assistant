# Versions
**version 0.2:**

**version 0.1:**
*Date: 16/09/2025*
* frontend changes 
  - streaming and mode selection incorporated.
* backend changes
  - a new async function 'inference generator' was created with 'stream inference generator'
  - static prompts are send to config files
  - mode checking added.
  - refined the training dataset for more flexible matching.


# Indus Faultbook Assistant

**Indus Faultbook Assistant** is a sophisticated, AI-powered chatbot designed to support the operations and diagnostics of the Indus accelerator control system. It leverages a multi-stage pipeline including intent classification, query rewriting, and Retrieval-Augmented Generation (RAG) to provide accurate, context-aware answers to user queries.

-----

## 🛠️ Technology Stack

### **Backend**

  * **Framework:** Flask
  * **Language:** Python 3.10
  * **Core AI/ML Libraries:**
      * `transformers`: For loading and running LLMs.
      * `torch`: The deep learning framework.
      * `peft`: For loading fine-tuned LoRA adapters (TinyLlama).
      * `bitsandbytes`: For 4-bit quantization of models to save resources.
      * `SQLAlchemy`: For database interaction.
  * **Database:** SQL Server (via `pyodbc`) for conversation logging and session management.
  * **Vector Database:** An unspecified vector database is used for the RAG pipelines (interfaced via `rag_setup.py`).

### **Frontend**

  * **Framework:** Vanilla JavaScript (ES6 Modules)
  * **Core Logic:**
      * `fetch` API for streaming Server-Sent Events (SSE).
      * `marked.js`: For rendering Markdown in chat responses.
  * **Styling:** Custom CSS.

### **AI Models**

  * **Primary LLM (Summarization, Rewriting, General Chat):** `mistralai/Mistral-7B-Instruct-v0.3`
  * **Intent Classification (Ensemble):**
      * Mistral 7B (as a zero-shot classifier)
      * Fine-tuned `TinyLlama` model
      * Fine-tuned `BERT` model
  * **NL2SQL Model:** A fine-tuned version of `mistral-7B` is used for this task.

-----

## 📋 Functional Requirements & Setup

### **Prerequisites**

  * Python 3.10+
  * NVIDIA GPU with CUDA support (for quantized models)
  * Access to a SQL Server database
  * Access to a running Vector Database instance

### **Installation**

1.  **Clone the repository:**

    ```bash
    git clone <your-repo-url>
    cd <your-repo-folder>
    ```

2.  **Create and activate a virtual environment:**

    ```bash
    python -m venv env
    source env/bin/activate  # On Windows: env\Scripts\activate
    ```

3.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure environment variables:**

      * Create a `.env` file or set environment variables for database connection strings, model paths, and other configurations specified in the `config.py` file.

5.  **Run the application:**

    ```bash
    python app/backend/gpu.py
    ```

    The application will be available at `http://127.0.0.2:5000`.

-----

-----

## ✨ Key Features

  * **Advanced Conversational AI:** Handles multi-turn dialogues and follow-up questions using a database-backed memory and query rewriting.
  * **Multi-Pipeline Architecture:** To handle various kinds of questions from users, the system uses a robust, multi-stage intent classification pipeline to route user prompts intelligently. The architecture identifies four primary intent categories:
      * **INTENT1\_FAULT\_SQL:** For queries that ask for specific, factual, or quantifiable information related to accelerator control faults.
      * **INTENT2\_FAULT\_RAG:** For queries that require a deeper, more explanatory answer about a fault related to accelerator control systems.
      * **INTENT3\_DOMAIN\_RAG:** For questions that ask about internal, domain-specific information related to RRCAT, Indus-1, Indus-2, and Indian accelerator control systems.
      * **INTENT4\_GENERAL\_INFO:** A fallback for general chitchat, greetings, or any question that does not fit into the other three categories.
  * **Ensemble-Based Intent Classification:** To accurately classify the user's intent, the system uses a combination of three techniques:
    1.  A 4-bit quantized **Mistral 7B** model leveraged with advanced prompt engineering.
    2.  A fine-tuned **TinyLlama 1B** model.
    3.  A fine-tuned, embedding-based **BERT** classifier.
  * **Real-time Streaming:** Streams responses token-by-token for an interactive, real-time user experience.
  * **Dynamic Frontend Feedback:** Provides users with real-time status updates on the backend pipeline (e.g., "Searching the database...", "Summarizing results...").
  * **Persistent Memory:** All conversations are logged in a SQL database, allowing for robust session management and future analysis.

-----

## 🏗️ System Architecture & Pipeline

The application follows a sophisticated request-response lifecycle designed for accuracy and efficiency.

```
                                                            User Input
                                                                |
                                                                v
                                                    +-----------------------------+
                                                    |    Flask Backend (@app.py)  |
                                                    |      - Get History from DB  |
                                                    |      - Rewrite Query        |
                                                    +-----------------------------+
                                                                |
                                                                v
                                                    +-----------------------------+
                                                    |  Intent Classification      |
                                                    |   (Mistral, TinyLlama, BERT)|
                                                    +-----------------------------+
                                                                |
                                                                v
     +--------------------------------+-----------------------------------------------------+------------------------------------------+
     | (INTENT1_FAULT_SQL)            | (INTENT2_FAULT_RAG)                                 | (INTENT3_DOMAIN_RAG)                     | (INTENT4_GENERAL_INFO)
     v                                v                                                     v                                          v
+-----------------+            +-----------------------------------------+   +-----------------------------------------+   +-----------------+
|   NL2SQL        |            |   RAG (Fault Info)                      |   |   RAG (Domain Info)                     |   |   General Chat  |
| - Generate SQL  |            | - Retrieve from "FAULT_INFO_COLLECTION" |   | - Retrieve from "DOMAININFO_COLLECTION" |   | - Base LLM      |
| - Execute Query |            +-----------------------------------------+   +-----------------------------------------+   +-----------------+
| - Summarize     |                           |                                          |                           |
+-----------------+                           |                                          |                           |
           |                                  V                                          V                           V
           V

     +---------------------------------------------------------------------------------------------------------------------------------------+
     |                                                     LLM Response Generation (Mistral)                                                 |
     |                                                  - Synthesize results into natural language                                           |
     |                                                  - Stream tokens back to user                                                         |
     +---------------------------------------------------------------------------------------------------------------------------------------+
                                                                         |
                                                                         v
                                                                    +-----------+
                                                                    | User (UI) |
                                                                    +-----------+
```

## 📈 Performance & Monitoring

The system is instrumented to provide performance metrics for each generated response:

  * **Total Tokens Generated:** The number of tokens in the assistant's response.
  * **Total Time:** The end-to-end time taken for the generation.
  * **Tokens/Second:** The throughput of the model generation.
  * **Resource Usage:** CPU and GPU utilization are logged to monitor system load.



  =====================

Yes, a SQL Server developer can find metadata related to a SQL Server database using various system functions and catalog views. Here are a few examples:  1. **Getting database properties:**  ```sql SELECT name, create_date, size, state_desc FROM sys.databases; ```  This query retrieves information about all databases on the SQL Server instance, including their names, creation dates, sizes, and current states.  2. **Listing tables in a specific database:**  ```sql SELECT name FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'YourDatabaseName'; ```  This query retrieves the names of all tables in the specified database.  3. **Checking constraints on a table:**  ```sql SELECT * FROM INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE WHERE TABLE_SCHEMA = 'YourDatabaseName' AND TABLE_NAME = 'YourTableName'; ```  This query retrieves information about all columns that are part of constraints in the specified table.  4. **Viewing stored procedures:**  ```sql SELECT name FROM sys.procedures WHERE is_ms_shipped = 0; ```  This query retrieves the names of all user-defined stored procedures, excluding system-shipped stored procedures.  5. **Finding views:**  ```sql SELECT name FROM sys.views; ```  This query retrieves the names of all views in the current database.  6. **Listing indexes:**  ```sql SELECT i.name AS IndexName, s.name AS TableName, sc.name AS ColumnName FROM sys.indexes AS i INNER JOIN sys.schemas AS s ON i.schema_id = s.schema_id INNER JOIN sys.columns AS sc ON i.object_id = sc.object_id WHERE i.is_primary_key = 0; ```  This query retrieves the names of all non-primary key indexes along with their table and column names.