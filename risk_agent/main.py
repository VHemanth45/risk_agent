from fastapi import FastAPI
from risk_agent.config import settings

app = FastAPI(title="ScamShield Risk Agent", version="0.1.0")

@app.get("/")
async def root():
    return {"message": "ScamShield Risk Agent is running", "mode": "Cloud" if settings.USE_CLOUD else "Local"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}
