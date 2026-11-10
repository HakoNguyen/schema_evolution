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
