FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --extra google

COPY . .

ENV PORT=8080

CMD ["sh", "-c", "uv run python main.py serve --host 0.0.0.0 --port ${PORT:-8080}"]
