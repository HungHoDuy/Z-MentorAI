import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv
from google.cloud import firestore_admin_v1

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

def main():
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "z-mentorai")
    client = firestore_admin_v1.FirestoreAdminClient()
    
    # Define index paths
    index1 = f"projects/{project_id}/databases/(default)/collectionGroups/learning_material/indexes/CICAgJim14AJ"
    index2 = f"projects/{project_id}/databases/(default)/collectionGroups/learning_material/indexes/CICAgJim14AK"
    
    for idx_name in [index1, index2]:
        print(f"Requesting deletion of index: {idx_name}...")
        try:
            client.delete_index(name=idx_name)
            print("Successfully deleted!")
        except Exception as e:
            print(f"Failed to delete index: {e}")

if __name__ == "__main__":
    main()
