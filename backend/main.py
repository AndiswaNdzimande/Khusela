import hmac
import os

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from integration import UploadRejected, check_payment, reset_fingerprints
from ocr import OcrUnavailableError

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


async def _check(image, expected_amount, expected_recipient, expected_reference, seller_id):
    image_bytes = await image.read()
    try:
        # OCR is slow and blocking, so keep it off the event loop.
        return await run_in_threadpool(
            check_payment,
            image_bytes,
            expected_amount=expected_amount,
            expected_recipient=expected_recipient,
            expected_reference=expected_reference,
            seller_id=seller_id,
        )
    except UploadRejected as exc:
        return JSONResponse(status_code=400, content={"error": exc.code, "message": exc.message})
    except OcrUnavailableError:
        return JSONResponse(
            status_code=503,
            content={"error": "ocr_unavailable",
                     "message": "Text reading is not available. Run scripts/setup_ocr.ps1."},
        )


# Both paths work: the guide says /check, interfaces.md says /api/check.
@app.post("/api/check")
@app.post("/check")
async def check_endpoint(
    image: UploadFile = File(...),
    expected_amount: str = Form(...),
    expected_recipient: str = Form(...),
    expected_reference: str = Form(""),
    seller_id: str = Form("demo_seller"),  # replaced by the login token once TASK-23 exists
):
    return await _check(image, expected_amount, expected_recipient, expected_reference, seller_id)


@app.post("/api/demo/reset")
def demo_reset(x_demo_key: str = Header(default="")):
    """Forget every stored screenshot fingerprint (demo and testing only).

    Locked: the endpoint does not exist (404) unless KHUSELA_DEMO_KEY is set,
    and then the caller must send the same value in the X-Demo-Key header.
    """
    expected = os.getenv("KHUSELA_DEMO_KEY", "")
    if not expected:
        raise HTTPException(status_code=404, detail="Not found")
    if not hmac.compare_digest(x_demo_key.encode(), expected.encode()):
        raise HTTPException(status_code=403, detail="Forbidden")
    reset_fingerprints()
    return {"status": "fingerprints cleared"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
