import os
os.environ["CHROMA_TELEMETRY"] = "FALSE"
import logging
import config
import json
from langchain_community.document_loaders import DirectoryLoader, TextLoader, JSONLoader, PyPDFLoader
from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
# from sentence_transformers import SentenceTransformer # Removed unused import
from chromadb.config import Settings
from langchain_chroma import Chroma
# from langchain_community.embeddings import OllamaEmbeddings # Removed unused import
import chromadb # Keep this import for direct client operations if needed, but we'll use it carefully

config.setup_logging()
logger = logging.getLogger(__name__)
logger.info("rag setup logging enabled...")

class RagSetup:
    def __init__(self):
        logger.info("object initialization...")
        self.embedding_model = HuggingFaceEmbeddings(
            model_name = config.ALLMINILM_EMBEDDER_MODEL_PATH,  
            model_kwargs={
                "local_files_only": True
                }
            )

        self.client_settings = Settings(
            is_persistent = True,
            persist_directory = config.CHROMA_DB_DIR,
            anonymized_telemetry = False
        )
        # Initialize the ChromaDB persistent client here
        # This client is used for direct ChromaDB operations like deleting collections
        self.chroma_client = chromadb.PersistentClient(path=self.client_settings.persist_directory, settings=self.client_settings)
        
        logger.info("embedding model and chroma client initialized...")


    def document_loader(self, data_directory):
        documents =[]
        for root, _, files in os.walk(data_directory):
            for file in files:
                file_path = os.path.join(root, file)
                _, file_extension = os.path.splitext(file_path)

                if file_extension == ".txt":
                    try:
                        loader = TextLoader(file_path)
                        documents.extend(loader.load())
                        logger.info(f"Loaded {file_path} with TextLoader")
                        print(f"Loaded {file_path} with TextLoader")
                    except Exception as e:
                        logger.info(f"Error loading {file_path} with Textloader\n{e}")
                        print(f"Error loading {file_path} with Textloader\n{e}")
                elif file_extension == ".pdf":
                    try:
                        loader = PyPDFLoader(file_path)
                        documents.extend(loader.load())
                        logger.info(f"Loaded {file_path} with PyPDFLoader")
                        print(f"Loaded {file_path} with PyPDFLoader")
                    except Exception as e:
                        logger.info(f"Error Loading {file_path} with PyPDFLoader\n{e}")
                        print(f"Error Loading {file_path} with PyPDFLoader\n{e}")
                elif file_extension == ".json":
                    try:
                        loader = JSONLoader(file_path, jq_schema=".", text_content=False)
                        docs = loader.load()
                        formatted_doc = []
                        for doc in docs:
                            metadata = doc.metadata
                            data_str = doc.page_content # Renamed to avoid shadowing
                            
                            try:
                                data = json.loads(data_str)
                                if isinstance(data, list) and data: # Check if it's a non-empty list
                                    item = data[0]
                                    if isinstance(item, dict): # Check if the first item is a dictionary
                                        text = (f"System: {item.get('system', 'N/A')}\n" # Use .get with default
                                                f"Description: {item.get('description', 'N/A')}\n"
                                                f"Severity: {item.get('severity', 'N/A')}\n"
                                                f"Cause: {item.get('cause', 'N/A')}\n"
                                                f"Solution: {item.get('solution', 'N/A')}\n"
                                                )
                                        doc.page_content = text
                                        formatted_doc.append(doc)
                                    else:
                                        logger.warning(f"JSON data in {file_path} does not have expected dictionary structure at index 0.")
                                        print(f"JSON data in {file_path} does not have expected dictionary structure at index 0.")
                                else:
                                    logger.warning(f"JSON data in {file_path} is empty or not a list.")
                                    print(f"JSON data in {file_path} is empty or not a list.")
                            except json.JSONDecodeError as jde:
                                logger.error(f"Error decoding JSON from {file_path}: {jde}")
                                print(f"Error decoding JSON from {file_path}: {jde}")
                            except Exception as inner_e:
                                logger.error(f"Error processing JSON content from {file_path}: {inner_e}")
                                print(f"Error processing JSON content from {file_path}: {inner_e}")

                        documents.extend(formatted_doc)
                        logger.info(f"Loaded {file_path} with JSONLoader")
                        print(f"Loaded {file_path} with JSONLoader")
                    except Exception as e:
                        logger.info(f"Error Loading {file_path} with JSONLoader\n{e}")
                        print(f"Error Loading {file_path} with JSONLoader\n{e}")
                else:
                    logger.info(f"Skippig unsupported files : {file_path}")
                    print(f"Skippig unsupported files : {file_path}")

        logger.info(f"Loaded {len(documents)} documents in total.")
        print(f"Loaded {len(documents)} documents in total.")
        return documents
    
    def chunk_text(self, documents):
        try:
            splitter = RecursiveCharacterTextSplitter(
                chunk_size = config.CHUNK_SIZE,
                chunk_overlap=config.CHUNK_OVERLAP
            )
            chunks = splitter.split_documents(documents)
            logger.info(f"Split into {len(chunks)} chunks")
            print(f"Split into {len(chunks)} chunks")
            return chunks
        except Exception as e:
            logger.info(f"Error splitting text: {e}")
            print(f"Error splitting text: {e}")
            return None

    def embed_and_store(self, chunks, collection_name):
        # Determine the maximum batch size based on ChromaDB's error message (e.g., 5461)
        # Using a slightly lower value to be safe.
        # This value can vary with ChromaDB versions or underlying hardware, so
        # making it a config variable or dynamically querying it might be better
        # for a production system.
        MAX_CHROMA_BATCH_SIZE = 5000 # Using a round number, safely below 5461

        # Use the persistent client to manage collections (e.g., delete)
        try:
            # Attempt to get the collection. If it exists, delete it.
            # This ensures we start fresh if the collection already has data.
            # get_or_create_collection is useful if you want to ensure it exists for deletion.
            collection = self.chroma_client.get_or_create_collection(name=collection_name)
            self.chroma_client.delete_collection(name=collection_name)
            print(f"Cleared existing collection: {collection_name}")
            logger.info(f"Cleared existing collection: {collection_name}")
        except Exception as e:
            # This likely means the collection didn't exist, which is fine for first run.
            print(f"Collection '{collection_name}' does not exist or error deleting (likely harmless if creating first time): {e}")
            logger.warning(f"Collection '{collection_name}' does not exist or error deleting (likely harmless if creating first time): {e}")

        # Initialize the LangChain Chroma wrapper for adding documents
        # This will create the collection if it doesn't exist after deletion
        client_collection = Chroma(
            collection_name=collection_name,
            embedding_function=self.embedding_model,
            persist_directory=config.CHROMA_DB_DIR,
            client_settings=self.client_settings # Pass the same client settings
        )

        # Batch the chunks and add them incrementally
        num_chunks_added = 0
        total_chunks = len(chunks)
        print(f"Starting to add {total_chunks} chunks to collection: {collection_name} in batches.")
        logger.info(f"Starting to add {total_chunks} chunks to collection: {collection_name} in batches.")

        for i in range(0, total_chunks, MAX_CHROMA_BATCH_SIZE):
            batch = chunks[i:i + MAX_CHROMA_BATCH_SIZE]
            try:
                client_collection.add_documents(batch)
                num_chunks_added += len(batch)
                print(f"Added batch {i//MAX_CHROMA_BATCH_SIZE + 1} of {len(batch)} chunks. Total added: {num_chunks_added}/{total_chunks}")
                logger.info(f"Added batch {i//MAX_CHROMA_BATCH_SIZE + 1} of {len(batch)} chunks. Total added: {num_chunks_added}/{total_chunks}")
            except Exception as e:
                print(f"Error adding batch to collection {collection_name} at index {i}: {e}")
                logger.error(f"Error adding batch to collection {collection_name} at index {i}: {e}")
                # You might want to break or raise here if a failed batch is critical
                break # Stop processing further if a batch fails

        print(f"Finished adding {num_chunks_added} chunks in total to collection: {collection_name}")
        logger.info(f"Finished adding {num_chunks_added} chunks in total to collection: {collection_name}")


    def retrieve_from_collection(self, collection_name, user_query, k=3, filters=None):

        client_collection = Chroma(
            collection_name=collection_name,
            embedding_function=self.embedding_model,
            persist_directory=config.CHROMA_DB_DIR,
            client_settings=self.client_settings
        )   

        # It's better to check if the collection actually exists before trying to get its documents
        # The LangChain Chroma wrapper doesn't have a direct "collection exists" method easily accessible,
        # but the underlying chromadb client does.
        try:
            collection_info = self.chroma_client.get_collection(name=collection_name)
            if collection_info.count() == 0: # Use count() for efficiency
                print(f"Collection '{collection_name}' is empty. No retrieval will be performed.")
                logger.info(f"Collection '{collection_name}' is empty. No retrieval will be performed.")
                return "", []
        except Exception as e:
            print(f"Collection '{collection_name}' does not exist. No retrieval will be performed. Error: {e}")
            logger.info(f"Collection '{collection_name}' does not exist. No retrieval will be performed. Error: {e}")
            return "", []


        search_kwargs = {"k":k}
        if filters:
            search_kwargs["filter"] = filters # Pass filters to the retriever

        retriever = client_collection.as_retriever(search_kwargs=search_kwargs)

        results = retriever.invoke(user_query)

        retrieved_docs = [doc.page_content for doc in results]
        retrieved_metadata = [doc.metadata for doc in results]
        context = "\n\n".join(retrieved_docs)
        
        sources = []
        for meta in retrieved_metadata:
            if 'source' in meta:
                sources.append(meta['source'])

        unique_sources_ordered = list(dict.fromkeys(sources))

        if collection_name == config.FAULT_INFO_COLLECTION:
            sources = []
            for meta in retrieved_metadata:
                if 'fault_id' in meta:
                    sources.append(f"Fault ID: {meta['fault_id']}")
            unique_sources_ordered = list(dict.fromkeys(sources))

        return context, unique_sources_ordered

