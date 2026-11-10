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
**Bước 3:** Lưu file. Trong khoảng 3 giây, engine tự nạp lại pipeline và bắt đầu theo dõi bảng mới, không cần khởi động lại.

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
    password: "${PROD_MYSQL_PASSWORD}"   # giá trị thật trong config/secrets.env (xem mục Bí mật)
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
> Không cần khởi động lại API server. **PipelineManager** ([`app/pipeline_manager.py`](app/pipeline_manager.py)) quét `config/pipelines/` mỗi 3 giây:
> - **File mới:** bắt đầu theo dõi. **File bị sửa:** nạp lại pipeline đó. **File bị xoá:** dừng theo dõi.
> - Mỗi pipeline chạy trên **worker riêng** (luồng xử lý và kết nối DB riêng). Pipeline A lỗi (DB sập, cấu hình sai) không ảnh hưởng pipeline B.
> - **File cấu hình lỗi** (YAML hỏng, `type` không hỗ trợ, thiếu `tables`, trùng `name`) chỉ khiến pipeline đó không được theo dõi. Lỗi hiện trên trang Topology và Configuration kèm lý do cụ thể.

### Bí mật (mật khẩu DB, token Telegram, mật khẩu Kafka SASL)

**Không ghi bí mật thật vào file YAML**, vì các file này được commit lên git. Làm giống Docker Compose và Kafka Connect: trong YAML chỉ ghi **tham chiếu**, còn giá trị thật để ở chỗ khác.

```yaml
# config/pipelines/market_trades.yaml  (được commit)
source:
  config:
    password: ${EXCHANGE_PG_PASSWORD}
```
```ini
# config/secrets.env  (đã gitignore — copy từ config/secrets.env.example)
EXCHANGE_PG_PASSWORD=password123
TELEGRAM_BOT_TOKEN=123456:ABC...
```

- **Thứ tự ưu tiên:** biến môi trường thật cùng tên, rồi đến `config/secrets.env`. Trên server, đặt biến môi trường là đủ, không cần file.
- **Engine chỉ thay giá trị thật lúc tạo kết nối.** Giá trị thật không bao giờ bị ghi ngược ra YAML, và API/UI chỉ thấy `${...}`.
- **Thiếu biến** (ví dụ chưa khai báo `EXCHANGE_PG_PASSWORD`): chỉ pipeline đó báo lỗi `missing secret(s): ...`, các pipeline khác vẫn chạy. Khi lưu qua UI, tham chiếu tới biến chưa có cũng bị chặn.
- **Sửa `secrets.env` có hiệu lực trong khoảng 3 giây**, không cần khởi động lại. Chỉ những pipeline dùng biến vừa đổi mới được nạp lại.
- **Bí mật viết thẳng kiểu cũ** vẫn chạy được, nhưng UI sẽ hiện `********`. Lưu lại mà không sửa thì giá trị cũ được giữ nguyên, không bị ghi thành chuỗi `********`.

### Sửa cấu hình qua Web UI (trang Configuration)

Mọi thao tác Lưu đều được **kiểm tra trước khi ghi file**, bằng đúng bộ luật mà engine dùng khi nạp cấu hình. Cấu hình sai thì không ghi, và form liệt kê từng lỗi, ví dụ `source.config.host: required` hay `target.config.port: required for clickhouse`.

- **Thông tin kết nối được kiểm tra theo từng engine:** Postgres dùng `dbname` (chấp nhận `database` như tên cũ, nhưng không được có cả hai), MySQL/ClickHouse/Mongo dùng `database`, ClickHouse và Mongo bắt buộc có `port`.
- **Form chỉ ghi đè những trường nó hiển thị.** Mọi trường khác trong file (ví dụ `bootstrap_servers`, `fallback_polling_interval_seconds`, tham số kết nối riêng) được giữ nguyên.
- **Không đổi được tên pipeline**, vì lịch sử schema và trạng thái freeze được lưu theo tên. Muốn đổi tên thì tạo pipeline mới rồi xóa pipeline cũ.
- **Tên pipeline** chỉ gồm chữ, số, `_` và `-` (tên được dùng làm tên file, nên chặn các ký tự như `../`). Không cho tạo trùng tên với pipeline đã có.
- **File được ghi nguyên tử** (ghi ra file tạm rồi đổi tên), nên engine không bao giờ đọc phải file đang ghi dở.
- Hạn chế: lưu qua UI sẽ **làm mất các dòng comment** trong file YAML. Muốn giữ comment thì sửa trực tiếp trong file.

