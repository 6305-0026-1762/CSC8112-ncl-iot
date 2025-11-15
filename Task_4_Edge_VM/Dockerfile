FROM python:3.9-slim

WORKDIR /app

# Install system deps for TensorFlow / matplotlib
RUN apt-get update && apt-get install -y \
    build-essential \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy model + inference script
# (Assumes pm25_model.tflite is at repo root when you build)
COPY ../pm25_model.tflite /app/pm25_model.tflite
COPY pm25_inference.py /app/

CMD ["python", "pm25_inference.py"]
