FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY preprocessor.py /app/

# Run the preprocessor
CMD ["python", "preprocessor.py"]
