from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import PlainTextResponse

router = APIRouter()

# This is the verification endpoint Meta uses to check your webhook
@router.get("/webhook")
async def verify_whatsapp(request: Request):
    params = request.query_params
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == "khusela_secret_token":
        return PlainTextResponse(content=params.get("hub.challenge"))
    raise HTTPException(status_code=403, detail="Invalid verification token")

# This is where Meta sends incoming messages
@router.post("/webhook")
async def receive_whatsapp(request: Request):
    data = await request.json()
    
    # Logic to extract the image URL and phone number goes here
    # For the hackathon, we can log it and return a 200 OK
    print("Incoming WhatsApp Message:", data)
    
    # In the final version, you would:
    # 1. Download the image
    # 2. Pass it to the engine (evaluate)
    # 3. Send a POST request back to Meta to reply with the verdict
    
    return {"status": "success"}