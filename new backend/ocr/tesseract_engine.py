"""Tesseract OCR for Khusela, with a local-first Docker fallback.

The module is designed so that every team laptop can run OCR even when the
Tesseract binary is not installed locally. Selection order is:

1. Local Tesseract through ``pytesseract`` (fastest).
2. The ``khusela-ocr`` Docker image built from ``ocr/Dockerfile``.

Set ``KHUSELA_OCR_BACKEND`` to ``local``, ``docker`` or ``auto`` (default) to
force a backend.

Install Tesseract locally:
  macOS:          brew install tesseract
  Ubuntu/Debian:  sudo apt-get install tesseract-ocr
  Windows:        winget install UB-Mannheim.TesseractOCR
                  (then reopen your terminal so PATH is refreshed)

Command line usage::

    python ocr/tesseract_engine.py --check
    python ocr/tesseract_engine.py --image screenshot.png
"""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, BinaryIO, Union

from .confidence import (
    RELIABLE_CONFIDENCE_THRESHOLD,
    ConfidenceScore,
    confidence_label,
    parse_tsv as _parse_tsv_confidence,
)

DEFAULT_DOCKER_IMAGE = "khusela-ocr:latest"
DOCKERFILE = Path(__file__).with_name("Dockerfile")
DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_BUILD_TIMEOUT_SECONDS = 600

ImageSource = Union[str, Path, bytes, bytearray, BinaryIO, Any]

_INSTALL_HELP = """\
No working OCR backend was found.

Install Tesseract locally:
  macOS:          brew install tesseract
  Ubuntu/Debian:  sudo apt-get install tesseract-ocr
  Windows:        winget install UB-Mannheim.TesseractOCR
                  (then reopen your terminal so PATH is refreshed)

Or use the Docker fallback (requires Docker Desktop):
  docker build -t {image} ocr/

Then verify with:
  python -m ocr.tesseract_engine --check
""".format(image=DEFAULT_DOCKER_IMAGE)


class OcrError(RuntimeError):
    """Raised when OCR is available but a run fails."""


class OcrUnavailableError(OcrError):
    """Raised when neither local Tesseract nor the Docker fallback can be used."""


@dataclass(frozen=True)
class OcrResult:
    """Raw OCR text, reliability score and engine metadata."""

    text: str
    confidence: float
    backend: str
    language: str
    psm: int
    tesseract_version: str | None = None
    preprocessed: bool = False
    word_count: int = 0
    mean_word_confidence: float = 0.0
    low_confidence_ratio: float = 0.0

    @property
    def raw_text(self) -> str:
        return self.text

    @property
    def ocr_confidence(self) -> float:
        return self.confidence

    @property
    def confidence_label(self) -> str:
        return confidence_label(self.confidence)

    @property
    def is_reliable(self) -> bool:
        return self.confidence >= RELIABLE_CONFIDENCE_THRESHOLD

    def as_dict(self) -> dict[str, Any]:
        return {
            "raw_ocr_text": self.text,
            "ocr_confidence": self.confidence,
            "confidence_label": self.confidence_label,
            "is_reliable": self.is_reliable,
            "word_count": self.word_count,
            "mean_word_confidence": self.mean_word_confidence,
            "low_confidence_ratio": self.low_confidence_ratio,
            "backend": self.backend,
            "language": self.language,
            "psm": self.psm,
            "tesseract_version": self.tesseract_version,
            "preprocessed": self.preprocessed,
        }


def docker_image_name() -> str:
    return os.getenv("KHUSELA_OCR_DOCKER_IMAGE", DEFAULT_DOCKER_IMAGE).strip() or DEFAULT_DOCKER_IMAGE


def _configured_tesseract_cmd() -> str | None:
    cmd = os.getenv("TESSERACT_CMD") or os.getenv("KHUSELA_TESSERACT_CMD")
    return cmd.strip() if cmd else None


@lru_cache(maxsize=1)
def local_tesseract_version() -> str | None:
    """Return the local Tesseract version, or ``None`` when unavailable."""
    try:
        import pytesseract
    except ImportError:
        return None

    cmd = _configured_tesseract_cmd()
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd

    try:
        return str(pytesseract.get_tesseract_version())
    except Exception:
        return None


def is_local_available() -> bool:
    return local_tesseract_version() is not None


def _docker_executable() -> str | None:
    return shutil.which("docker")


