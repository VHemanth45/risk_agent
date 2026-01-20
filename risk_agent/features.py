import re
import sys
from pathlib import Path
from loguru import logger
from tqdm import tqdm
import typer
# import pandas as pd # Not strictly needed if we just use lists
from sentence_transformers import SentenceTransformer
from qdrant_client import models

# Ensure project root is in path for imports
PROJ_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJ_ROOT))

from risk_agent.config import PROCESSED_DATA_DIR, RAW_DATA_DIR, settings

app = typer.Typer()

def load_raw_data():
    data = []
    
    # Process Non-Scam (Label: legit) -> Safe Example
    non_scam_path = RAW_DATA_DIR / "English_NonScam.txt"
    if non_scam_path.exists():
        text = non_scam_path.read_text(encoding="utf-8", errors="replace")
        chunks = text.split("\n\n")
        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk: continue
            # Remove leading numbering like "1. ", "309. "
            cleaned = re.sub(r'^\d+\.\s*', '', chunk)
            if cleaned:
                # MATCHING THE IMAGE SCHEMA:
                data.append({
                    "text": cleaned,
                    "category": "ground_truth",
                    "risk_label": "legit",
                    "description": "Safe conversations (Normal banking)"
                })
    else:
        logger.warning(f"File not found: {non_scam_path}")

    # Process Scam (Label: scam) -> Scam Pattern
    scam_path = RAW_DATA_DIR / "English_Scam.txt"
    if scam_path.exists():
        text = scam_path.read_text(encoding="utf-8", errors="replace")
        chunks = text.split("\n\n")
        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk: continue
            cleaned = re.sub(r'^\d+\.\s*', '', chunk)
            if cleaned:
                # MATCHING THE IMAGE SCHEMA:
                data.append({
                    "text": cleaned,
                    "category": "ground_truth",
                    "risk_label": "scam", 
                    "description": "The pre-loaded data (Pig Butchering scripts, etc.)"
                })
    else:
        logger.warning(f"File not found: {scam_path}")
                
    return data

@app.command()
def main(
    collection_name: str = "financial_risk_data",
    model_name: str = "all-MiniLM-L6-v2",
    batch_size: int = 64,
    recreate: bool = False
):
    """
    Load data, generate embeddings, and upsert to Qdrant.
    """
    logger.info("Loading raw data...")
    raw_data = load_raw_data()
    logger.info(f"Total records found: {len(raw_data)}")
    
    if not raw_data:
        logger.error("No data found! Exiting.")
        return

    # Initialize Model
    logger.info(f"Loading embedding model: {model_name}...")
    model = SentenceTransformer(model_name)
    
    texts = [d["text"] for d in raw_data]
    
    logger.info("Generating embeddings (this may take a while)...")
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=batch_size)
    
    # Initialize Qdrant
    client = settings.get_qdrant_client()
    
    # Check collection
    collections = client.get_collections().collections
    exists = any(c.name == collection_name for c in collections)
    
    if not exists or recreate:
        if recreate and exists:
            logger.info(f"Deleting existing collection {collection_name}...")
            client.delete_collection(collection_name)
            
        logger.info(f"Creating collection {collection_name}...")
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=384, # Output size of all-MiniLM-L6-v2
                distance=models.Distance.COSINE
            )
        )
    else:
        logger.info(f"Collection {collection_name} already exists. Appending to it.")

    # Prepare points
    logger.info("Upserting points to Qdrant...")
    points = []
    for idx, (item, vector) in enumerate(zip(raw_data, embeddings)):
        # We can use a simple integer ID or UUID. 
        # Ideally, hash the content for deduplication, but simple int ID for now.
        # If appending, we need to know the offset. 
        # But for this simple script, let's assume valid IDs.
        # Actually Qdrant allows creating points with integer IDs.
        points.append(models.PointStruct(
            id=idx,
            vector=vector.tolist(),
            payload=item
        ))
    
    # Batch upsert
    total_batches = (len(points) + batch_size - 1) // batch_size
    for i in tqdm(range(0, len(points), batch_size), total=total_batches, desc="Upserting"):
        batch = points[i : i + batch_size]
        client.upsert(
            collection_name=collection_name,
            points=batch
        )
        
    logger.success(f"Successfully processed {len(points)} records into collection '{collection_name}'.")

if __name__ == "__main__":
    app()
