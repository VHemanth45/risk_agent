from fastapi import FastAPI, UploadFile, File, HTTPException
from risk_agent.config import settings
from risk_agent.features import generate_embeddings
from risk_agent.llm import extract_text_from_image, analyze_risk_evidence, transcribe_audio
from risk_agent.logic import analyze_image_risk
from PIL import Image
import io
import uuid
from typing import List
from loguru import logger
from qdrant_client.http import models

app = FastAPI(title="ScamShield Risk Agent", version="0.1.0")

HISTORY_COLLECTION = "user_history"

@app.on_event("startup")
async def startup_event():
    """
    Ensure the user_history collection exists for long-term memory.
    """
    client = settings.get_qdrant_client()
    try:
        collections = client.get_collections().collections
        exists = any(c.name == HISTORY_COLLECTION for c in collections)
        
        if not exists:
            logger.info(f"Creating {HISTORY_COLLECTION} collection for Long-term Memory...")
            client.create_collection(
                collection_name=HISTORY_COLLECTION,
                vectors_config=models.VectorParams(
                    size=1024, # Matching our standard layout (CLIP/BGE + padding)
                    distance=models.Distance.COSINE
                )
            )
    except Exception as e:
        logger.error(f"Could not initialize {HISTORY_COLLECTION}: {e}")

@app.get("/")
async def root():
    return {"message": "ScamShield Risk Agent is running", "mode": "Cloud" if settings.USE_CLOUD else "Local"}

@app.post("/analyze_risk/")
async def analyze_risk(files: List[UploadFile] = File(...)):
    aggregated_text = ""
    visual_evidence = []
    memory_context = ""
    
    try:
        inputs_processed = 0
        
        for file in files:
            content = await file.read()
            filename = file.filename
            
            # --- IMAGE PROCESSING ---
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                try:
                    pil_image = Image.open(io.BytesIO(content))
                    visual_result = analyze_image_risk(pil_image)
                    if visual_result["risk_level"] in ["High", "Medium", "Low"]:
                        visual_evidence.append({"filename": filename, "visual_risk": visual_result})
                except Exception as v_err:
                    logger.error(f"Visual fail: {v_err}")

                extracted = extract_text_from_image(content)
                if extracted:
                    aggregated_text += f"\n--- Source: {filename} (Image Text) ---\n{extracted}\n"
                    inputs_processed += 1
            
            # --- AUDIO PROCESSING ---
            elif filename.lower().endswith(('.mp3', '.wav', '.m4a', '.ogg')):
                mime = "audio/mp3"
                if filename.lower().endswith('.wav'): mime = "audio/wav"
                elif filename.lower().endswith('.m4a'): mime = "audio/mp4"
                
                transcript = transcribe_audio(content, mime_type=mime)
                if transcript:
                    aggregated_text += f"\n--- Source: {filename} (Audio Transcript) ---\n{transcript}\n"
                    inputs_processed += 1

            # --- TEXT FILE PROCESSING ---
            elif filename.endswith('.txt'):
                text = content.decode('utf-8', errors='replace')
                if text.strip():
                    aggregated_text += f"\n--- Source: {filename} (Chat Log) ---\n{text.strip()}\n"
                    inputs_processed += 1
            
        # --- PHASE 2: SEARCH GENOME (Public Database) ---
        similar_text_cases = []
        if aggregated_text.strip():
            search_query = aggregated_text[:2000] 
            embeddings, _ = generate_embeddings([search_query])
            query_vector = embeddings[0]
            
            client = settings.get_qdrant_client()
            
            # 1. Search Known Scam Genome (Public)
            search_result = client.query_points(
                collection_name="text_based",
                query=query_vector.tolist(),
                limit=5
            )
            for hit in search_result.points:
                payload = hit.payload or {}
                # Try multiple common keys for text content
                raw_text = (
                    payload.get("original_text") or 
                    payload.get("text") or 
                    payload.get("page_content") or 
                    payload.get("content") or
                    payload.get("description") or
                    "No text content available"
                )
                
                # specific fix: if it's a list (some embeddings do this), join it
                if isinstance(raw_text, list):
                    raw_text = " ".join(str(x) for x in raw_text)
                
                # Clean up whitespace
                clean_text = " ".join(str(raw_text).split())
                
                similar_text_cases.append({
                    "text_snippet": clean_text[:300],
                    "risk_label": payload.get("risk_label", "unknown"),
                    "score": float(hit.score)
                })

            # 2. LONG-TERM MEMORY: Search User History (Private)
            history_result = client.query_points(
                collection_name=HISTORY_COLLECTION,
                query=query_vector.tolist(),
                limit=3,
                score_threshold=0.85 # Only bring back high-confidence matches
            )
            
            if history_result.points:
                memory_context = "PAST USER REPORTS DETECTED:\n"
                for hit in history_result.points:
                    prev_verdict = hit.payload.get('verdict_summary', 'No summary')
                    memory_context += f"- Previously seen on {hit.payload.get('timestamp', 'Unknown date')}. Verdict: {prev_verdict}\n"

        # --- PHASE 3: FINAL REASONING (LLM) ---
        visual_summary = ""
        for item in visual_evidence:
            v = item['visual_risk']
            visual_summary += f"- Image '{item['filename']}' detected as {v['risk_level']} Risk. Analysis: {v['analysis']}\n"

        final_user_content = f"""
        {memory_context if memory_context else ""}

        VISUAL EVIDENCE FOUND:
        {visual_summary if visual_summary else "No specific visual scam patterns detected."}

        TEXTUAL/AUDIO EVIDENCE:
        {aggregated_text if aggregated_text else "No readable text found."}
        """

        llm_analysis = analyze_risk_evidence(final_user_content, similar_text_cases)
        
        # --- PHASE 4: PERSIST TO MEMORY ---
        if aggregated_text.strip():
            try:
                import datetime
                client.upsert(
                    collection_name=HISTORY_COLLECTION,
                    points=[models.PointStruct(
                        id=str(uuid.uuid4()),
                        vector=query_vector.tolist(),
                        payload={
                            "timestamp": datetime.datetime.now().isoformat(),
                            "original_input": aggregated_text[:500],
                            "verdict_summary": f"{llm_analysis['risk_level']} Risk ({llm_analysis['probability']*100:.0f}%)",
                            "recommendations": llm_analysis.get("recommendations", [])
                        }
                    )]
                )
                logger.info("Interaction saved to Long-term Memory.")
            except Exception as e:
                logger.error(f"Memory persistence failed: {e}")
        
        return {
            "inputs_processed": inputs_processed,
            "final_verdict": llm_analysis,
            "detailed_evidence": {
                "visual_analysis": visual_evidence,
                "text_matches": similar_text_cases,
                "aggregated_text": aggregated_text,
                "memory_context": memory_context
            }
        }

    except Exception as e:
        logger.error(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail=str(e))
