import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from google.cloud import firestore
from google.cloud.firestore_v1.vector import Vector
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

from langchain_google_vertexai import VertexAIEmbeddings

def main():
    db = firestore.Client()
    col = db.collection("learning_material")
    
    print("Initializing embeddings...")
    embeddings = VertexAIEmbeddings(model_name="text-embedding-004")
    
    query_text = "python programming for beginners"
    print(f"Embedding query: '{query_text}'...")
    query_vector = embeddings.embed_query(query_text)
    
    print(f"Query vector dimensions: {len(query_vector)}")
    
    print("Performing find_nearest vector search on description_embedding...")
    try:
        query = col.find_nearest(
            vector_field="description_embedding",
            query_vector=Vector(query_vector),
            distance_measure=DistanceMeasure.COSINE,
            limit=5,
            distance_result_field="vector_distance"
        )
        
        results = list(query.stream())
        print(f"Found {len(results)} results:")
        for doc in results:
            print(f"- ID: {doc.id}")
            print(f"  Name: {doc.get('name')}")
            print(f"  Distance (Similarity): {doc.get('vector_distance')}")
    except Exception as e:
        print("\nFailed to run native vector search:")
        print(str(e))

if __name__ == "__main__":
    main()
