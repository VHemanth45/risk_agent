from fastapi import FastAPI, UploadFile, File, HTTPException
from risk_agent.config import settings
from risk_agent.features import generate_embeddings
import zipfile
import io
import re
from loguru import logger
from qdrant_client import models

app = FastAPI(title="ScamShield Risk Agent", version="0.1.0")

@app.get("/")
async def root():
    return {"message": "ScamShield Risk Agent is running", "mode": "Cloud" if settings.USE_CLOUD else "Local"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}

from typing import List
from risk_agent.llm import extract_text_from_image

@app.post("/analyze_risk/")
async def analyze_risk(files: List[UploadFile] = File(...)):
    """
    Analyzes uploaded files (Text, Zip, or Image) for financial risk.
    """
    aggregated_text = ""
    valid_filenames = []
    
    try:
        inputs_processed = 0
        
        for file in files:
            content = await file.read()
            filename = file.filename
            
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                logger.info(f"Processing image: {filename}")
                extracted = extract_text_from_image(content)
                if extracted:
                    aggregated_text += f"\n--- Source: {filename} (Image) ---\n{extracted}\n"
                    inputs_processed += 1
            
            elif filename.endswith('.txt'):
                text = content.decode('utf-8', errors='replace')
                if text.strip():
                    aggregated_text += f"\n--- Source: {filename} (Text) ---\n{text.strip()}\n"
                    inputs_processed += 1
            
            else:
                 logger.warning(f"Skipping unsupported file type: {filename}")
            
        if not aggregated_text.strip():
             raise HTTPException(status_code=400, detail="No readable text found in uploaded files.")
             
        # Generate Embeddings (for the whole context or chunks?)
        # For simple mapping, let's embed the whole aggregated text to find broad context, 
        # OR split into chunks if too large. For now, let's try whole text or first 2000 chars for search.
        search_query = aggregated_text[:2000] 
        embeddings, _ = generate_embeddings([search_query])
        query_vector = embeddings[0]
        
        # Query Qdrant
        client = settings.get_qdrant_client()
        collection_name = "text_based"
        
        search_result = client.query_points(
            collection_name=collection_name,
            query=query_vector.tolist(),
            limit=5,
            with_payload=True
        )

        
        similar_cases = []
        for hit in search_result.points:
            similar_cases.append({
                "text_snippet": (hit.payload.get("original_text", "") or "")[:300] + "...",
                "risk_label": hit.payload.get("risk_label", "unknown"),
                "score": float(hit.score),
                "type": hit.payload.get("scam_type", "unknown")
            })
        if not search_result.points:
            logger.warning("No similar vectors found in Qdrant")

        
            
        # Final Analysis with Heuristics (No LLM)
        probability = 0.0
        if similar_cases:
            probability = min(1.0, sum(c["score"] for c in similar_cases) / len(similar_cases))
            
        if similar_cases and probability > 0.6:
            analysis_result = {
                "risk_level": "High",
                "probability": probability,
                "analysis": "Strong similarity to known scam patterns",
                "sources": similar_cases
            }
        else:
            analysis_result = {
                "risk_level": "Low",
                "probability": probability,
                "analysis": "Low similarity to known scam patterns",
                "sources": similar_cases
            }
        
        return {
            "inputs_processed": inputs_processed,
            "analysis": analysis_result,
            "similar_cases_found": similar_cases
        }


    except Exception as e:
        logger.error(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

