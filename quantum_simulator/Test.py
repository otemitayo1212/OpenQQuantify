import os
import json
import requests
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()

# Step 1: Read your data.json
DATA_FILE = "data.json"
try:
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        payload = json.load(f)
    print(f"✅ Loaded payload from {DATA_FILE}")
except Exception as e:
    print(f"❌ Failed to read {DATA_FILE}: {e}")
    exit(1)

# Step 2: Load API key
API_KEY = os.getenv("OPENROUTER_API_KEY")
if not API_KEY:
    print("❌ Missing OPENROUTER_API_KEY in environment")
    exit(1)

# Step 3: Build request
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "http://localhost",  # Optional
    "X-Title": "Test OpenRouter"
}

print("📡 Sending request to OpenRouter API...")

# Step 4: Send request
try:
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        data=json.dumps(payload),
        timeout=15  # optional: timeout after 15 seconds
    )
    response.raise_for_status()  # Raises HTTPError for bad status codes

    # Step 5: Parse and print response
    data = response.json()
    print("✅ Success! Here's the assistant's response:")
    print(data["choices"][0]["message"]["content"])

except requests.exceptions.HTTPError as http_err:
    print(f"❌ HTTP error: {http_err}")
    print("🔍 Response:", response.text)

except requests.exceptions.RequestException as req_err:
    print(f"❌ Request error: {req_err}")

except Exception as e:
    print(f"❌ Unexpected error: {e}")
