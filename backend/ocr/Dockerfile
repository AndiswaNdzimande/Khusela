# Minimal Tesseract image used as the OCR fallback when Tesseract is not
# installed on the host. Build from the repository root with:
#
#   docker build -t khusela-ocr:latest backend/ocr
#
# The engine invokes it as:
#
#   docker run --rm -i khusela-ocr:latest stdin stdout -l eng --psm 6 tsv
#
FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-osd \
    && rm -rf /var/lib/apt/lists/*

# Images are piped in on stdin and TSV is written to stdout, so no volume
# mounts are needed (this is what makes Windows/macOS/Linux behave the same).
ENTRYPOINT ["tesseract"]
