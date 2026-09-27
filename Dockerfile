FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bancocloud bancocloud
COPY contracts contracts
COPY config config
COPY prompts prompts
COPY data/generator data/generator
COPY data/synthetic/customer_seed.jsonl data/synthetic/customer_seed.jsonl
COPY infra/local/schema.sql infra/local/schema.sql
ENV PYTHONPATH=/app
CMD ["uvicorn","bancocloud.api.core:app","--host","0.0.0.0","--port","8000"]
