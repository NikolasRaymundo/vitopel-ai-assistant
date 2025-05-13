from dotenv import load_dotenv
import os

load_dotenv()  # This loads your .env file

api_key = os.getenv("OPENAI_API_KEY")

if api_key:
    print("✅ .env loaded successfully!")
else:
    print("❌ .env not loaded or key missing.")
