"""Tesseract OCR for Khusela, with a local-first Docker fallback.

The module is designed so that every team laptop can run OCR even when the
Tesseract binary is not installed locally. Selection order is:

1. Local Tesseract through ``pytesseract`` (fastest).
2. The ``khusela-ocr`` Docker image built from ``backend/ocr/Dockerfile``.

Set ``KHUSELA_OCR_BACKEND`` to ``local``, ``docker`` or ``auto`` (default) to
force a backend. See ``docs/ocr-setup.md`` for installation instructions.

Command line usage::

    python backend/ocr/tesseract_engine.py --check
    python backend/ocr/tesseract_engine.py --image screenshot.png
    python backend/ocr/tesseract_engine.py --build-docker
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, BinaryIO, Union

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

Or use the Docker fallback:
  docker build -t {image} backend/ocr
  # or: ./scripts/setup_ocr.sh   (Windows: .\\scripts\\setup_ocr.ps1)

Then verify with:
  python backend/ocr/tesseract_engine.py --check
""".format(image=DEFAULT_DOCKER_IMAGE)


class OcrError(RuntimeError):
    """Raised when OCR is available but a run fails."""


class OcrUnavailableError(OcrError):
    """Raised when neither local Tesseract nor the Docker fallback can be used."""


@dataclass(frozen=True)
class OcrResult:
    """The text and mean word confidence (0.0-1.0) returned by Tesseract."""

    text: str
    confidence: float
    backend: str
    language: str
    psm: int
    tesseract_version: str | None = None
    preprocessed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Backend detection
# ---------------------------------------------------------------------------


def docker_image_name() -> str:
    """Return the configured Docker image name."""
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
        # pytesseract raises TesseractNotFoundError or TesseractError depending
        # on how the binary is broken. Either way, local OCR is unavailable.
        return None


def is_local_available() -> bool:
    """True when pytesseract and a working Tesseract binary are installed."""
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
    """True when the Docker CLI is installed and the daemon is reachable."""
    return _docker_daemon_running()


def docker_image_available(image: str | None = None) -> bool:
    """True when the OCR Docker image has already been built."""
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
    """Return the OCR backends that can run on this machine, best first."""
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
    """Build the OCR Docker image and return its name."""
    docker = _docker_executable()
    if not docker:
        raise OcrUnavailableError(
            "Docker is not installed or not on PATH, so the OCR fallback cannot run.\n\n"
            + _INSTALL_HELP
        )

    target = image or docker_image_name()
    command = [docker, "build", "-t", target, "-f", str(DOCKERFILE), str(DOCKERFILE.parent)]

    if not quiet:
        print(f"Building OCR Docker image '{target}' (this only happens once)...", file=sys.stderr)

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
        raise OcrError(
            f"Could not build the OCR Docker image '{target}'.\n{details}\n\n"
            "If you are offline, ask a teammate to run "
            f"'docker build -t {target} backend/ocr' and share the image, "
            "or install Tesseract locally."
        )

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
            f"Run: docker build -t {image} backend/ocr"
        )

    build_docker_image(image)


def select_backend(preferred: str | None = None) -> str:
    """Pick an OCR backend, raising a helpful error if none can run."""
    choice = (preferred or os.getenv("KHUSELA_OCR_BACKEND") or "auto").strip().lower()
    if choice not in {"auto", "local", "docker"}:
        raise ValueError(
            f"Unknown OCR backend '{choice}'. Use 'auto', 'local' or 'docker'."
        )

    if choice == "local":
        if is_local_available():
            return "local"
        raise OcrUnavailableError(
            "KHUSELA_OCR_BACKEND=local but local Tesseract is not installed.\n\n"
            + _INSTALL_HELP
        )

    if choice == "docker":
        if is_docker_available():
            return "docker"
        raise OcrUnavailableError(
            "KHUSELA_OCR_BACKEND=docker but Docker is not running.\n"
            "Start Docker Desktop (or the Docker service) and try again.\n\n"
            + _INSTALL_HELP
        )

    if is_local_available():
        return "local"
    if is_docker_available():
        return "docker"
    raise OcrUnavailableError(_INSTALL_HELP)


# ---------------------------------------------------------------------------
# OCR execution
# ---------------------------------------------------------------------------


def _read_image_bytes(image: ImageSource) -> bytes:
    """Normalise paths, file objects, bytes and PIL images to PNG/raw bytes."""
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

    raise TypeError(
        "image must be a path, bytes, a binary file object or a PIL.Image.Image"
    )


def _to_pil_image(data: bytes) -> Any:
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise OcrUnavailableError(
            "Pillow is not installed. Run: pip install -r backend/requirements.txt"
        ) from exc

    stream = io.BytesIO(data)
    image = Image.open(stream)
    image.load()
    return image


