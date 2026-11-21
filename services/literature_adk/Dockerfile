FROM python:3.12-slim
WORKDIR /app
COPY services/literature_adk/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY services services
EXPOSE 8001
CMD ["uvicorn", "services.literature_adk.app:app", "--host", "0.0.0.0", "--port", "8001"]
