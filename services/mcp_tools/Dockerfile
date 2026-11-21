FROM python:3.12-slim
WORKDIR /app
COPY services/mcp_tools/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY paperlens paperlens
COPY packages packages
COPY services services
EXPOSE 9000
CMD ["python", "-m", "services.mcp_tools.server"]
