import requests
import zipfile
import io
import os

def create_test_zip():
    # Create a dummy zip file in memory
    mf = io.BytesIO()
    
    with zipfile.ZipFile(mf, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('test_scam.txt', "Hello, I am calling from your bank security department. We have detected suspicious activity on your account. Please transfer funds to this secure account immediately to protect your money.")
        zf.writestr('test_legit.txt', "Hi, I'm just calling to check if you want to grab lunch later? Let me know.")
    
    return mf.getvalue()

def test_api():
    url = "http://localhost:8000/analyze_risk/"
    zip_content = create_test_zip()
    
    files = {'file': ('test.zip', zip_content, 'application/zip')}
    
    try:
        response = requests.post(url, files=files)
        if response.status_code == 200:
            print("Response:", response.json())
        else:
            print("Error:", response.status_code, response.text)
    except requests.exceptions.ConnectionError:
        print("Could not connect to server. Make sure uvicorn is running.")

if __name__ == "__main__":
    test_api()
