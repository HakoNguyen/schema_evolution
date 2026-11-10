-- OLTP nguồn: bảng trade của "sàn giao dịch" (schema v1, trước mọi kịch bản thay đổi).
CREATE TABLE IF NOT EXISTS trades (
    trade_id     BIGINT        NOT NULL,
    symbol       VARCHAR(20)   NOT NULL,
    price        NUMERIC(18,8) NOT NULL,
    qty          NUMERIC(18,8) NOT NULL,
    trade_time   TIMESTAMPTZ   NOT NULL,
    ingested_at  TIMESTAMPTZ   NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, trade_id)
);

-- Pipeline 2 (market_tickers): thống kê 24h của từng coin, cập nhật liên tục (UPSERT theo symbol).
CREATE TABLE IF NOT EXISTS tickers (
    symbol        VARCHAR(20)   PRIMARY KEY,
    last_price    NUMERIC(24,8),
    open_price    NUMERIC(24,8),
    high_price    NUMERIC(24,8),
    low_price     NUMERIC(24,8),
    base_volume   NUMERIC(28,8),
    quote_volume  NUMERIC(28,8),
    event_time    TIMESTAMPTZ   NOT NULL
);
