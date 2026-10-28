FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/veripop
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY engine ./engine
COPY scripts ./scripts
RUN useradd --create-home --uid 10001 appuser && mkdir -p /srv/veripop/data && chown -R appuser:appuser /srv/veripop
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
