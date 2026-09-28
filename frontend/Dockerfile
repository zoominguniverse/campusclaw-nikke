FROM python:3.14-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 5173
CMD ["gunicorn", "--bind", "0.0.0.0:5173", "--workers", "2", "server:app"]