if __name__ == "__main__":
    user_prompt = "What is SRS in Accelerator Physics?"

    obj = RagSetup()
    
    # Process Accelerator Physics documents
    print(f"\n--- Processing {config.ACC_PY_DOC_DIR} ---")
    logger.info(f"--- Processing {config.ACC_PY_DOC_DIR} ---")
    documents_acc = obj.document_loader(config.ACC_PY_DOC_DIR)
    chunks_acc = obj.chunk_text(documents_acc)
    if chunks_acc: # Only attempt to store if chunks were successfully created
        obj.embed_and_store(chunks_acc, config.DOMAININFO_COLLECTION)
    else:
        print(f"No chunks to embed for {config.ACC_PY_DOC_DIR}. Skipping embedding.")
        logger.warning(f"No chunks to embed for {config.ACC_PY_DOC_DIR}. Skipping embedding.")

    # Process DB Schema documents
    print(f"\n--- Processing {config.DB_SCHEMA_DOC_DIR} ---")
    logger.info(f"--- Processing {config.DB_SCHEMA_DOC_DIR} ---")
    documents_db = obj.document_loader(config.DB_SCHEMA_DOC_DIR)
    chunks_db = obj.chunk_text(documents_db)
    if chunks_db: # Only attempt to store if chunks were successfully created
        obj.embed_and_store(chunks_db, config.DBSCHEMA_COLLECTION)
    else:
        print(f"No chunks to embed for {config.DB_SCHEMA_DOC_DIR}. Skipping embedding.")
        logger.warning(f"No chunks to embed for {config.DB_SCHEMA_DOC_DIR}. Skipping embedding.")

    print(f"\n--- Retrieving from {config.DOMAININFO_COLLECTION} ---")
    logger.info(f"--- Retrieving from {config.DOMAININFO_COLLECTION} ---")
    retrieved_docs, retrieved_metadata = obj.retrieve_from_collection(config.DOMAININFO_COLLECTION, user_prompt)
    print(f"Retrieved Documents:\n{retrieved_docs}")
    logger.info(f"Retrieved documents: {retrieved_docs}")
    print(f"Sources: {retrieved_metadata}")
    logger.info(f"Sources: {retrieved_metadata}")