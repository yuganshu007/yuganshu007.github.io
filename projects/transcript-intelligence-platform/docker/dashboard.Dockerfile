FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir streamlit plotly pandas duckdb pyarrow structlog boto3

COPY platform_common ./platform_common
COPY services/analytics_dashboard ./services/analytics_dashboard

ENV PYTHONPATH=/app
EXPOSE 8501
CMD ["streamlit", "run", "services/analytics_dashboard/app/Home.py", \
     "--server.address=0.0.0.0", "--server.port=8501"]
