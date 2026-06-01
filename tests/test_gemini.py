import os
import sys
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.gemini_provider import GeminiProvider

def test_gemini():
    load_dotenv()
    
    # Retrieve Gemini API settings
    api_key = os.getenv("GEMINI_API_KEY")
    model_name = os.getenv("DEFAULT_MODEL", "gemini-2.0-flash")
    if not model_name.startswith("gemini") or model_name == "gemini-1.5-flash":
        model_name = "gemini-2.0-flash"


    
    print(f"--- Testing Gemini Provider ---")
    print(f"Model Name: {model_name}")
    
    if not api_key or api_key == "your_gemini_api_key_here":
        print("❌ Error: GEMINI_API_KEY is not set or has placeholder value in your .env file.")
        print("Please replace it with a valid Gemini API Key from Google AI Studio.")
        return

    try:
        provider = GeminiProvider(model_name=model_name, api_key=api_key)
        
        prompt = "Explain what an AI Agent is in one sentence."
        print(f"\nUser: {prompt}")
        print("Assistant: ", end="", flush=True)
        
        for chunk in provider.stream(prompt):
            print(chunk, end="", flush=True)
        print("\n\n✅ Gemini Provider is working correctly!")
        
    except Exception as e:
        print(f"\n❌ Error during execution: {e}")

if __name__ == "__main__":
    test_gemini()
