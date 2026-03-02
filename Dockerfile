FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir requests==2.32.3

COPY main.py .

RUN useradd --create-home --shell /bin/bash appuser
USER appuser

CMD ["python", "main.py"]
