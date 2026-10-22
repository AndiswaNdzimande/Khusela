from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from engine.evaluate import evaluate
from engine.ai_explainer import generate_ai_explanation

app = FastAPI(title="Khusela API")

# Allow the React frontend to talk to the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For hackathon only. Restrict in production.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health_check():
    return {"status": "Khusela API is running"}

@app.post("/api/check")
async def check_payment(
    image: UploadFile = File(...),
    expected_amount: str = Form(...),
    expected_recipient: str = Form(...)
):
    print(f"Received check request for {expected_amount} to {expected_recipient}")
    
    # --- MOCK OCR (Until Nyakallo merges her Tesseract code) ---
    # We deliberately mismatch the amount to test the engine's WAIT/STOP logic
    extracted_data = {
        "amount": "R1,500.00",  # Fake OCR read (Mismatch)
        "recipient": "J. Doe",   # Fake OCR read (Mismatch)
        "ocr_confidence": 0.95
    }

    expected_data = {
        "amount": expected_amount,
        "recipient": expected_recipient
    }

    # 1. Run Ayanda's Deterministic Rule Engine
    verdict_result = evaluate(
        extracted=extracted_data, 
        expected=expected_data, 
        ocr_confidence=extracted_data["ocr_confidence"], 
        dup_result={"found": False} # Mocking no duplicate for now
    )

    # 2. Run Ayanda's Gemini AI Explainer
    ai_text = generate_ai_explanation(verdict_result)
    
    # 3. Attach the AI text and extracted data to the response for the frontend
    verdict_result["explanation"] = ai_text
    verdict_result["extracted_text"] = extracted_data

    return verdict_result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)