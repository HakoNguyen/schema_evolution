-- Warehouse phân tích: bản sao của trades, khớp schema v1 của nguồn.
-- {db} = analytics (pipeline có engine) hoặc analytics_naive (pipeline đối chứng), do setup.py thay vào.
-- ReplacingMergeTree + SELECT ... FINAL loại bản ghi trùng khi loader ghi lại (at-least-once).
CREATE DATABASE IF NOT EXISTS {db};

CREATE TABLE IF NOT EXISTS {db}.trades (
    trade_id     Int64,
    symbol       String,
    price        Decimal(18,8),
    qty          Decimal(18,8),
    trade_time   DateTime64(3, 'UTC'),
    ingested_at  DateTime64(6, 'UTC')  -- micro giây như Postgres: check.py dùng làm mốc đối chiếu chính xác
) ENGINE = ReplacingMergeTree
ORDER BY (symbol, trade_id);
