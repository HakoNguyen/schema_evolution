-- init_clickhouse.sql
-- Tạo bảng "users" bên ClickHouse khớp đúng cấu trúc baseline của Mongo
-- (init_mongo_source.js) — để lần quét đầu tiên coi đây là trạng thái
-- "đã đồng bộ", sau đó mọi thay đổi ở Mongo sẽ được tự động ALTER lên
-- bảng này.
--
-- Cách chạy (đứng ngoài container, dùng client HTTP hoặc clickhouse-client):
--
--   Cách 1 - qua HTTP interface (curl):
--     cat init_clickhouse.sql | curl 'http://localhost:8123/' --data-binary @-
--
--   Cách 2 - exec vào container:
--     docker cp init_clickhouse.sql clickhouse_db:/tmp/init_clickhouse.sql
--     docker exec -it clickhouse_db clickhouse-client --multiquery --queries-file /tmp/init_clickhouse.sql

DROP TABLE IF EXISTS users;

CREATE TABLE users
(
    _id       String,
    name      String,
    email     String,
    age       Int32,
    is_vip    Bool,
    created_at DateTime
)
ENGINE = MergeTree()
ORDER BY _id;

-- Lưu ý: _id ở đây là String vì ObjectId của Mongo được mongo.py chuẩn
-- hoá về 'text' (xem _infer_type trong mongo.py), tương ứng String bên
-- ClickHouse (xem NORMALIZED_TO_CLICKHOUSE trong clickhouse.py).
--
-- KHÔNG cần insert data mẫu vào đây — crawl_metadata() chỉ cần cấu trúc
-- cột, không cần data thật để hoạt động (khác với Mongo, nơi bắt buộc
-- phải có document thật để sample suy luận type).
