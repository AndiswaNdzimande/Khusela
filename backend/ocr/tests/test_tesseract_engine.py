import io
import os

import pytest

from ocr import tesseract_engine as engine


TSV = """level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext
1\t1\t0\t0\t0\t0\t0\t0\t400\t200\t-1\t
4\t1\t1\t1\t1\t0\t10\t10\t200\t20\t-1\t
5\t1\t1\t1\t1\t1\t10\t10\t50\t20\t95.5\tHello
5\t1\t1\t1\t1\t2\t70\t10\t50\t20\t84.5\tWorld
5\t1\t1\t1\t2\t1\t10\t40\t50\t20\t90.0\tSecond
5\t1\t1\t1\t2\t2\t70\t40\t50\t20\t-1\t
"""


def test_parse_tsv_builds_lines_and_mean_confidence():
    text, confidence = engine.parse_tsv(TSV)

    assert text == "Hello World\nSecond"
    assert confidence == pytest.approx(0.9)


def test_parse_tsv_handles_empty_output():
    text, confidence = engine.parse_tsv("")

    assert text == ""
    assert confidence == 0.0


def test_auto_prefers_local(monkeypatch):
    monkeypatch.setattr(engine, "is_local_available", lambda: True)
    monkeypatch.setattr(engine, "is_docker_available", lambda: True)

    assert engine.select_backend("auto") == "local"


def test_auto_falls_back_to_docker(monkeypatch):
    monkeypatch.setattr(engine, "is_local_available", lambda: False)
    monkeypatch.setattr(engine, "is_docker_available", lambda: True)

    assert engine.select_backend() == "docker"


def test_backend_can_be_forced_with_env(monkeypatch):
    monkeypatch.setattr(engine, "is_local_available", lambda: True)
    monkeypatch.setattr(engine, "is_docker_available", lambda: True)
    monkeypatch.setenv("KHUSELA_OCR_BACKEND", "docker")

    assert engine.select_backend() == "docker"


def test_missing_backends_raise_actionable_error(monkeypatch):
    monkeypatch.setattr(engine, "is_local_available", lambda: False)
    monkeypatch.setattr(engine, "is_docker_available", lambda: False)

    with pytest.raises(engine.OcrUnavailableError) as excinfo:
        engine.select_backend()

    message = str(excinfo.value)
    assert "brew install tesseract" in message
    assert "docker build" in message


def test_forced_local_backend_does_not_silently_use_docker(monkeypatch):
    monkeypatch.setattr(engine, "is_local_available", lambda: False)
    monkeypatch.setattr(engine, "is_docker_available", lambda: True)

    with pytest.raises(engine.OcrUnavailableError):
        engine.select_backend("local")


def test_run_ocr_uses_selected_backend(monkeypatch):
    monkeypatch.setattr(engine, "select_backend", lambda preferred=None: "docker")

    def fake_docker(image, language, psm):
        assert image == b"fake-image"
        assert language == "eng"
        return "R1,800.00\nThabo Sneakers", 0.91, None

    monkeypatch.setattr(engine, "_run_docker", fake_docker)

    result = engine.run_ocr(b"fake-image", preprocess=False)

    assert result.backend == "docker"
    assert result.text == "R1,800.00\nThabo Sneakers"
    assert result.confidence == 0.91
    assert result.language == "eng"
    assert result.psm == 6


def test_broken_local_install_falls_back_to_docker_in_auto_mode(monkeypatch):
    monkeypatch.delenv("KHUSELA_OCR_BACKEND", raising=False)
    monkeypatch.setattr(engine, "is_local_available", lambda: True)
    monkeypatch.setattr(engine, "is_docker_available", lambda: True)

    def broken_local(image, language, psm):
        raise engine.OcrError("tesseract exploded")

    monkeypatch.setattr(engine, "_run_local", broken_local)
    monkeypatch.setattr(
        engine,
        "_run_docker",
        lambda image, language, psm: ("fallback text", 0.42, None),
    )

    result = engine.run_ocr(b"image", preprocess=False)

    assert result.backend == "docker"
    assert result.text == "fallback text"


def test_invalid_psm_env_raises(monkeypatch):
    monkeypatch.setenv("KHUSELA_OCR_PSM", "not-a-number")

    with pytest.raises(ValueError):
        engine.run_ocr(b"image")


def test_docker_image_name_can_be_configured(monkeypatch):
    monkeypatch.setenv("KHUSELA_OCR_DOCKER_IMAGE", "my-ocr:test")

    assert engine.docker_image_name() == "my-ocr:test"


@pytest.mark.skipif(
    os.getenv("KHUSELA_OCR_INTEGRATION") != "1",
    reason="set KHUSELA_OCR_INTEGRATION=1 to run real Tesseract/Docker OCR",
)
def test_real_ocr_on_blank_image():
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (400, 200), "white").save(buffer, format="PNG")

    result = engine.run_ocr(buffer.getvalue())

    assert result.backend in {"local", "docker"}
    assert result.preprocessed is True
    assert result.text == ""
    assert result.confidence == 0.0
