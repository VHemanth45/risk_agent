import numpy as np
from sentence_transformers import SentenceTransformer
from risk_agent.config import get_client

# 1. Setup
client = get_client()
model = SentenceTransformer('clip-ViT-B-32')
COLLECTION_NAME = "text_based"

# 2. Query: Hum "Profit Screenshot" dhoondhna chahte hain
query_text = "Mobile phone showing huge crypto profit green chart"
print(f"🔎 Searching for: '{query_text}'...")

# 3. Create Vector (With Zero Padding)
# Note: Text search ke liye bhi humein same dimension match karni padegi
vector_512 = model.encode(query_text)
padding = np.zeros(1024 - len(vector_512))
query_vector = np.concatenate([vector_512, padding]).tolist()

# 4. Search in Qdrant
print(f"Client methods: {[m for m in dir(client) if 'search' in m or 'query' in m]}")

try:
    results = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=3
    )
except AttributeError:
    print("⚠️ client.search not found, trying query_points...")
    from qdrant_client.http import models
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=3
    ).points

# 5. Show Results
print("\n--- Results ---")
for res in results:
    # Handle both ScoredPoint (search) and PointStruct/Record (query_points might return different objects)
    # query_points returns QueryResponse which has points.
    # Actually client.search returns list of ScoredPoint.
    # client.query_points returns QueryResponse.
    
    payload = res.payload
    score = res.score if hasattr(res, 'score') else 0.0
    if payload.get("type") == "screenshot":
        print(f"📸 Found Image: {payload.get('filename')} | Score: {res.score:.4f}")
        print(f"   Label: {payload.get('risk_label')}")
    else:
        # Handle cases where payload might be None or text key missing
        text_content = payload.get('text', 'No text content') if payload else 'No payload'
        print(f"📄 Found Text: {text_content[:50]}... | Score: {res.score:.4f}")
