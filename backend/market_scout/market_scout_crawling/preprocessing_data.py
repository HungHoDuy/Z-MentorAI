import pandas as pd
from google.cloud import firestore
db = firestore.Client()
import re
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt

collection_ref = db.collection('careerviet_jobs')
all_docs = collection_ref.stream()
data_for_df = []
for doc in all_docs:
    doc_data = doc.to_dict()
    data_for_df.append(doc_data)

# Step 4: Create a pandas DataFrame
df = pd.DataFrame(data_for_df)

# Step 5: Display the head of the DataFrame
print("Head of the DataFrame:")
df.head()