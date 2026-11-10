# Hướng dẫn Cấu hình Hệ thống (Config-as-Code)

Hệ thống Schema Evolution sử dụng cơ chế **Config-as-Code** tương tự như các nền tảng Data Engineering hiện đại (Airbyte, dbt, Debezium). Mọi luồng đồng bộ (pipeline) đều được khai báo thông qua các file `.yaml`.

Cấu trúc thư mục cấu hình nằm tại `config/`:
```text
config/
├── main.yaml                # Cấu hình lõi (Scheduler, Telegram bot)
└── pipelines/               # Chứa các file khai báo luồng đồng bộ
    ├── pg_to_mysql.yaml
    ├── mongo_to_clickhouse.yaml
    └── ...
```

---

## 1. Thêm Bảng vào Pipeline Đã Có

Nếu bạn muốn hệ thống theo dõi thêm một bảng mới trên một Data Pipeline đã được cấu hình sẵn (ví dụ: thêm bảng `products` vào luồng Postgres -> MySQL).

**Bước 1:** Mở file cấu hình tương ứng, ví dụ `config/pipelines/pg_to_mysql.yaml`.
**Bước 2:** Cuộn xuống danh sách `tables:` và thêm tên bảng mới vào:
```diff
 tables:
   - customers
   - orders
+  - products
```
**Bước 3:** Lưu file. Hệ thống (Scheduler) sẽ tự động nhận diện và cập nhật cấu trúc bảng mới lên giao diện Web ở chu kỳ quét tiếp theo (mặc định 60s).

---

## 2. Tạo Pipeline Đồng bộ Mới

Nếu bạn vừa dựng một Database mới và muốn thiết lập một luồng đồng bộ hoàn toàn mới (Ví dụ: Từ `Oracle` sang `Snowflake`, hoặc tự giám sát một cụm `MySQL` mới).

**Bước 1:** Tạo một file `.yaml` mới bên trong thư mục `config/pipelines/`. Đặt tên tùy ý, ví dụ: `mysql_production_monitor.yaml`.
**Bước 2:** Copy form mẫu sau và điền thông số kết nối:

```yaml
# Tên hiển thị của Pipeline trên giao diện và Telegram
name: "mysql_production_monitor"

# 1. CẤU HÌNH DATABASE NGUỒN (Bắt buộc)
source:
  type: "mysql" # Hỗ trợ: postgres, mysql, mongodb, clickhouse
  config:
    host: "192.168.1.100"
    port: 3306
    user: "admin"
    password: "secret_password"
    database: "production_db"

# 2. CẤU HÌNH DATABASE ĐÍCH (Tuỳ chọn)
# Nếu bạn bỏ qua phần 'target' này, hệ thống sẽ chạy ở chế độ 
# "Chỉ giám sát cảnh báo" (Self-monitor) mà không tự động chạy lệnh DDL.
target:
  type: "clickhouse"
  config:
    host: "10.0.0.5"
    port: 8123
    user: "default"
    password: ""
    database: "default"

# 3. DANH SÁCH BẢNG CẦN THEO DÕI
tables:
  - users
  - payments
```

> [!TIP]
> Bạn không cần khởi động lại API server. `scheduler.py` sẽ tự động phát hiện file `.yaml` mới của bạn và bắt đầu đồng bộ ngay lập tức!

> [!WARNING]
> Lưu ý từ khoá tên Database giữa các Engine:
> - Postgres dùng: `dbname`
> - MySQL, ClickHouse, Mongo dùng: `database`

---

## 3. Cấu hình Kết nối Kafka & Multi-Cluster CDC Events

Hệ thống Schema Evolution tích hợp cơ chế lắng nghe sự kiện CDC Real-time thông qua Kafka / Redpanda Bus.

### A. Cấu hình Kafka Mặc định (`config/main.yaml`)
Bạn có thể trỏ địa chỉ Kafka Broker về Server địa phương hoặc Server ở xa trong file `config/main.yaml`:

```yaml
kafka:
  # Địa chỉ Kafka Broker (có thể khai báo 1 IP hoặc cụm cluster cách nhau bởi dấu phẩy)
  bootstrap_servers: "localhost:19092"
  group_id: "schema-evolution-group"

  # (Tùy chọn) Bổ sung nếu Kafka Server ở xa bật bảo mật SASL/SSL
  # security_protocol: "SASL_PLAINTEXT"
  # sasl_mechanism: "PLAIN"
  # sasl_plain_username: "my_user"
  # sasl_plain_password: "my_password"
```

### B. Cấu hình Kết nối Nhiều Kafka Cluster Cùng Lúc (Multi-Kafka Cluster)
Nếu hệ thống của bạn cần đồng bộ dữ liệu từ **nhiều cụm Kafka Server khác nhau** (ví dụ: Cluster A tại Hà Nội, Cluster B tại TP.HCM), bạn chỉ cần khai báo đè mục `kafka:` vào từng file pipeline riêng biệt trong `config/pipelines/<pipeline_name>.yaml`:

```yaml
name: "pg_to_mysql"
kafka:
  bootstrap_servers: "192.168.1.50:9092"   # Trỏ riêng tới Kafka Cluster của chi nhánh
  group_id: "pg-cluster-group"

source:
  type: "postgres"
  ...
```

> [!NOTE]
> Khi chạy `python -m app.kafka_consumer`, hệ thống sẽ tự động phân nhóm và khởi tạo các **Thread Worker độc lập** để lắng nghe song song đồng thời từ tất cả các Kafka Cluster mà bạn đã khai báo!

### C. Khởi chạy Kafka Consumer Background Worker
```powershell
python -m app.kafka_consumer
```
