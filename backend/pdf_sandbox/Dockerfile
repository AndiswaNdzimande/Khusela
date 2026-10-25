# TASK-27: Sandboxed PDF parser image.
# Build:  docker build -t khusela-pdf-sandbox ./pdf_sandbox
# Run:    docker run --rm --network none --read-only \
#           --tmpfs /tmp:size=32m \
#           --memory 256m --cpus 0.5 \
#           --cap-drop ALL --security-opt no-new-privileges \
#           -i khusela-pdf-sandbox < /path/to/file.pdf

FROM python:3.12-slim

# Install pdfminer.six (pure-Python, no system deps needed)
RUN pip install --no-cache-dir pdfminer.six==20221105

# Non-root user
RUN useradd --no-create-home --shell /bin/false parser
USER parser

WORKDIR /app
COPY --chown=parser:parser parse_pdf.py /app/parse_pdf.py

# Read PDF bytes from stdin, write JSON to stdout
ENTRYPOINT ["python", "/app/parse_pdf.py"]
