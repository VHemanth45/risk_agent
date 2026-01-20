import os
import numpy as np
from PIL import Image
from sentence_transformers import SentenceTransformer
from risk_agent.config import get_client
from qdrant_client.http import models
from rich.console import Console
from rich.progress import track

console = Console()
client = get_client()

# 1. Collection Name Check (Crucial step from your logs)
# Your logs showed the collection is named 'text_based', NOT 'scam_genome'
COLLECTION_NAME = "text_based" 
TARGET_SIZE = 1024

# 2. Load the SMALL Model (Safe for laptop)
# We use the standard model (512 dims) to avoid RAM crash
console.print("🧠 Loading Standard CLIP Model (Lightweight)...")
model = SentenceTransformer('clip-ViT-B-32')

# 3. Check Connection
try:
    collections = client.get_collections().collections
    exists = any(c.name == COLLECTION_NAME for c in collections)
    
    if not exists:
        console.print(f"❌ Error: Collection '{COLLECTION_NAME}' not found!", style="red")
        console.print("Ask your teammate for the exact collection name.")
        exit(1)
    else:
        console.print(f"✅ Found collection: {COLLECTION_NAME}")

except Exception as e:
    console.print(f"❌ Connection Error: {e}")
    exit(1)

# 4. Images Process Logic
IMAGE_DIRS = {
    "scam": "data/images/scam",
    "legit": "data/images/legit"
}

points = []
# Start IDs at 10,000 to avoid clashing with teammate's text data (0-2000)
idx = 10000 

for label, folder_path in IMAGE_DIRS.items():
    if not os.path.exists(folder_path):
        console.print(f"⚠️ Folder not found: {folder_path}", style="yellow")
        continue

    files = [f for f in os.listdir(folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
    
    # Sort files to ensure order is consistent
    files.sort()
    
    for file_name in track(files, description=f"Embedding {label} images..."):
        file_path = os.path.join(folder_path, file_name)
        
        try:
            # A. Load Image
            image = Image.open(file_path)
            
            # B. Generate 512-dim Vector
            vector_512 = model.encode(image)
            
            # C. THE HACK: Pad with Zeros to reach 1024
            # We add 512 zeros to the end to match teammate's schema
            padding = np.zeros(TARGET_SIZE - len(vector_512))
            vector_1024 = np.concatenate([vector_512, padding]).tolist()
            
            # D. Create Payload
            payload = {
                "category": "image_evidence",
                "risk_label": label,  # 'scam' or 'legit'
                "description": f"{label} screenshot: {file_name}",
                "source": "manual_collection",
                "filename": file_name,
                "type": "screenshot"
            }
            
            # E. Add Point
            points.append(models.PointStruct(
                id=idx,
                vector=vector_1024,
                payload=payload
            ))
            idx += 1
            
        except Exception as e:
            console.print(f"❌ Error processing {file_name}: {e}", style="red")

# 5. Upload to Qdrant
if points:
    console.print(f" Uploading {len(points)} image vectors to Cloud...")
    try:
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points
        )
        console.print("✅ Image Ingestion Complete! (Memory Safe Mode)", style="green bold")
    except Exception as e:
        console.print(f"❌ Upload Failed: {e}", style="red")
else:
    console.print(" No valid images found to upload.", style="red")
