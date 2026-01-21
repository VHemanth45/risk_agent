import requests
import io
from PIL import Image, ImageDraw, ImageFont

def create_test_image():
    # Create an image with some text
    img = Image.new('RGB', (400, 200), color='white')
    d = ImageDraw.Draw(img)
    # Just basic text, default font
    d.text((10, 10), "Bank Alert: Your account is compromised.", fill=(255, 0, 0))
    d.text((10, 30), "Please wire $5000 to safe account immediately.", fill=(0, 0, 0))
    
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    return img_byte_arr.getvalue()

def test_api():
    url = "http://localhost:8000/analyze_risk/"
    
    # 1. Text File
    text_content = "Mom, I dropped my phone in the toilet. This is my new number. Need money for rent."
    
    # 2. Image File
    image_content = create_test_image()
    
    files = [
        ('files', ('scam_text.txt', text_content, 'text/plain')),
        ('files', ('screenshot.png', image_content, 'image/png'))
    ]
    
    print("Sending request with text and image...")
    try:
        response = requests.post(url, files=files)
        if response.status_code == 200:
            print("\nResponse Status: OK")
            print(response.json())
        else:
            print(f"Error: {response.status_code}")
            print(response.text)
    except requests.exceptions.ConnectionError:
        print("Could not connect. Is uvicorn running?")

if __name__ == "__main__":
    test_api()
