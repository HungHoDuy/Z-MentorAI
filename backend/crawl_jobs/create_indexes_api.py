import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from google.cloud import firestore_admin_v1

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

def main():
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "z-mentorai")
    collection_group = "learning_material"
    
    client = firestore_admin_v1.FirestoreAdminClient()
    parent = f"projects/{project_id}/databases/(default)/collectionGroups/{collection_group}"
    
    print(f"Connecting to Firestore Admin API. Project: {project_id}, Collection: {collection_group}")
    
    # 1. Composite Index: domainIDs + description_embedding (768-dim)
    desc_idx = firestore_admin_v1.Index(
        query_scope="COLLECTION",
        fields=[
            {"field_path": "domainIDs", "array_config": "CONTAINS"},
            {"field_path": "description_embedding", "vector_config": {"dimension": 768, "flat": {}}}
        ]
    )
    
    # 2. Composite Index: domainIDs + name_embedding (128-dim)
    name_idx = firestore_admin_v1.Index(
        query_scope="COLLECTION",
        fields=[
            {"field_path": "domainIDs", "array_config": "CONTAINS"},
            {"field_path": "name_embedding", "vector_config": {"dimension": 128, "flat": {}}}
        ]
    )
    
    # Trigger creations
    try:
        print("Registering composite index: domainIDs + description_embedding...")
        op = client.create_index(parent=parent, index=desc_idx)
        print("Index creation request submitted successfully!")
    except Exception as e:
        print(f"Request failed or index already exists: {e}")
        
    try:
        print("Registering composite index: domainIDs + name_embedding...")
        op = client.create_index(parent=parent, index=name_idx)
        print("Index creation request submitted successfully!")
    except Exception as e:
        print(f"Request failed or index already exists: {e}")

if __name__ == "__main__":
    main()
