"""
TASK-27: API-side bridge to the sandboxed PDF parser.
Spawns the Docker container, pipes the PDF bytes in, reads JSON out.
Treats any non-zero exit, timeout, or crash as "unparseable" (fails closed).
"""
import json
import logging
import os
import subprocess

logger = logging.getLogger(__name__)

SANDBOX_IMAGE = os.getenv("PDF_SANDBOX_IMAGE", "khusela-pdf-sandbox")
SANDBOX_TIMEOUT = int(os.getenv("PDF_SANDBOX_TIMEOUT_SECONDS", "10"))


def parse_pdf_sandboxed(raw_bytes: bytes) -> dict:
    """
    Run the PDF parser inside the Docker sandbox.
    Returns {"text": "..."} on success or {"error": "..."} on failure.
    Never raises – always returns a dict.
    """
    cmd = [
        "docker", "run",
        "--rm",
        "--network", "none",
        "--read-only",
        "--tmpfs", "/tmp:size=32m",
        "--memory", "256m",
        "--cpus", "0.5",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "-i",
        SANDBOX_IMAGE,
    ]
    try:
        result = subprocess.run(
            cmd,
            input=raw_bytes,
            capture_output=True,
            timeout=SANDBOX_TIMEOUT,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace")[:200]
            logger.warning("PDF sandbox exited %d: %s", result.returncode, stderr)
            return {"error": f"sandbox exited with code {result.returncode}"}

        return json.loads(result.stdout)

    except subprocess.TimeoutExpired:
        logger.warning("PDF sandbox timed out after %ds", SANDBOX_TIMEOUT)
        return {"error": "parser timed out"}
    except FileNotFoundError:
        logger.error("Docker is not available; PDF sandbox cannot run.")
        return {"error": "docker not found"}
    except Exception as exc:  # noqa: BLE001
        logger.exception("PDF sandbox unexpected error: %s", exc)
        return {"error": str(exc)}