### Cấu hình nào tự áp dụng, cấu hình nào cần khởi động lại

Theo cách Prometheus, Nginx và Airflow làm, cấu hình được chia hai loại: **runtime** (áp dụng trong khoảng 3 giây, không cần khởi động lại) và **bootstrap** (gắn với nơi lưu trữ trạng thái, phải khởi động lại).

| Cấu hình | Loại | Khi bạn sửa và lưu file |
|---|---|---|
| `config/pipelines/*.yaml` | runtime | Pipeline mới chạy, pipeline sửa nạp lại, pipeline xoá dừng |
| `main.yaml` → `telegram` | runtime | Dùng token/chat mới ngay, không động tới worker |
| `main.yaml` → `kafka`, `scheduler` | runtime | Các worker và Kafka consumer khởi động lại với giá trị mới. `scheduler.interval_seconds` chỉ áp dụng cho pipeline `polling`; pipeline `event_driven` dùng `fallback_polling_interval_seconds` của riêng nó |
| `main.yaml` → `registry.dir` | **bootstrap** | **Không áp dụng** khi đang chạy (đổi chỗ lưu trạng thái giữa chừng có thể làm mất trạng thái freeze/draft). UI báo "needs a restart". Khởi động lại backend để áp dụng |

**File mới bị lỗi thì giữ cấu hình cũ (last-known-good):** nếu `main.yaml` bị gõ hỏng, engine **tiếp tục chạy bằng cấu hình hợp lệ gần nhất**, và UI hiện thẻ "main: Config error" kèm lý do. Sửa lại file là lỗi tự biến mất. Lúc **khởi động** mà `main.yaml` đã lỗi thì engine dừng và báo lỗi rõ ràng, vì khi đó chưa có cấu hình nào chạy tốt để giữ lại.

**Khởi động lại backend** (chỉ cần khi đổi `registry.dir`): vào terminal đang chạy `uvicorn api.main:app --port 8000` (cửa sổ tên **backend** nếu dùng `demo\start.ps1`), bấm **Ctrl+C**, rồi chạy lại lệnh đó. Dữ liệu không mất, nhưng mất khoảng 30 đến 60 giây đầu để Kafka consumer ổn định lại.

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
detection:
  mode: event_driven
  kafka:                                     # phải nằm TRONG detection (đặt ở ngoài sẽ bị bỏ qua)
    bootstrap_servers: "192.168.1.50:9092"   # Trỏ riêng tới Kafka Cluster của chi nhánh
    group_id: "pg-cluster-group"
    topic: "pg_to_mysql"                     # = topic.prefix của Debezium connector
  fallback_polling_interval_seconds: 60      # vẫn quét định kỳ phòng khi lỡ event

source:
  type: "postgres"
  ...
```

> [!NOTE]
> Engine tạo **một Kafka consumer cho mỗi cluster**. Consumer chỉ chuyển message tới worker của pipeline tương ứng, việc kiểm tra schema chạy trong worker đó. Vì vậy một pipeline chậm không làm chậm các pipeline khác dùng chung cluster. Thêm hoặc bớt pipeline thì consumer tự cập nhật danh sách topic.

### C. Chạy engine
Engine tự chạy cùng API server (`uvicorn api.main:app --port 8000`). Muốn chạy engine độc lập, không kèm API:
```powershell
python -m app.scheduler   # PipelineManager: quét định kỳ + Kafka consumer cho mọi pipeline
```