@lru_cache(maxsize=1)
def _docker_daemon_running() -> bool:
    docker = _docker_executable()
    if not docker:
        return False
    try:
        result = subprocess.run(
            [docker, "info"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def is_docker_available() -> bool:
    return _docker_daemon_running()


def docker_image_available(image: str | None = None) -> bool:
    docker = _docker_executable()
    if not docker:
        return False
    try:
        result = subprocess.run(
            [docker, "image", "inspect", image or docker_image_name()],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def available_backends() -> list[str]:
    backends: list[str] = []
    if is_local_available():
        backends.append("local")
    if is_docker_available():
        backends.append("docker")
    return backends


def build_docker_image(
    image: str | None = None,
    *,
    timeout: float = DEFAULT_BUILD_TIMEOUT_SECONDS,
    quiet: bool = False,
) -> str:
    docker = _docker_executable()
    if not docker:
        raise OcrUnavailableError(
            "Docker is not installed or not on PATH.\n\n" + _INSTALL_HELP
        )

    target = image or docker_image_name()
    dockerfile_dir = DOCKERFILE.parent if DOCKERFILE.exists() else Path("ocr")
    command = [docker, "build", "-t", target, str(dockerfile_dir)]

    if not quiet:
        print(f"Building OCR Docker image '{target}'...", file=sys.stderr)

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise OcrError(f"Timed out after {timeout:.0f}s while building the OCR image.") from exc
    except OSError as exc:
        raise OcrError(f"Could not run Docker: {exc}") from exc

    if result.returncode != 0:
        details = (result.stderr or result.stdout or "unknown Docker error").strip()
        raise OcrError(f"Could not build the OCR Docker image '{target}'.\n{details}")

    if not quiet:
        print(f"OCR Docker image '{target}' is ready.", file=sys.stderr)
    return target


def _ensure_docker_image(image: str) -> None:
    if docker_image_available(image):
        return

    autobuild = os.getenv("KHUSELA_OCR_AUTOBUILD", "1").strip().lower()
    if autobuild in {"0", "false", "no", "off"}:
        raise OcrUnavailableError(
            f"The OCR Docker image '{image}' is not built and "
            "KHUSELA_OCR_AUTOBUILD is disabled.\n"
            f"Run: docker build -t {image} ocr/"
        )

    build_docker_image(image)


def select_backend(preferred: str | None = None) -> str:
    choice = (preferred or os.getenv("KHUSELA_OCR_BACKEND") or "auto").strip().lower()
    if choice not in {"auto", "local", "docker"}:
        raise ValueError(f"Unknown OCR backend '{choice}'. Use 'auto', 'local' or 'docker'.")

    if choice == "local":
        if is_local_available():
            return "local"
        raise OcrUnavailableError("KHUSELA_OCR_BACKEND=local but local Tesseract is not installed.\n\n" + _INSTALL_HELP)

    if choice == "docker":
        if is_docker_available():
            return "docker"
        raise OcrUnavailableError("KHUSELA_OCR_BACKEND=docker but Docker is not running.\n\n" + _INSTALL_HELP)

    if is_local_available():
        return "local"
    if is_docker_available():
        return "docker"
    raise OcrUnavailableError(_INSTALL_HELP)


def _read_image_bytes(image: ImageSource) -> bytes:
    if isinstance(image, (bytes, bytearray)):
        return bytes(image)

    if isinstance(image, (str, Path)):
        return Path(image).read_bytes()

    read = getattr(image, "read", None)
    if callable(read):
        data = read()
        if isinstance(data, str):
            data = data.encode()
        if isinstance(data, (bytes, bytearray)):
            return bytes(data)
        raise TypeError("File object did not return bytes.")

    save = getattr(image, "save", None)
    if callable(save):
        buffer = io.BytesIO()
        fmt = (getattr(image, "format", None) or "PNG").upper()
        image.save(buffer, format=fmt)
        return buffer.getvalue()

    raise TypeError("image must be a path, bytes, a binary file object or a PIL.Image.Image")


def _to_pil_image(data: bytes) -> Any:
    try:
        from PIL import Image
    except ImportError as exc:
        raise OcrUnavailableError(
            "Pillow is not installed. Run: pip install -r requirements.txt"
        ) from exc

    stream = io.BytesIO(data)
    image = Image.open(stream)
    image.load()
    return image


def parse_tsv(tsv: str) -> tuple[str, float]:
    text, score = _parse_tsv_confidence(tsv)
    return text, score.score


def _timeout_seconds() -> float:
    raw = os.getenv("KHUSELA_OCR_TIMEOUT", str(DEFAULT_TIMEOUT_SECONDS))
    try:
        return max(1.0, float(raw))
    except ValueError:
        return float(DEFAULT_TIMEOUT_SECONDS)


def _run_local(
    image: ImageSource,
    language: str,
    psm: int,
) -> tuple[str, ConfidenceScore, str | None]:
    try:
        import pytesseract
        from pytesseract import Output
    except ImportError as exc:
        raise OcrUnavailableError(
            "pytesseract is not installed. Run: pip install -r requirements.txt"
        ) from exc

    cmd = _configured_tesseract_cmd()
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd

    pil_image = _to_pil_image(_read_image_bytes(image))
    try:
        tsv = pytesseract.image_to_data(
            pil_image,
            lang=language,
            config=f"--psm {psm}",
            output_type=Output.STRING,
        )
    except Exception as exc:
        raise OcrError(f"Local Tesseract failed: {exc}") from exc

    text, confidence = _parse_tsv_confidence(str(tsv))
    return text, confidence, local_tesseract_version()


def _run_docker(
    image: ImageSource,
    language: str,
    psm: int,
    docker_image: str | None = None,
) -> tuple[str, ConfidenceScore, None]:
    docker = _docker_executable()
    if not docker:
        raise OcrUnavailableError("Docker is not installed or not on PATH.\n\n" + _INSTALL_HELP)

    target = docker_image or docker_image_name()
    _ensure_docker_image(target)

    command = [
        docker, "run", "--rm", "-i",
        target, "stdin", "stdout",
        "-l", language,
        "--psm", str(psm),
        "tsv",
    ]

    try:
        result = subprocess.run(
            command,
            input=_read_image_bytes(image),
            capture_output=True,
            timeout=_timeout_seconds(),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise OcrError(f"Docker OCR timed out after {_timeout_seconds():.0f}s.") from exc
    except OSError as exc:
        raise OcrError(f"Could not run Docker: {exc}") from exc

    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise OcrError(f"Docker OCR failed (exit {result.returncode}): {stderr}")

    tsv = result.stdout.decode("utf-8", errors="replace")
    text, confidence = _parse_tsv_confidence(tsv)
    return text, confidence, None


def run_ocr(
    image: ImageSource,
    *,
    language: str | None = None,
    psm: int | None = None,
    backend: str | None = None,
    preprocess: bool = True,
    preprocess_config: Any = None,
) -> OcrResult:
    """Run Tesseract on an image using the best available backend.

    Args:
        image: Path, bytes, binary file object or ``PIL.Image.Image``.
        language: Tesseract language code (default: ``KHUSELA_OCR_LANG`` or ``eng``).
        psm: Tesseract page segmentation mode (default: ``KHUSELA_OCR_PSM`` or ``6``).
        backend: ``local``, ``docker`` or ``auto``.
        preprocess: Apply grayscale/resize/threshold preprocessing first.
        preprocess_config: Optional :class:`ocr.preprocess.PreprocessConfig`.

    Raises:
        OcrUnavailableError: No backend is usable (includes install help).
        OcrError: A backend was selected but the OCR run failed.
    """
    lang = (language or os.getenv("KHUSELA_OCR_LANG") or "eng").strip() or "eng"

    if psm is None:
        raw_psm = os.getenv("KHUSELA_OCR_PSM", "6")
        try:
            psm = int(raw_psm)
        except ValueError as exc:
            raise ValueError(f"KHUSELA_OCR_PSM must be an integer, got {raw_psm!r}") from exc

    if preprocess:
        from .preprocess import preprocess_bytes
        image = preprocess_bytes(image, preprocess_config)

    selected = select_backend(backend)

    if selected == "local":
        try:
            text, score, version = _run_local(image, lang, psm)
        except OcrError:
            if (backend or os.getenv("KHUSELA_OCR_BACKEND") or "auto").strip().lower() != "auto":
                raise
            if not is_docker_available():
                raise
            text, score, version = _run_docker(image, lang, psm)
            selected = "docker"
    else:
        text, score, version = _run_docker(image, lang, psm)

    return OcrResult(
        text=text,
        confidence=score.score,
        backend=selected,
        language=lang,
        psm=psm,
        tesseract_version=version,
        preprocessed=bool(preprocess),
        word_count=score.word_count,
        mean_word_confidence=score.mean_word_confidence,
        low_confidence_ratio=score.low_confidence_ratio,
    )


def _module_installed(name: str) -> bool:
    try:
        __import__(name)
    except ImportError:
        return False
    return True


def _check() -> int:
    local_version = local_tesseract_version()
    docker_ok = is_docker_available()
    image = docker_image_name()
    image_ok = docker_image_available(image) if docker_ok else False

    print("Khusela OCR check")
    print(f"  Python:            {sys.version.split()[0]}")
    print(f"  pytesseract:       {'installed' if _module_installed('pytesseract') else 'MISSING'}")
    print(f"  Local Tesseract:   {local_version or 'not found'}")
    print(f"  Docker:            {'available' if docker_ok else 'not found / not running'}")
    print(f"  Docker image:      {image} ({'built' if image_ok else 'not built'})")

    try:
        selected = select_backend()
    except OcrUnavailableError as exc:
        print("\nFAIL: no OCR backend is usable.")
        print(str(exc))
        return 1

    print(f"  Selected backend:  {selected}")
    print("\nOK: OCR is ready.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Khusela OCR runner")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--image", help="run OCR on an image and print the text")
    parser.add_argument("--backend", choices=["auto", "local", "docker"])
    parser.add_argument("--lang", default=None)
    parser.add_argument("--psm", type=int, default=None)
    parser.add_argument("--no-preprocess", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.check or not args.image:
            return _check()

        result = run_ocr(
            args.image,
            language=args.lang,
            psm=args.psm,
            backend=args.backend,
            preprocess=not args.no_preprocess,
        )
    except (OcrError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result.as_dict(), indent=2, ensure_ascii=False))
    else:
        print(f"Backend:    {result.backend}")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"Language:   {result.language} (psm {result.psm})")
        print("--- text ---")
        print(result.text)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
