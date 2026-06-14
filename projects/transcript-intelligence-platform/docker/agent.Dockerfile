FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir fastapi uvicorn httpx jsonschema pydantic boto3 structlog tenacity

COPY platform_common ./platform_common
COPY services/agent_chatbot ./services/agent_chatbot
COPY services/observability ./services/observability

ENV PYTHONPATH=/app
EXPOSE 8080
CMD ["uvicorn", "services.agent_chatbot.app.api:app", "--host", "0.0.0.0", "--port", "8080"]
