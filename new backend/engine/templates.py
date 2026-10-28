TEMPLATES = {
    "MATCH": (
        "The visible details match your expected sale. Confirm the funds in your "
        "banking app before releasing goods."
    ),
    "WAIT_AMOUNT": (
        "The amount visible on the screenshot does not match your expected sale. "
        "Do not release goods. Verify in your banking app."
    ),
    "WAIT_NAME": (
        "The recipient name on the screenshot does not match your business name. "
        "Verify in your banking app."
    ),
    "WAIT_REFERENCE": (
        "The payment reference does not match your sale. Verify the funds in your bank."
    ),
    "STOP_DUPLICATE": (
        "This exact screenshot has been linked to another account. Do not release goods. "
        "Verify the funds in your bank app."
    ),
    "STOP_UNREADABLE": (
        "The image is too blurry to verify. Ask the buyer for a clear, original screenshot."
    ),
    "OCR_UNAVAILABLE": (
        "Khusela stored the check and fingerprint, but OCR is not configured on this "
        "backend yet. Do not release goods until you confirm the deposit in your banking app."
    ),
}


def get_template(reason_code: str) -> str:
    return TEMPLATES.get(
        reason_code,
        "Verify the funds in your banking app before releasing goods.",
    )
