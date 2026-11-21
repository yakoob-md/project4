FROM python:3.12-slim
WORKDIR /app
COPY services/review_worker/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY services services
COPY paperlens/core.py paperlens/core.py
EXPOSE 8002
CMD ["uvicorn", "services.review_worker.app:app", "--host", "0.0.0.0", "--port", "8002"]
