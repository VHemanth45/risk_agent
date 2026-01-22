# 🛡️ ScamShield Risk Agent

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109%2B-green)
![Qdrant](https://img.shields.io/badge/Qdrant-Vector%20DB-red)
![Groq](https://img.shields.io/badge/Groq-Llama3%20%26%20Whisper-orange)
![License](https://img.shields.io/badge/License-MIT-purple)

**ScamShield Risk Agent** is a state-of-the-art **Multimodal Financial Fraud Detection System**. It combines **Computer Vision (OCR)**, **Audio Transcription**, **Vector Search (RAG)**, and **Large Language Models (LLMs)** to analyze user-uploaded evidence (images, audio, text) and detect potential scams in real-time.

<div align="center">
  <img src="assets/demo_screenshot_1.png" alt="ScamShield CLI Demo 1" width="100%">
  <br>
  <img src="assets/demo_screenshot_2.png" alt="ScamShield CLI Demo 2" width="100%">
</div>


---

## 🚀 Key Features

*   **Multimodal Analysis**:
    *   📸 **Images**: Detects fake crypto dashboards and extracts text using **Google Gemini 2.0 Flash**.
    *   🎙️ **Audio**: Transcribes voice messages/calls using **Google Gemini 2.0 Flash**.
    *   💬 **Text**: Analyzes chat logs and emails.
*   **Vector Search (RAG)**:
    *   Uses **Qdrant** to search a public "Scam Genome" database for known scam scripts (e.g., Pig Butchering, Tech Support scams).
    *   Maintains a private **Long-term Memory** of user history to detect recurring threats.
*   **Advanced Reasoning**:
    *   Powered by **Google Gemini 2.0 Flash** or **Groq (Llama 3)** to provide a final verdict with actionable recommendations.
*   **Rich CLI**: A beautiful, interactive command-line interface for easy testing.
*   **REST API**: Built with **FastAPI** for scalable integration.

---

## 🛠️ Tech Stack

*   **Core**: Python 3.10+
*   **API**: FastAPI, Uvicorn
*   **Vector Database**: Qdrant (Local or Cloud)
*   **LLM & Multimodal**: Google Gemini 2.0 Flash (OCR, Transcription, Analysis)
*   **Embeddings**: CLIP / BGE (via SentenceTransformers)
*   **Vector Database**: Qdrant (Local or Cloud)
*   **CLI**: Rich

---

## 📋 Prerequisites

Ensure you have the following installed:

*   **Python 3.10** or higher
*   **Make** (optional, for convenience commands)
*   **Qdrant** (Docker container or Cloud API Key)

---

## ⚙️ Installation

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/YourUsername/risk_agent.git
    cd risk_agent
    ```

2.  **Set up Virtual Environment**
    We use `uv` for fast dependency management, but standard `pip` works too.
    ```bash
    # Using Make
    make create_environment
    source .venv/bin/activate
    
    # OR Manual
    python3 -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```

3.  **Install Dependencies**
    ```bash
    # Using Make
    make requirements
    
    # OR Manual
    pip install -r requirements.txt
    ```

4.  **Download/Initialize Data**
    (Optional) If you have the raw data files (`English_Scam.txt`, etc.) in `data/raw/`, you can initialize the vector database:
    ```bash
    python -m risk_agent.features --recreate
    ```

    *   **Image Data** (Scam Screenshots):
        If you have images in `data/images/scam` and `data/images/legit`, run:
        ```bash
        python -m risk_agent.ingest_images
        ```

---

## 🔐 Configuration

### 1. Set up Qdrant Cloud (Recommended)
If you want to use a cloud vector database (easier setup):
1.  Sign up at [Qdrant Cloud](https://cloud.qdrant.io/).
2.  Create a **Free Tier Cluster**.
3.  Go to **Data Access Control** and generate an API Key.
4.  Copy the **Cluster URL** and **API Key**.

### 2. Environment Variables
Create a `.env` file in the root directory. Copy the structure below and fill in your API keys:

```ini
# .env

# --- Qdrant Setup ---
# Set to True to use Qdrant Cloud, False to use local container/file
USE_CLOUD=False
QDRANT_CLOUD_URL=https://your-cluster-url.qdrant.tech
QDRANT_API_KEY=your_qdrant_api_key

# --- LLM Provider Settings ---
# Options: "gemini" or "groq"
LLM_PROVIDER=gemini

# --- API Keys ---
# Required if using Gemini
GOOGLE_API_KEY=your_google_gemini_key

# Optional (if using OpenAI models in future)
OPENAI_API_KEY=sk-...
```

---

## 🏃 Usage

You need two terminals to run the system end-to-end.

### 1. Start the API Server
The backend handles file processing, OCR, transcription, and vector search.

```bash
# Run with Uvicorn (Auto-reload enabled)
uvicorn risk_agent.main:app --reload --port 8000
```
_You should see "Application startup complete" in the logs._

### 2. Run the CLI Application
The CLI acts as a client to send files to the server and display results.

```bash
python run_cli.py
```

### 3. Interact
*   Follow the prompts in the CLI.
*   Enter paths to your evidence files (images, audio, or text).
    *   Example: `/path/to/screenshot.png, /path/to/voice_note.mp3`
*   View the detailed Risk Report and Recommendations.

---

Run the included verification scripts to ensure subsystems are working:

*   **Run Unit Tests**:
    ```bash
    pytest tests/
    ```

---

## 📁 Project Structure

```
risk_agent/
├── data/                   # Data storage
│   ├── raw/                # Raw scam datasets
│   └── processed/          # Processed artifacts
├── risk_agent/             # Source Code
│   ├── main.py             # FastAPI entry point
│   ├── llm.py              # LLM, OCR, and Transcription logic
│   ├── features.py         # Embedding generation & Qdrant ingestion
│   ├── config.py           # Configuration management
│   ├── logic.py            # Logical rules
│   └── ...
├── run_cli.py              # CLI Entry point
├── requirements.txt        # Python dependencies
├── Makefile                # Shortcut commands
└── README.md               # Documentation
```
