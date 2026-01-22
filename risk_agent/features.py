import re
import sys
from pathlib import Path
from loguru import logger
from tqdm import tqdm
import typer
# import pandas as pd # Not strictly needed if we just use lists
from sentence_transformers import SentenceTransformer
from qdrant_client import models
from datasets import load_dataset

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
                # Prepend metadata to the text being embedded for consistency
                # Since these are local files, we assign default "type" and "personality"
                scam_type = "legit_banking"
                personality = "unknown"
                
                embedded_text = f"Type: {scam_type}\nPersonality: {personality}\nDialogue:\n{cleaned}"

                data.append({
                    "text": embedded_text, # Embed the structured text
                    "original_text": cleaned,
                    "category": "ground_truth",
                    "risk_label": "legit",
                    "scam_type": scam_type,
                    "personality": personality,
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
                # Known scam scripts
                scam_type = "scam_scripts"
                personality = "unknown"
                
                embedded_text = f"Type: {scam_type}\nPersonality: {personality}\nDialogue:\n{cleaned}"
                
                data.append({
                    "text": embedded_text,
                    "original_text": cleaned,
                    "category": "ground_truth",
                    "risk_label": "scam", 
                    "scam_type": scam_type,
                    "personality": personality,
                    "description": "The pre-loaded data (Pig Butchering scripts, etc.)"
                })
    else:
        logger.warning(f"File not found: {scam_path}")

    # Process Hugging Face Dataset: BothBosu/multi-agent-scam-conversation
    try:
        logger.info("Loading Hugging Face dataset: BothBosu/multi-agent-scam-conversation")
        # Load the dataset (assuming 'train' split if not specified, but explicit is better)
        hf_dataset = load_dataset("BothBosu/multi-agent-scam-conversation", split="train")
        
        for item in hf_dataset:
            # item keys based on image: 'dialogue', 'type', 'labels', 'personality'
            try:
                raw_text = item.get("dialogue", "")
                if not raw_text.strip():
                    continue

                # Image shows 'labels' (plural)
                label_val = item.get("labels") 
                # 0 -> legit, 1 -> scam
                risk_label = "scam" if label_val == 1 else "legit"
                
                scam_type = item.get("type", "unknown")
                personality = item.get("personality", "unknown")
                
                # Construct text for embedding utilizing metadata
                embedded_text = f"Type: {scam_type}\nPersonality: {personality}\nDialogue:\n{raw_text}"
                
                data.append({
                    "text": embedded_text,
                    "original_text": raw_text,
                    "category": "hf_dataset",
                    "risk_label": risk_label,
                    "scam_type": scam_type,
                    "personality": personality,
                    "description": f"Source: BothBosu/multi-agent-scam-conversation, Type: {scam_type}"
                })
            except Exception as e:
                logger.warning(f"Skipping an item due to error: {e}")
                
    except Exception as e:
        logger.error(f"Failed to load HF dataset: {e}")
                
    return data

def generate_embeddings(texts, model_name="BAAI/bge-large-en-v1.5", max_seq_length=512, batch_size=32):
    """
    Generate embeddings for a list of texts using the specified model.
    """
    logger.info(f"Loading embedding model: {model_name}...")
    model = SentenceTransformer(model_name)
    model.max_seq_length = max_seq_length
    logger.info(f"Model sequence length set to: {max_seq_length}")
    logger.info(f"Model loaded on device: {model.device}")
    
    logger.info(f"Generating embeddings (Batch Size: {batch_size})...")
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=batch_size)
    return embeddings, model.get_sentence_embedding_dimension()

@app.command()
def main(
    collection_name: str = "text_based",
    model_name: str = "BAAI/bge-large-en-v1.5",
    batch_size: int = 32,
    recreate: bool = False,
    max_seq_length: int = 512
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

    texts = [d["text"] for d in raw_data]
    
    # Generate Embeddings
    embeddings, embedding_dim = generate_embeddings(texts, model_name, max_seq_length, batch_size)
    
    # Initialize Qdrant
    client = settings.get_qdrant_client()
    
    # Check collection
    collections = client.get_collections().collections
    exists = any(c.name == collection_name for c in collections)

    
    if not exists or recreate:
        if recreate and exists:
            logger.info(f"Deleting existing collection {collection_name}...")
            client.delete_collection(collection_name)
            
        logger.info(f"Creating collection {collection_name} with dimension {embedding_dim}...")
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=embedding_dim, 
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
