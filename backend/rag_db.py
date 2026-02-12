import pandas as pd
from sqlalchemy import create_engine
import re
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
import config
import pyodbc # pyodbc is imported but not directly used by SQLAlchemy, it's the underlying driver
import os

# It's good practice to print available drivers for debugging connection issues
print(pyodbc.drivers())

class FaultbookIngestor:
    """
    Handles the end-to-end process of fetching fault log data from SQL Server,
    preprocessing it, transforming it into documents, and persisting
    these documents as embeddings into a Chroma vector store.
    """

    def __init__(self, db_engine, sql_query: str, persist_directory: str, collection_name: str):
        """
        Initializes the FaultbookIngestor with database connection details and Chroma settings.

        Args:
            db_engine: An SQLAlchemy Engine object for database connection.
            sql_query (str): The SQL query to fetch data from the fault book.
            persist_directory (str): The directory where the Chroma vector store will be persisted.
            collection_name (str): The name of the collection within the Chroma vector store.
        """
        self.engine = db_engine
        self.sql_query = sql_query
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.df = None  # DataFrame will be loaded and preprocessed here
        self.documents = []

        # Initialize HuggingFace embeddings model
        # The 'local_files_only' flag ensures the model is loaded from cache/local path
        # If the model is not found locally, you might need to temporarily remove
        # 'model_kwargs={"local_files_only": True}' for the first run to allow download.
        self.embeddings = HuggingFaceEmbeddings(
            model_name=config.ALLMINILM_EMBEDDER_MODEL_PATH,
            model_kwargs={"local_files_only": True}
        )
        print(f"✅ Embeddings model loaded: {config.ALLMINILM_EMBEDDER_MODEL_PATH}")

    def _fetch_data_from_sql(self):
        """
        Fetches data from the SQL Server using the provided engine and SQL query.
        Stores the fetched data in self.df.
        """
        print("Attempting to fetch data from SQL Server...")
        try:
            # Use engine.connect() to get a connection object, then access its raw DBAPI2 connection
            with self.engine.connect() as connection:
                self.df = pd.read_sql_query(self.sql_query, connection.connection)
            print("✅ Data fetched successfully from SQL Server.")
            print(self.df.head(3)) # Print head for verification
            file_path = os.path.join(config.FAULT_DOC_DIR, "faultbook_data.csv")
            self.df.to_csv(file_path, index=False, encoding='utf-8')
        except Exception as e:
            print(f"❌ Error fetching data from SQL Server: {e}")
            raise # Re-raise the exception to stop the pipeline if data fetching fails

    def _clean_duration(self, duration):
        """
        Cleans and normalizes the fault_duration column.
        Converts various string formats to 'X.X min' and handles 'N/A' values.
        """
        if isinstance(duration, str):
            duration = duration.strip().lower()
            if duration in ['na', 'n/a', 'not available', '']:
                return '0 min'
            match = re.match(r'(\d+)\s*mins?\s*(\d+)\s*secs?', duration)
            if match:
                mins, secs = match.groups()
                total_min = int(mins) + (int(secs) / 60)
                return f"{total_min:.1f} min"
            return duration
        return '0 min'

    def _safe_strip(self, val):
        """
        Safely strips whitespace from string values, handling non-string types.
        """
        try:
            return str(val).strip()
        except Exception:
            return 'N/A'

    def _preprocess_data(self):
        """
        Applies various preprocessing steps to the DataFrame (self.df).
        Includes datetime conversion, duration cleaning, and string stripping.
        """
        if self.df is None:
            print("Error: DataFrame not loaded for preprocessing. Call _fetch_data_from_sql first.")
            return

        print("Starting data preprocessing...")
        # Convert datetime columns
        self.df['fault_time'] = pd.to_datetime(self.df['fault_time'], errors='coerce')
        self.df['log_time'] = pd.to_datetime(self.df['log_time'], errors='coerce')

        # Clean fault_duration
        self.df['fault_duration'] = self.df['fault_duration'].apply(self._clean_duration)

        # Fill any remaining NaN values
        self.df.fillna('N/A', inplace=True)

        # Apply safe_strip to all object (string) columns
        for col in self.df.select_dtypes(include=['object']).columns:
            self.df[col] = self.df[col].apply(self._safe_strip)
        print("✅ Data preprocessing complete.")

    def row_to_chunk(self, row) -> str:
        """
        Converts a single DataFrame row into a formatted text chunk for embedding.
        """
        return f"""
Fault ID: {row['fault_id']}
Fault Time: {row['fault_time']}
System: {row['system_name']}
Device: {row['device_name']}
Description: {row['fault_description']}
Persons Involved: {row['persons_involved']}
Action Taken: {row['action_taken']}
Faulty System: {row['faulty_system']}
Human Error: {row['human_error']}
FDA Entry: {row['fda_entry']}
Logged By: {row['logged_by']}
Log Time: {row['log_time']}
First Observation: {row['first_observation']}
Beam Affected: {row['beam_affected']}
""".strip()

    def prepare_documents(self):
        """
        Transforms the preprocessed DataFrame rows into LangChain Document objects.
        Each document contains the formatted text content and relevant metadata.
        """
        if self.df is None:
            print("Error: DataFrame not available to prepare documents. Ensure data is fetched and preprocessed.")
            return

        print("Preparing documents for ingestion...")
        documents = []
        for _, row in self.df.iterrows():
            content = self.row_to_chunk(row)
            metadata = {
                "fault_id": row['fault_id'],
                "fault_time": str(row['fault_time']), # Convert datetime to string for metadata
                "system_name": row['system_name']
            }
            documents.append(Document(page_content=content, metadata=metadata))
        self.documents = documents
        print(f"✅ {len(self.documents)} documents prepared from DataFrame.")

    def ingest_to_chroma(self):
        """
        Ingests the prepared documents into the Chroma vector store.
        If documents are not yet prepared, it calls prepare_documents first.
        """
        if not self.documents:
            self.prepare_documents()

        if not self.documents:
            print("Error: No documents to ingest into Chroma. Data pipeline might have failed earlier.")
            return None

        print("Ingesting documents into Chroma vector store...")
        vectorstore = Chroma.from_documents(
            documents=self.documents,
            embedding=self.embeddings,
            persist_directory=self.persist_directory,
            collection_name=self.collection_name
        )
        print(f"✅ Chroma vector store created and persisted at: {self.persist_directory}")
        print(f"✅ Collection name used: {self.collection_name}")
        return vectorstore

    def run_ingestion_pipeline(self):
        """
        Orchestrates the entire ingestion pipeline:
        1. Fetches data from SQL.
        2. Preprocesses the data.
        3. Prepares LangChain Document objects.
        4. Ingests documents into Chroma.
        """
        print("\n--- Starting Faultbook Data Ingestion Pipeline ---")
        try:
            # self._fetch_data_from_sql()
            
            # Save to CSV after fetching and before preprocessing, if desired for debugging
            with open(os.path.join(config.FAULT_DOC_DIR,"faultbook_data.csv"), 'r', encoding='utf-8') as f:
                self.df = pd.read_csv(f)
            print("Data loaded from faultbook_data.csv")

            self._preprocess_data()
            self.prepare_documents()
            vectorstore = self.ingest_to_chroma()
            print("--- Ingestion pipeline complete. Vector store is ready for use. ---")
            return vectorstore
        except Exception as e:
            print(f"❌ An error occurred during the ingestion pipeline: {e}")
            return None

# -----------------------------
# 5️⃣ Entry Point for the script

if __name__ == "__main__":
    # Setup logging (assuming config.setup_logging() exists and works)
    config.setup_logging()

    # Define persistence settings for Chroma
    persist_dir = config.CHROMA_DB_DIR
    collection_name = config.FAULT_INFO_COLLECTION

    # Define database connection string and query
    print(f"CONNECTION_STRING: {config.SQLALCHEMY_CONNECTION_STRING}")
    engine = create_engine(config.SQLALCHEMY_CONNECTION_STRING)
    query = 'SELECT * FROM fault_bookv3 ORDER BY fault_id DESC;'

    # Instantiate the FaultbookIngestor
    ingestor = FaultbookIngestor(
        db_engine=engine,
        sql_query=query,
        persist_directory=persist_dir,
        collection_name=collection_name
    )

    # Run the full ingestion pipeline
    vectorstore = ingestor.run_ingestion_pipeline()

    if vectorstore:
        print("\nSuccessfully created/updated Chroma vector store.")
    else:
        print("\nFailed to create/update Chroma vector store. Check logs for errors.")