def parse_tsv(tsv: str) -> tuple[str, float]:
    """Convert Tesseract TSV output into ``(text, mean_confidence)``.

    Confidence is returned on the same 0.0-1.0 scale the rule engine expects.
    Rows without a real confidence (``-1``) are ignored.
    """
    lines: dict[tuple[str, str, str, str], list[str]] = {}
    order: list[tuple[str, str, str, str]] = []
    confidences: list[float] = []

    reader = csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE)
    for row in reader:
        if str(row.get("level", "")).strip() != "5":
            continue
        word = (row.get("text") or "").strip()
        if not word:
            continue

        key = (
            str(row.get("page_num", "")),
            str(row.get("block_num", "")),
            str(row.get("par_num", "")),
            str(row.get("line_num", "")),
        )
        if key not in lines:
            lines[key] = []
            order.append(key)
        lines[key].append(word)

        raw_conf = row.get("conf")
        try:
            conf = float(raw_conf)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if conf >= 0:
            confidences.append(conf)

    text = "\n".join(" ".join(lines[key]) for key in order)
    confidence = round(sum(confidences) / len(confidences) / 100.0, 4) if confidences else 0.0
    return text, max(0.0, min(1.0, confidence))


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
) -> tuple[str, float, str | None]:
    try:
        import pytesseract
        from pytesseract import Output
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise OcrUnavailableError(
            "pytesseract is not installed. Run: pip install -r backend/requirements.txt"
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
        # TesseractNotFoundError / TesseractError / bad language data.
        raise OcrError(f"Local Tesseract failed: {exc}") from exc

    text, confidence = parse_tsv(str(tsv))
    return text, confidence, local_tesseract_version()


def _run_docker(
    image: ImageSource,
    language: str,
    psm: int,
    docker_image: str | None = None,
) -> tuple[str, float, None]:
    docker = _docker_executable()
    if not docker:
        raise OcrUnavailableError(
            "Docker is not installed or not on PATH.\n\n" + _INSTALL_HELP
        )

    target = docker_image or docker_image_name()
    _ensure_docker_image(target)

    command = [
        docker,
        "run",
        "--rm",
        "-i",
        target,
        "stdin",
        "stdout",
        "-l",
        language,
        "--psm",
        str(psm),
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
        raise OcrError(
            f"Docker OCR timed out after {_timeout_seconds():.0f}s."
        ) from exc
    except OSError as exc:
        raise OcrError(f"Could not run Docker: {exc}") from exc

    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise OcrError(f"Docker OCR failed (exit {result.returncode}): {stderr}")

    tsv = result.stdout.decode("utf-8", errors="replace")
    text, confidence = parse_tsv(tsv)
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
        language: Tesseract language code. Defaults to ``KHUSELA_OCR_LANG``
            or ``eng``.
        psm: Tesseract page segmentation mode. Defaults to ``KHUSELA_OCR_PSM``
            or ``6`` (a single uniform block of text, good for screenshots).
        backend: ``local``, ``docker`` or ``auto``. Overrides
            ``KHUSELA_OCR_BACKEND``.
        preprocess: Apply grayscale/resize/threshold preprocessing first
            (enabled by default; see :mod:`ocr.preprocess`).
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
        try:
            from .preprocess import preprocess_bytes
        except ImportError:  # running tesseract_engine.py as a plain script
            from preprocess import preprocess_bytes  # type: ignore[no-redef]

        image = preprocess_bytes(image, preprocess_config)

    selected = select_backend(backend)

    if selected == "local":
        try:
            text, confidence, version = _run_local(image, lang, psm)
        except OcrError:
            # A broken local install should not block the team: try Docker when
            # auto-selection is in play. Explicit requests still raise.
            if (backend or os.getenv("KHUSELA_OCR_BACKEND") or "auto").strip().lower() != "auto":
                raise
            if not is_docker_available():
                raise
            text, confidence, version = _run_docker(image, lang, psm)
            selected = "docker"
    else:
        text, confidence, version = _run_docker(image, lang, psm)

    return OcrResult(
        text=text,
        confidence=confidence,
        backend=selected,
        language=lang,
        psm=psm,
        tesseract_version=version,
        preprocessed=bool(preprocess),
    )


# ---------------------------------------------------------------------------
# Command line helpers
# ---------------------------------------------------------------------------


def _check() -> int:
    local_version = local_tesseract_version()
    docker_ok = is_docker_available()
    image = docker_image_name()
    image_ok = docker_image_available(image) if docker_ok else False

    print("Khusela OCR check")
    print(f"  Python:            {sys.version.split()[0]}")
    print(f"  pytesseract:       {'installed' if _module_installed('pytesseract') else 'MISSING'}")
    print(f"  Local Tesseract:   {local_version or 'not found'}")
    print(f"  Docker:            {'available' if docker_ok else ('installed, daemon not running' if _docker_executable() else 'not found')}")
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


def _module_installed(name: str) -> bool:
    try:
        __import__(name)
    except ImportError:
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Khusela OCR runner (Tesseract + Docker fallback)")
    parser.add_argument("--check", action="store_true", help="check which OCR backend will be used")
    parser.add_argument("--image", help="run OCR on an image and print the text")
    parser.add_argument("--build-docker", action="store_true", help="build the OCR Docker fallback image")
    parser.add_argument("--backend", choices=["auto", "local", "docker"], help="force a backend")
    parser.add_argument("--lang", default=None, help="Tesseract language code (default: eng)")
    parser.add_argument("--psm", type=int, default=None, help="Tesseract page segmentation mode (default: 6)")
    parser.add_argument(
        "--no-preprocess",
        action="store_true",
        help="skip grayscale/resize/threshold preprocessing",
    )
    parser.add_argument("--json", action="store_true", help="print OCR output as JSON")
    args = parser.parse_args(argv)

    try:
        if args.build_docker:
            image = build_docker_image()
            print(image)
            return 0

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
