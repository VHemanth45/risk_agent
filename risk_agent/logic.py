import numpy as np
from risk_agent.config import get_client
from sentence_transformers import SentenceTransformer
from PIL import Image

# Load Models (Global Load)
# Note: Loading model at module level means it loads when imported. 
# Ensure enough memory or handle lazy loading if app scales.
vision_model = SentenceTransformer('clip-ViT-B-32')

client = get_client()
COLLECTION_NAME = "Scam Genome"
TARGET_SIZE = 1024

def analyze_image_risk(image_file):
    """
    Input: Image file (from API upload) - expects a PIL Image object
    Output: Dictionary with risk_level, score, and analysis.
    """
    try:
        # 1. Image ko Vector mein badlo (512 dims)
        # Note: 'image_file' PIL image honi chahiye
        vector_512 = vision_model.encode(image_file)
        
        # 2. Zero Padding (Hack to match 1024 dims of teammate's DB)
        padding = np.zeros(TARGET_SIZE - len(vector_512))
        query_vector = np.concatenate([vector_512, padding]).tolist()

        # 3. Search in Qdrant
        # Using query_points as search might be deprecated/behaving odd in some versions
        results = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=1,
            with_payload=True
        ).points

        if not results:
            return {
                "risk_level": "Unknown",
                "probability": 0.0,
                "analysis": "No similar image found in database.",
                "source": None
            }

        top_match = results[0]
        label = top_match.payload.get("risk_label")
        score = top_match.score
        filename = top_match.payload.get("filename", "unknown")

        # 4. Decision Logic
        if label == "scam" and score > 0.28:
            return {
                "risk_level": "High", 
                "probability": float(score), 
                "analysis": f"CRITICAL: Visual similarity to known scam evidence ({filename}). Do not trust this screenshot.",
                "source": top_match.payload
            }
        elif label == "legit":
            return {
                "risk_level": "Low", 
                "probability": float(score), 
                "analysis": "Verified: Matches interface of official/legit applications.",
                "source": top_match.payload
            }
        else:
            return {
                "risk_level": "Medium", 
                "probability": float(score), 
                "analysis": "Suspicious: Image content is unclear but resembles financial charts.",
                "source": top_match.payload
            }

    except Exception as e:
        return {"risk_level": "Error", "analysis": str(e), "source": None}
