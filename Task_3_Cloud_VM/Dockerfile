FROM python:3.9-slim

WORKDIR /app

# Install minimal build tools (often enough for prophet/matplotlib wheels)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy ML engine and predictor code
COPY ml_engine.py /app/
COPY predictor.py /app/

CMD ["python", "predictor.py"]

