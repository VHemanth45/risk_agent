from pathlib import Path
import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
import openai

# Paths
PROJ_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJ_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

# Load environment variables from .env file
load_dotenv()

class Settings:
    """
    Application configuration settings.
    Handles logic for switching between Cloud and Local Qdrant instances.
    """
    def __init__(self):
        # 1. Load Toggle
        # Default to True not to break if env var is missing, but can be set to False
        self.USE_CLOUD = os.getenv("USE_CLOUD", "True").lower() == "true"
        
        # 2. Qdrant Setup
        if self.USE_CLOUD:
            print("🔧 Configuration: Using Qdrant CLOUD Mode")
            self.QDRANT_URL = os.getenv("QDRANT_CLOUD_URL")
            self.QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
            
            if not self.QDRANT_URL or not self.QDRANT_API_KEY:
                raise ValueError("❌ Error: QDRANT_CLOUD_URL and QDRANT_API_KEY must be set in .env when USE_CLOUD=True")
                
            self.qdrant_client = QdrantClient(
                url=self.QDRANT_URL,
                api_key=self.QDRANT_API_KEY,
            )
        else:
            print("🔧 Configuration: Using Qdrant LOCAL Mode")
            # Ensure the local directory exists or will be created by QdrantClient
            local_path = "./local_qdrant_db"
            self.qdrant_client = QdrantClient(path=local_path)

        # 3. OpenAI Setup
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        if not self.OPENAI_API_KEY:
             # Warning only, as some parts might work without it (e.g. pure vector retrieval if embeddings are pre-calculated, though unlikely)
             print("⚠️ Warning: OPENAI_API_KEY not found in .env")
        else:
            openai.api_key = self.OPENAI_API_KEY

        # 4. Google Gemini Setup
        self.GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
        if not self.GOOGLE_API_KEY:
            print("⚠️ Warning: GOOGLE_API_KEY not found in .env")


    def get_qdrant_client(self):
        return self.qdrant_client

# Instantiate a global settings object
try:
    settings = Settings()
    qdrant_client = settings.get_qdrant_client()
except Exception as e:
    print(f"Failed to initialize configuration: {e}")
    raise

def get_client():
    """Returns the initialized QdrantClient instance."""
    return qdrant_client
