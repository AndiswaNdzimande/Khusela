import os
from dotenv import load_dotenv
from google import genai

# Load environment variables
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")


def generate_ai_explanation(verdict_result: dict) -> str:
    verdict = verdict_result.get("verdict", "WAIT")
    reasons = verdict_result.get("reasons", [])
    template_fallback = verdict_result.get("explanation", "Please verify in your bank.")

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
        # Use the new Google GenAI client
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        text = response.text.strip()

        # AI GUARDRAIL: If the verdict is STOP/WAIT, the AI must not say "safe" or "paid"
        if verdict != "MATCH":
            bad_words = ["safe to release", "paid", "funds have cleared", "safe"]
            if any(word in text.lower() for word in bad_words):
                print("AI GUARD TRIGGERED: AI hallucinated safety. Falling back to template.")
                return template_fallback

        return text

    except Exception as e:
        print(f"AI Error: {e}. Falling back to template.")
        return template_fallback