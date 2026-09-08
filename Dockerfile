FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN groupadd -g 1001 bot && useradd -r -u 1001 -g bot bot && mkdir /data && chown bot:bot /data
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY pyproject.toml README.md LICENSE main.py ./
COPY src ./src
COPY utils ./utils
RUN pip install --no-deps .
USER 1001:1001
CMD ["python", "main.py"]
