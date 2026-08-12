from google import genai
from config import settings

print("API key loaded:", bool(settings.gemini_api_key))
print("Model:", settings.gemini_model)

client = genai.Client(
    api_key=settings.gemini_api_key
)

response = client.models.generate_content(
    model=settings.gemini_model,
    contents="What is 2 + 2?"
)

print("Response:")
print(response.text)