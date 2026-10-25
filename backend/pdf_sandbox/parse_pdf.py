"""
TASK-27: PDF parser that runs inside the Docker sandbox.
Reads raw PDF bytes from stdin, writes JSON to stdout.
Exit 0  → success  (JSON with "text" key)
Exit 1  → parse error  (JSON with "error" key)
"""
import json
import sys
import io

try:
    from pdfminer.high_level import extract_text
    from pdfminer.pdfparser import PDFSyntaxError

    raw = sys.stdin.buffer.read()
    if not raw:
        print(json.dumps({"error": "empty input"}))
        sys.exit(1)

    try:
        text = extract_text(io.BytesIO(raw))
        print(json.dumps({"text": text or ""}))
        sys.exit(0)
    except (PDFSyntaxError, Exception) as exc:
        print(json.dumps({"error": f"parse failed: {exc}"}))
        sys.exit(1)

except Exception as exc:
    print(json.dumps({"error": f"startup failed: {exc}"}))
    sys.exit(1)
