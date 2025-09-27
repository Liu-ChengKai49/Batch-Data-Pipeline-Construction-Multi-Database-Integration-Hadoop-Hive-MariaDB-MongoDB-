FROM python:3.11-slim
WORKDIR /app
COPY docker/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -U pip && pip install --no-cache-dir -r /app/requirements.txt
COPY pyproject.toml /app/pyproject.toml
RUN pip install --no-cache-dir ".[dev]"
COPY src /app/src
ENV PYTHONPATH=/app/src
CMD ["python","-c","print('etl image ready')"]
