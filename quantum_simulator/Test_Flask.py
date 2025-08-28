import requests
import json

API_URL = "http://localhost:5000/api/ask"
API_KEY = "your_api_key_here"  # optional

payload = {
    "prompt": "What is the capital of France?",
    "service_context": "general"
}
headers = {
    "Content-Type": "application/json"
}
def main():
    print("📡 Sending request to Flask API...")

    try:
        response = requests.post(API_URL, json=payload, headers=headers, stream=True)
        print(f"🔁 Status Code: {response.status_code}")
        if response.status_code != 200:
            print("❌ Request failed with error:")
            print(response.text)
            return

        print("✅ Connected. Streaming response:\n")
        for line in response.iter_lines():
            if line:
                decoded = line.decode("utf-8").replace("data: ", "")
                try:
                    json_obj = json.loads(decoded)
                    print(json_obj.get("delta") or json_obj.get("event") or json_obj)
                except json.JSONDecodeError:
                    print(f"(Non-JSON Line): {decoded}")
    except Exception as e:
        print("❌ Error while testing Flask endpoint:", e)

if __name__ == "__main__":
    main()
