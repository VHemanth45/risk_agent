import socket
import os
from urllib.parse import urlparse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# The URL from your .env
url = os.getenv("QDRANT_CLOUD_URL")

if not url:
    print(" Error: QDRANT_CLOUD_URL not found in .env")
    exit(1)

hostname = urlparse(url).hostname

print(f"Testing connectivity to: {hostname}")

try:
    ip = socket.gethostbyname(hostname)
    print(f" SUCCESS! Resolved to IP: {ip}")
except socket.gaierror:
    print(" FAILURE: Could not resolve hostname (DNS Error).")
    print(" SOLUTION: Connect to Mobile Hotspot and try again.")
