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
    
    print(f"Listing indexes for collection: {collection_group}")
    try:
        request = firestore_admin_v1.ListIndexesRequest(parent=parent)
        page_result = client.list_indexes(request=request)
        for index in page_result:
            print("=" * 40)
            print(f"Name: {index.name}")
            print(f"Query Scope: {index.query_scope}")
            print(f"State: {index.state}")
            print("Fields:")
            for field in index.fields:
                field_path = field.field_path
                mode = ""
                if field.order:
                    mode = f"order: {field.order.name}"
                elif field.array_config:
                    mode = f"array_config: {field.array_config.name}"
                elif field.vector_config:
                    mode = f"vector_config: dimension={field.vector_config.dimension}"
                print(f"  - {field_path} ({mode})")
    except Exception as e:
        print(f"Failed to list indexes: {e}")

if __name__ == "__main__":
    main()
