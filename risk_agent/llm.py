import google.generativeai as genai
from risk_agent.config import settings
import PIL.Image
import io
import json
from loguru import logger

def configure_genai():
    if not settings.GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY is not set in environment variables.")
    genai.configure(api_key=settings.GOOGLE_API_KEY)

def extract_text_from_image(image_bytes: bytes) -> str:
    """
    Uses Gemini Vision (Flash) to OCR text from images.
    """
    try:
        configure_genai()
        model = genai.GenerativeModel('gemini-2.0-flash')
        image = PIL.Image.open(io.BytesIO(image_bytes))
        response = model.generate_content(["Please transcribe all text from this image exactly as it appears. Output only the text.", image])
        return response.text
    except Exception as e:
        logger.error(f"Error in OCR: {e}")
        return ""

def transcribe_audio(audio_bytes: bytes, mime_type: str = "audio/mp3") -> str:
    """
    Uses Gemini 2.0 Flash to transcribe audio files.
    """
    try:
        configure_genai()
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Pass audio bytes directly to the prompt
        # Note: Gemini 1.5/2.0 supports bytes for audio parts
        response = model.generate_content([
            "Please transcribe this audio file exactly as spoken.",
            {"mime_type": mime_type, "data": audio_bytes}
        ])
        return response.text
    except Exception as e:
        logger.error(f"Error in Audio Transcription: {e}")
        return f"[Error in Transcription: {e}]"

def analyze_risk_with_gemini(user_content: str, similar_cases: list) -> dict:
    """
    Sends the aggregated evidence (Visual + Text + Audio) to Gemini for a final verdict.
    """
    try:
        configure_genai()
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Format similar cases from Qdrant for the LLM context
        similar_cases_str = "\n\n".join([
            f"Case (Risk: {c['risk_label']}, Score: {c['score']:.2f}):\n{c['text_snippet']}" 
            for c in similar_cases
        ])
        
        # --- PROMPT ENGINEERING ---
        prompt = f"""
        You are a generic but highly specialized Risk Analysis Agent for financial scams.
        You have access to MULTIMODAL evidence:
        1. VISUAL EVIDENCE: Descriptions of screenshots (e.g., "Fake Crypto Dashboard detected").
        2. TEXTUAL EVIDENCE: Chat logs or text extracted from images.
        3. AUDIO EVIDENCE: Transcripts of voice messages or calls.

        --------------------------------------------------
        USER SUBMISSION (EVIDENCE):
        {user_content}
        --------------------------------------------------

        SIMILAR KNOWN SCAM PATTERNS (From Database):
        {similar_cases_str}
        --------------------------------------------------
        
        TASK:
        Analyze the evidence for signs of a scam.
        - If VISUAL EVIDENCE indicates a "High Risk" or "Fake Dashboard", weight this heavily.
        - If TEXTUAL/AUDIO EVIDENCE matches known "Pig Butchering" or "Tech Support" scripts, flag it.
        - Provide 3-4 SPECIFIC, ACTIONABLE recommendations for the user to stay safe (e.g., "Block this number", "Do not transfer crypto", "Report to local authorities").
        
        OUTPUT JSON FORMAT ONLY:
        {{
            "probability": <float 0.0 to 1.0>,
            "risk_level": "Low" | "Medium" | "High",
            "analysis": "<detailed explanation citing specific visual, text, or audio red flags>",
            "recommendations": ["<step 1>", "<step 2>", "<step 3>"],
            "sources": ["<refer to specific similar cases if relevant>"]
        }}
        """
        
        response = model.generate_content(prompt)
        
        # Cleaning the response to ensure valid JSON
        text = response.text.replace("```json", "").replace("```", "").strip()
        
        return json.loads(text)

    except Exception as e:
        logger.error(f"Error in Gemini Analysis: {e}")
        # Fallback response if LLM fails
        return {
            "probability": 0.0,
            "risk_level": "Unknown",
            "analysis": f"AI reasoning failed: {e}. Rely on raw visual/text matches.",
            "recommendations": ["Ensure you are using official apps/websites only.", "Never share your private keys or OTP with anyone.", "If you suspect a scam, stop all communication immediately."],
            "sources": []
        }
