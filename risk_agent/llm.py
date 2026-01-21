import google.generativeai as genai
from risk_agent.config import settings
import PIL.Image
import io
import json
from loguru import logger
from groq import Groq
import easyocr

# Initialize the reader once to avoid reloading the model on every request
# gpu=False can be set if no GPU is available, but let's let it auto-detect or default.
# For a generic environment, we might want to wrap this in a try-except or lazy load if it's heavy,
# but the requirement says "Initialize the OCR reader globally".
try:
    reader = easyocr.Reader(['en'])
except Exception as e:
    logger.error(f"Failed to initialize EasyOCR: {e}")
    reader = None

def configure_genai():
    if not settings.GOOGLE_API_KEY:
        # We might not need this for OCR anymore, but keep it for other functions if they use it
        # raise ValueError("GOOGLE_API_KEY is not set...") 
        # The original code raised an error. Let's keep it but it won't be called by extract_text_from_image anymore.
        pass
    if settings.GOOGLE_API_KEY:
        genai.configure(api_key=settings.GOOGLE_API_KEY)

def extract_text_from_image(image_bytes: bytes) -> str:
    """
    Uses local EasyOCR to extract text from images.
    """
    if reader is None:
        logger.error("EasyOCR reader not initialized.")
        return ""
        
    try:
        # EasyOCR supports bytes directly!
        result = reader.readtext(image_bytes, detail=0)
        return " ".join(result)
    except Exception as e:
        logger.error(f"Error in OCR: {e}")
        return ""

def transcribe_audio(audio_bytes: bytes, mime_type: str = "audio/mp3") -> str:
    """
    Uses Groq (Whisper) to transcribe audio files.
    """
    try:
        if not settings.GROQ_API_KEY:
             raise ValueError("GROQ_API_KEY not set")
        
        client = Groq(api_key=settings.GROQ_API_KEY)
        
        # Determine extension from mime_type
        ext = "mp3"
        if "wav" in mime_type: ext = "wav"
        elif "mp4" in mime_type: ext = "mp4"
        elif "ogg" in mime_type: ext = "ogg"

        # Prepare file-like object
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = f"audio.{ext}" # Groq needs a filename to detect format
        
        transcription = client.audio.transcriptions.create(
            file=(audio_file.name, audio_file.read()),
            model="whisper-large-v3",
            response_format="json",
            temperature=0.0
        )
        
        return transcription.text
    except Exception as e:
        logger.error(f"Error in Audio Transcription (Groq): {e}")
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

def analyze_risk_with_groq(user_content: str, similar_cases: list) -> dict:
    """
    Sends the aggregated evidence to Groq (Llama 3) for a final verdict.
    """
    try:
        if not settings.GROQ_API_KEY:
             raise ValueError("GROQ_API_KEY not set")
        
        client = Groq(api_key=settings.GROQ_API_KEY)
        
        # Format similar cases
        similar_cases_str = "\n\n".join([
            f"Case (Risk: {c['risk_label']}, Score: {c['score']:.2f}):\n{c['text_snippet']}" 
            for c in similar_cases
        ])
        
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
        - Provide 3-4 SPECIFIC, ACTIONABLE recommendations for the user to stay safe.
        
        OUTPUT JSON FORMAT ONLY:
        {{
            "probability": <float 0.0 to 1.0>,
            "risk_level": "Low" | "Medium" | "High",
            "analysis": "<detailed explanation citing specific visual, text, or audio red flags>",
            "recommendations": ["<step 1>", "<step 2>", "<step 3>"],
            "sources": ["<refer to specific similar cases if relevant>"]
        }}
        """
        
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that outputs JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        return json.loads(completion.choices[0].message.content)

    except Exception as e:
        logger.error(f"Error in Groq Analysis: {e}")
        return {
             "probability": 0.0,
             "risk_level": "Unknown",
             "analysis": f"Groq reasoning failed: {e}",
             "recommendations": [],
             "sources": []
        }

def analyze_risk_evidence(user_content: str, similar_cases: list) -> dict:
    """
    Dispatches the analysis to the configured LLM provider.
    """
    provider = settings.LLM_PROVIDER
    if provider == "groq":
        logger.info("Using Groq for Risk Analysis")
        return analyze_risk_with_groq(user_content, similar_cases)
    else:
        logger.info("Using Gemini for Risk Analysis")
        return analyze_risk_with_gemini(user_content, similar_cases)
