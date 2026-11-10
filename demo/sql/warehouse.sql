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

-- Pipeline 2 (market_tickers): bản mới nhất theo symbol (ReplacingMergeTree giữ event_time lớn nhất).
CREATE TABLE IF NOT EXISTS {db}.tickers (
    symbol        String,
    last_price    Nullable(Decimal(24,8)),
    open_price    Nullable(Decimal(24,8)),
    high_price    Nullable(Decimal(24,8)),
    low_price     Nullable(Decimal(24,8)),
    base_volume   Nullable(Decimal(28,8)),
    quote_volume  Nullable(Decimal(28,8)),
    event_time    DateTime64(3, 'UTC')
) ENGINE = ReplacingMergeTree(event_time)
ORDER BY symbol;
