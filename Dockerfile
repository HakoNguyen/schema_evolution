# Schema Evolution: engine + API + giao diện web trong MỘT image, một cổng (8000).
#
#   docker compose up -d --build engine        # rồi mở http://localhost:8000
#
# - config/ (main.yaml, pipelines/*.yaml, secrets.env) và data/ (registry, lịch sử) gắn từ máy host:
#   sửa trên web hay sửa file đều được engine nạp lại sau ~3 giây, dừng container không mất gì.
# - Config viết cho máy host dùng "localhost:<cổng>" (Postgres 5431, Kafka 19092...). Trong container,
#   localhost là chính container, nên mỗi cổng trong FORWARD_PORTS được socat chuyển về máy host.
#   Nhờ vậy cùng một config chạy được cả trên host lẫn trong Docker. Riêng Redpanda còn quảng bá
#   "localhost:19092" cho client, nên chuyển tiếp là cách duy nhất không phải sửa config.
#   DB ở máy khác (host thật, không phải localhost) thì không cần thêm gì.

# --- 1. Build giao diện (Vite) ra file tĩnh ---
FROM node:20-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- 2. Engine + API, phục vụ luôn giao diện đã build ---
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends socat \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
# streamlit chỉ dùng cho giao diện cũ (app/app.py), API không import -> bỏ khỏi image cho nhẹ.
RUN grep -v '^streamlit' requirements.txt > /tmp/requirements.txt \
    && pip install --no-cache-dir -r /tmp/requirements.txt
COPY src/ src/
COPY app/ app/
COPY api/ api/
COPY --from=frontend /build/dist frontend/dist

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    FORWARD_PORTS="5431 3306 27017 8123 19092 8083"
EXPOSE 8000
# Nghe cả 127.0.0.1 lẫn ::1: client như psycopg2 thử "localhost" qua IPv6 trước.
CMD ["sh", "-c", "for p in $FORWARD_PORTS; do socat TCP-LISTEN:$p,bind=127.0.0.1,fork,reuseaddr TCP:host.docker.internal:$p & socat TCP6-LISTEN:$p,bind=[::1],ipv6only=1,fork,reuseaddr TCP:host.docker.internal:$p 2>/dev/null & done; exec uvicorn api.main:app --host 0.0.0.0 --port 8000"]
