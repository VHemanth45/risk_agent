from risk_agent.config import get_client

try:
    client = get_client()
    collections = client.get_collections()
    print("✅ Connection Successful!")
    print(f"Collections found: {collections}")
except Exception as e:
    print(f"❌ Connection Failed: {e}")
