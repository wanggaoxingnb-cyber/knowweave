FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=7860 DEMO_CLOUD=1 DEMO_AUTO_RESET=1 DEMO_RATE_LIMIT=30
EXPOSE 7860
CMD ["python", "-m", "app.main"]
