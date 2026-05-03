import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    print("GROQ_API_KEY not found in .env")
else:
    client = Groq(
        api_key=api_key,
    )
    try:
        print("Testing Groq with Native SDK (client.chat.completions.create)...")
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": "Say hello and confirm you are working."}]
        )
        print(f"Response: {response.choices[0].message.content}")
    except Exception as e:
        print(f"Error: {e}")
