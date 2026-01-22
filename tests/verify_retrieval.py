import numpy as np
from sentence_transformers import SentenceTransformer
from risk_agent.config import settings
from qdrant_client.http import models

def main():
    print("Testing Qdrant Retrieval...")
    client = settings.get_qdrant_client()
    model = SentenceTransformer('clip-ViT-B-32')
    
    query = "fake crypto dashboard profit"
    print(f"Query: {query}")
    
    # Generate vector
    vector_512 = model.encode(query)
    padding = np.zeros(1024 - len(vector_512))
    query_vector = np.concatenate([vector_512, padding]).tolist()
    
    try:
        results = client.query_points(
            collection_name="Scam Genome",
            query=query_vector,
            limit=3
        ).points
        
        print(f"\nFound {len(results)} matches:")
        for res in results:
            print(f"- [{res.score:.4f}] {res.payload.get('filename', 'No Filename')} | Label: {res.payload.get('risk_label')}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
