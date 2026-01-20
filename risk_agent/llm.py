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
    try:
        configure_genai()
        model = genai.GenerativeModel('gemini-2.0-flash')
        image = PIL.Image.open(io.BytesIO(image_bytes))
        response = model.generate_content(["Please transcribe all text from this image exactly as it appears. output only the text.", image])
        return response.text
    except Exception as e:
        logger.error(f"Error in OCR: {e}")
        return ""

def analyze_risk_with_gemini(user_content: str, similar_cases: list) -> dict:
    try:
        configure_genai()
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        similar_cases_str = "\n\n".join([
            f"Case (Risk: {c['risk_label']}, Score: {c['score']:.2f}):\n{c['text_snippet']}" 
            for c in similar_cases
        ])
        
        prompt = f"""
        You are a specialized Risk Analysis Agent for financial scams.
        
        USER CONTENT:
        {user_content}
        
        SIMILAR KNOWN CASES (from database):
        {similar_cases_str}
        
        TASK:
        Analyze the USER CONTENT for signs of a scam.
        Use the SIMILAR KNOWN CASES as reference points.
        
        OUTPUT JSON FORMAT:
        {{
            "probability": <float 0.0 to 1.0>,
            "risk_level": "Low" | "Medium" | "High",
            "analysis": "<detailed explanation citing specific similarities or red flags>",
            "sources": ["<refer to specific similar cases if relevant>"]
        }}
        Display ONLY the JSON string. Do not use markdown blocks.
        """
        
        response = model.generate_content(prompt)
        text = response.text.replace("```json", "").replace("```", "").strip()
        
        return json.loads(text)
    except Exception as e:
        logger.error(f"Error in Gemini Analysis: {e}")
        # Fallback response
        return {
            "probability": 0.0,
            "risk_level": "Unknown",
            "analysis": f"Failed to analyze logic due to error: {e}",
            "sources": []
        }
