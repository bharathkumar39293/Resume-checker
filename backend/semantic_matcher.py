import os
from sentence_transformers import SentenceTransformer
from langchain_community.vectorstores import Chroma
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# Initialize a local SentenceTransformer embedding model
# You can choose different models from https://www.sbert.net/docs/pretrained_models.html
# 'all-MiniLM-L6-v2' is a good balance of size and performance for many tasks.
embeddings_model = SentenceTransformer('all-MiniLM-L6-v2')

# Initialize ChromaDB
# We'll use a simple in-memory client for now. For production, consider persistent storage.
# Or configure a specific directory for ChromaDB to store its data.
CHROMA_PERSIST_DIR = "./chroma_db"
if not os.path.exists(CHROMA_PERSIST_DIR):
    os.makedirs(CHROMA_PERSIST_DIR)

# A simple persistent client. Create a new collection each time for demonstration.
# In a real application, you'd manage collections more carefully.
chroma_client = Chroma(
    persist_directory=CHROMA_PERSIST_DIR, 
    embedding_function=lambda text: embeddings_model.encode(text).tolist() # Wrap with lambda
)

def generate_and_store_embedding(text, doc_id, collection_name="default_collection"):
    # Generate embedding for the text
    # The SentenceTransformer model expects a list of strings, even for a single text
    embedding = embeddings_model.encode([text])[0].tolist()
    
    # Get or create collection
    collection = chroma_client._client.get_or_create_collection(name=collection_name)

    # Store embedding in Chroma
    # ChromaDB expects a list of documents and their corresponding IDs
    collection.add(
        embeddings=[embedding],
        documents=[text],
        metadatas=[{"source": doc_id}],
        ids=[doc_id]
    )

def get_embedding(doc_id, collection_name="default_collection"):
    collection = chroma_client._client.get_or_create_collection(name=collection_name)
    results = collection.get(ids=[doc_id], include=['embeddings'])
    if results and results['embeddings']:
        return np.array(results['embeddings'][0])
    return None

def calculate_semantic_fit_score(resume_text, jd_text):
    # Generate and store embeddings (can be optimized to only generate if not exists)
    resume_id = "resume_" + str(hash(resume_text))
    jd_id = "jd_" + str(hash(jd_text))
    
    # Generate and store if not present
    generate_and_store_embedding(resume_text, resume_id)
    generate_and_store_embedding(jd_text, jd_id)
    
    resume_embedding = get_embedding(resume_id)
    jd_embedding = get_embedding(jd_id)
    
    if resume_embedding is None or jd_embedding is None:
        return 0.0
    
    # Reshape for cosine_similarity: expects 2D arrays
    resume_embedding = resume_embedding.reshape(1, -1)
    jd_embedding = jd_embedding.reshape(1, -1)

    # Compute cosine similarity
    similarity = cosine_similarity(resume_embedding, jd_embedding)[0][0]
    
    # Return as percentage, rounded to integer
    return int(similarity * 100)

# No __main__ block needed here as this module is imported by app.py
