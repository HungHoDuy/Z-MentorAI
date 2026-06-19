import subprocess
import json
import time

def run_command(args):
    if args[0] == "gcloud":
        args[0] = "gcloud.cmd"
    print(f"Executing: {' '.join(args)}")
    res = subprocess.run(args, capture_output=True, text=True)
    if res.returncode == 0:
        print("Success!")
        print(res.stdout)
    else:
        print("Failed!")
        print(res.stderr)
    print("-" * 50)

def main():
    project = "z-mentorai"
    collection = "learning_material"
    
    # Define vector configs as dictionaries to avoid escaping issues
    name_vector_config = json.dumps({"dimension": "128", "flat": {}})
    desc_vector_config = json.dumps({"dimension": "768", "flat": {}})
    
    # 1. Single field description embedding index
    run_command([
        "gcloud", "firestore", "indexes", "composite", "create",
        f"--project={project}",
        f"--collection-group={collection}",
        "--query-scope=COLLECTION",
        f"--field-config=vector-config={desc_vector_config},field-path=description_embedding"
    ])
    
    # 2. Single field name embedding index
    run_command([
        "gcloud", "firestore", "indexes", "composite", "create",
        f"--project={project}",
        f"--collection-group={collection}",
        "--query-scope=COLLECTION",
        f"--field-config=vector-config={name_vector_config},field-path=name_embedding"
    ])
    
    # 3. Composite description embedding index with domainIDs filter
    run_command([
        "gcloud", "firestore", "indexes", "composite", "create",
        f"--project={project}",
        f"--collection-group={collection}",
        "--query-scope=COLLECTION",
        "--field-config=field-path=domainIDs,array-config=contains",
        f"--field-config=vector-config={desc_vector_config},field-path=description_embedding"
    ])
    
    # 4. Composite name embedding index with domainIDs filter
    run_command([
        "gcloud", "firestore", "indexes", "composite", "create",
        f"--project={project}",
        f"--collection-group={collection}",
        "--query-scope=COLLECTION",
        "--field-config=field-path=domainIDs,array-config=contains",
        f"--field-config=vector-config={name_vector_config},field-path=name_embedding"
    ])

if __name__ == "__main__":
    main()
