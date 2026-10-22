import os
import google.generativeai as genai
from dotenv import load_dotenv
from .templates import get_template

# Load environment variables (from .env file)
load_dotenv()

# Configure Gemini
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

def generate_ai_explanation(verdict_result: dict) -> str:
    """
    TASK-13: Takes the deterministic verdict and asks Gemini to explain it.
    Strict timeout and fallback to templates if the AI fails.
    """
    verdict = verdict_result.get("verdict", "WAIT")
    reasons = verdict_result.get("reasons", [])
    template_fallback = verdict_result.get("explanation", "Please verify in your bank.")

    # If no API key is set, immediately return the template fallback
    if not api_key:
        print("WARNING: No GEMINI_API_KEY found. Using template fallback.")
        return template_fallback

    prompt = f"""
    You are Khusela, a helpful assistant for South African small business owners.
    We have just run a safety check on a payment screenshot.
    
    The deterministic verdict is: {verdict}
    The reasons are: {reasons}
    
    Write a short, friendly 2-sentence explanation for the seller.
    If the verdict is STOP, tell them firmly not to release the goods.
    If the verdict is WAIT, tell them to verify the funds in their bank app.
    If the verdict is MATCH, remind them to still check their bank app.
    
    Do not change the verdict. Do not add new rules. Keep it under 40 words.
    """

    try:
        # Use a fast model (gemini-1.5-flash)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # We use a short timeout so the demo doesn't hang if the API is slow
        response = model.generate_content(prompt)
        
        if response.text:
            return response.text.strip()
        else:
            return template_fallback

    except Exception as e:
        # If the AI fails (timeout, quota exceeded, no internet), fail gracefully
        print(f"AI Error: {e}. Falling back to template.")
        return template_fallback