"""Kết nối dùng chung cho demo (từ máy host tới các container Docker)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Demo chỉ nói chuyện với engine qua HTTP (Gate API + Reporting API), không đọc file nội bộ của engine.
ENGINE_API = os.getenv("DEMO_ENGINE_API", "http://localhost:8000")
ENGINE_TOKEN = os.getenv("DEMO_ENGINE_TOKEN")  # token vai reporter khi engine bật auth.users

PG = {
    "host": os.getenv("DEMO_PG_HOST", "localhost"),
    "port": int(os.getenv("DEMO_PG_PORT", "5431")),
    "user": "admin",
    "password": "password123",
    "dbname": "exchange",
}
PG_ADMIN_DB = "sample_db"  # DB mặc định của container, dùng để CREATE/DROP DATABASE exchange

CH = {
    "host": os.getenv("DEMO_CH_HOST", "localhost"),
    "port": int(os.getenv("DEMO_CH_PORT", "8123")),
    "username": "default",
    "password": "clickhouse123",
}
CH_DATABASE = "analytics"
CH_NAIVE_DATABASE = "analytics_naive"  # pipeline đối chứng: loader không có engine bảo vệ

KAFKA_BOOTSTRAP = os.getenv("DEMO_KAFKA", "localhost:19092")
CONNECT_URL = os.getenv("DEMO_CONNECT_URL", "http://localhost:8083")

CONNECTOR_NAME = "market-trades-source"
TOPIC = "market.public.trades"  # <topic.prefix>.<schema>.<table>
LOADER_GROUP = "warehouse-loader"
LOADER_NAIVE_GROUP = "warehouse-loader-naive"
SOURCE_TABLE = "trades"
PIPELINE_NAME = "market_trades"
REGISTRY_KEY = f"{PIPELINE_NAME}/{SOURCE_TABLE}"
REGISTRY_DIR = "data/registry"  # khớp registry.dir trong config/main.yaml

# Pipeline 2 (chạy song song với market_trades): cùng DB nguồn, cùng Debezium connector, khác bảng.
TICKERS_PIPELINE = "market_tickers"
TICKERS_TABLE = "tickers"

# Pipeline 3 (mức 3): sink Kafka Connect có sẵn (Debezium JDBC sink) chép tickers sang Postgres replica.
# Sink chỉ ghi dữ liệu (schema.evolution=none); engine giữ schema bảng replica và pause/resume sink theo freeze.
# Chọn tickers (không phải trades): kịch bản rename của trades làm sink cố định schema chết khi đọc lại
# message cũ — xem CONFIGURATION_GUIDE mục 5.
REPLICA_PIPELINE = "market_tickers_replica"
REPLICA_DB = "exchange_replica"
SINK_CONNECTOR_NAME = "market-tickers-replica"
SINK_GROUP = f"connect-{SINK_CONNECTOR_NAME}"  # consumer group Kafka Connect tự đặt cho sink
