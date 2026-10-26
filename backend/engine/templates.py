# backend/engine/templates.py

TEMPLATES = {
    "MATCH": "The visible details match your expected sale. However, you must confirm the funds are in your banking app before releasing goods.",
    "WAIT_AMOUNT": "The amount visible on the screenshot does not match your expected sale. Do not release goods. Verify in your banking app.",
    "WAIT_NAME": "The recipient name on the screenshot does not match your business name. Verify in your banking app.",
    "STOP_DUPLICATE": "This exact screenshot has been linked to another account. Do not release goods. Verify the funds in your bank app.",
    "STOP_UNREADABLE": "The image is too blurry to verify. Ask the buyer for a clear, original screenshot.",
    "STUB_MODE": "This is a stub explanation. Please verify funds in your bank app."
}

def get_template(reason_code: str) -> str:
    """
    TASK-12: Returns a deterministic explanation string based on the verdict.
    """
    return TEMPLATES.get(reason_code, "Verify the funds in your banking app before releasing goods.")