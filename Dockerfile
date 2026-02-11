FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

# Data directory wordt als volume gemount
VOLUME /app/data

CMD ["python", "automation.py"]
