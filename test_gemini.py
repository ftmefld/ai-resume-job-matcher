import os

from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

models_to_try = [
    "gemini-3.8-flash",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
]

for model_name in models_to_try:
    try:
        print(f"Trying {model_name}...")

        response = client.models.generate_content(
            model=model_name,
            contents="Reply with exactly: Gemini connection works"
        )

        print(response.text)
        print(f"Success with {model_name}")
        break

    except Exception as error:
        print(f"{model_name} failed:")
        print(error)