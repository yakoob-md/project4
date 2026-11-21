FROM node:22-slim AS frontend
WORKDIR /frontend
COPY apps/web/package*.json ./
RUN npm install
COPY apps/web .
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY paperlens paperlens
COPY services/m0_contracts.py services/m1_contracts.py services/m1_storage.py services/paper_jobs.py services/
COPY --from=frontend /frontend/dist paperlens/react
ENV PORT=8080
CMD ["sh","-c","exec uvicorn paperlens.service:app --host 0.0.0.0 --port ${PORT}"]
