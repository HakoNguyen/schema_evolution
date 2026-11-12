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
  - users                       # bảng đích cùng tên
  - sales.orders                # Postgres: schema khác public -> bảng đích "orders"
  - source: sales.order_items   # bảng đích đặt tên khác nguồn
    target: order_items_raw
  # Có target: tên bảng đích chỉ gồm chữ, số, _ (đi thẳng vào ALTER TABLE). Nguồn tên "my-table"
  # thì ánh xạ: {source: my-table, target: my_table}.

# 4. CÁCH PHÁT HIỆN THAY ĐỔI (tuỳ chọn, mặc định polling theo scheduler.interval_seconds)
detection:
  mode: polling
  interval_seconds: 300         # chu kỳ quét riêng của pipeline này
```

**Engine không tạo bảng đích.** Lúc khai báo pipeline, bảng đích phải có sẵn và khớp nguồn (việc nạp dữ liệu ban đầu là của ETL). Lần quét đầu tiên engine lấy schema nguồn hiện tại làm baseline (v1), từ đó mới theo dõi thay đổi.

Tên bảng chỉ gồm chữ, số, `_ $ -` và tối đa một dấu chấm (`schema.table`), vì tên đi thẳng vào câu DDL. Hai bảng nguồn không được đổ vào cùng một bảng đích.

**Kiểu dữ liệu khi tự đồng bộ không làm mất dữ liệu.** Đã kiểm chứng trên Postgres, MySQL và Mongo thật:

| Nguồn | ClickHouse | MySQL (đích) | Lý do |
|---|---|---|---|
| `TIMESTAMP`, `TIMESTAMPTZ`, `DATETIME(n)` | `DateTime64(6)`, `DateTime64(6, 'UTC')` | `DATETIME(6)` | Giữ micro giây (`DateTime` thường làm mất phần dưới giây) |
| `NUMERIC` không ghi precision | `Decimal(76, 38)` | `DECIMAL(65,30)` | `Float64` làm tròn tiền; `DECIMAL` thường của MySQL là `(10,0)` |
| `DATE` | `Date32` | `DATE` | `Date` của ClickHouse chỉ từ năm 1970 |
| `CHAR(n)`, `VARCHAR(n)` | `String` | giữ nguyên | `FixedString(n)` đếm byte nên cắt chữ tiếng Việt |
| MySQL `INT UNSIGNED`, `BIGINT UNSIGNED` | `Int64`, `Decimal(20,0)` | | Lên kiểu có dấu rộng hơn một bậc, không tràn số |

Nếu DDL tự động chạy lỗi trên đích (sai quyền, kiểu không chuyển được), bảng **bị freeze và có cảnh báo** như một thay đổi breaking. Engine không báo "đã đồng bộ" khi đích thật ra chưa đổi.

**Nguồn MongoDB (không có schema):** kiểu cột được suy ra từ 10.000 document mới nhất. Field không có trong mẫu **không** bị coi là đã xóa, và mẫu toàn số nhỏ **không** bị coi là thu hẹp kiểu, nên không có freeze giả. Field là object/array lồng nhau được lưu dạng chuỗi JSON; field con mới bên trong không được theo dõi riêng.

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
- **Gõ mật khẩu thật trên Web UI cũng an toàn:** khi lưu, API tự chuyển giá trị vào `config/secrets.env` và YAML chỉ nhận tham chiếu. Tên biến theo vị trí: pipeline `shop_sales` + `source.config.password` thành `${SHOP_SALES_SOURCE_PASSWORD}`; `telegram.bot_token` trong `main.yaml` thành `${TELEGRAM_BOT_TOKEN}`. Lưu lại chỗ đó thì cập nhật đúng biến đó. Xóa pipeline thì biến vẫn nằm lại trong `secrets.env`, cần dọn tay.
- **Bí mật viết thẳng trong YAML kiểu cũ** vẫn chạy được, UI hiện `********`. Lần lưu tiếp theo qua UI sẽ chuyển nó sang `secrets.env`.

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
| `main.yaml` → `kafka`, `scheduler` | runtime | Các worker và Kafka consumer khởi động lại với giá trị mới. `scheduler.interval_seconds` là chu kỳ mặc định cho pipeline `polling` không khai báo `detection.interval_seconds`; pipeline `event_driven` dùng `fallback_polling_interval_seconds` của riêng nó |
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
> Engine tạo **một Kafka consumer cho mỗi cluster**. Consumer chỉ chuyển message tới worker của pipeline tương ứng, việc kiểm tra schema chạy trong worker đó. Vì vậy một pipeline chậm không làm chậm các pipeline khác dùng chung cluster. Thêm hoặc bớt pipeline thì consumer tự cập nhật danh sách topic. Nhiều pipeline có thể dùng chung một `topic` (cùng một Debezium connector): message được chuyển tới **mọi** pipeline có khai báo bảng đó trong `tables`, pipeline không khai báo thì bỏ qua.

> [!IMPORTANT]
> **Message phải là JSON** (`value.converter=org.apache.kafka.connect.json.JsonConverter`). Nên bật `value.converter.schemas.enable=true`: khi đó cả thay đổi kiểu (độ dài, precision) cũng được phát hiện trong khoảng 2 giây. Không có schema thì chỉ thêm, xóa, đổi tên cột được phát hiện ngay; đổi kiểu phải chờ lần quét dự phòng. Avro/Protobuf (Schema Registry) chưa được hỗ trợ: engine ghi **một** cảnh báo cho mỗi topic và topic đó chỉ còn được phát hiện qua quét dự phòng.

**Lịch sử sự kiện** (Live CDC Event Stream, các lần Approve/Reject) được lưu vào `<registry.dir>/_events.jsonl`, nên khởi động lại backend không mất timeline.

### C. Chạy engine
Engine tự chạy cùng API server (`uvicorn api.main:app --port 8000`). Muốn chạy engine độc lập, không kèm API:
```powershell
python -m app.scheduler   # PipelineManager: quét định kỳ + Kafka consumer cho mọi pipeline
```

---

## 4. Tích hợp data plane (loader, Kafka Connect, Spark job...)

Engine chỉ quản lý **schema** (control plane). Thành phần ghi dữ liệu (data plane) do bạn tự chọn, và giao tiếp với engine qua 2 API. Engine không cần biết bên trong các thành phần đó.

### Gate API: được ghi hay phải dừng?
```http
GET /api/gate/{pipeline}/{table}
→ {"state": "open" | "frozen", "schema_version": 3,
   "pending_changes": [{"change_type": "rename_column", "column": "qty"}],
   "column_renames": {"qty": "quantity"}}
```
- `frozen`: có thay đổi breaking đang chờ duyệt. **Dừng ghi** bảng đó (giữ dữ liệu trong hàng đợi, không commit offset) cho tới khi trạng thái trở về `open`.
- `column_renames`: các lần đổi tên đã duyệt. Message cũ còn trong hàng đợi vẫn mang tên cột cũ, nên phải ghi vào cột tên mới.
- Không gọi được API thì nên **giữ trạng thái đã biết gần nhất** (fail-static).

### Reporting API: báo trạng thái để hiện trên UI (không bắt buộc)
```http
POST /api/pipelines/{pipeline}/components/{name}
{"state": "running", "role": "warehouse sink",
 "metrics": {"rows_per_sec": 512.3, "lag_seconds": 1.6}, "message": ""}
```
- `state` gợi ý: `running` / `ok` (xanh), `hold` / `paused` (vàng), `failed` / `error` (đỏ). Thành phần im lặng quá 15 giây sẽ hiện là `stale`.
- `metrics`: tối đa 30 giá trị đơn (số, chuỗi, bool). Trang **Pipelines Overview** hiển thị nguyên các giá trị này; chỉ số `rows_per_sec` có thêm sparkline.
- Ví dụ hoàn chỉnh: [`demo/loader.py`](demo/loader.py) (`Reporter`, `FreezeGate`) và [`demo/check.py`](demo/check.py) (`report`).
- Khi engine bật xác thực (mục 6), gửi kèm `Authorization: Bearer <token vai reporter>`. Loader demo đọc token từ biến môi trường `DEMO_ENGINE_TOKEN`.

---

## 5. Sink có sẵn, không sửa được code (khai báo `components:`)

Gate API và Reporting API cần sửa code của sink. Với sink có sẵn như Kafka Connect, bạn chỉ cần khai báo trong YAML của pipeline:

```yaml
# config/pipelines/market_trades.yaml
components:
  - name: trades-sink                       # tên hiện trên Pipelines Overview
    role: warehouse sink                    # tuỳ chọn
    tables: [trades]                        # tuỳ chọn, mặc định là mọi bảng của pipeline
    kafka_group: connect-trades-sink        # engine tự đo consumer lag (Kafka Connect: connect-<tên connector>)
    kafka_connect:                          # engine tự pause/resume connector theo freeze
      url: http://localhost:8083
      connector: trades-sink
  - name: spark-job                         # chỉ khai báo, tự báo cáo qua Reporting API
    role: batch sink
```

- **Chỉ khai báo:** nếu chưa từng báo cáo thì component hiện `missing` (đỏ), thay vì không hiện gì.
- **`kafka_group`:** khoảng 2 giây một lần, engine đọc lag và trạng thái group (`Stable` → `running`, `Empty` → `stopped`). Lag là tổng trên mọi partition group đang được giao hoặc đã commit. Partition chưa commit lần nào được tính từ đầu log, giống `rpk group describe`. Kafka lấy theo `detection.kafka` hoặc `kafka` trong `main.yaml`. Kafka Connect chỉ commit offset định kỳ (`offset.flush.interval.ms`, mặc định 60 giây), nên lag của sink Connect nhảy theo từng bậc.
- **`kafka_connect`:**
  - Có bảng nào trong `tables` bị freeze thì engine `PUT /connectors/{name}/pause`. Mọi bảng mở lại thì `PUT .../resume`.
  - Task bị `FAILED` lúc đang freeze sẽ được restart khi resume (`POST .../restart?includeTasks=true&onlyFailed=true`).
  - Engine vừa tự `ALTER` bảng đích của component (thay đổi không breaking) thì trong 30 giây sau đó, task FAILED được restart một lần. Lý do: sink có thể nhận message schema mới trước khi `ALTER` xong.
  - Khoảng 2 giây một lần, engine đối chiếu trạng thái thật của connector. Vì vậy cách gỡ freeze nào cũng có tác dụng: approve, reject, nguồn tự rollback, `unfreeze_cli`. Engine khởi động lại cũng không ảnh hưởng.
  - Không gọi được Kafka Connect trong lúc bảng đang freeze thì engine gửi cảnh báo Telegram 1 lần và ghi vào Live Events.
- **Mỗi connector chỉ khai báo ở một pipeline, và một lần.** Nếu hai pipeline cùng điều khiển một connector, chúng sẽ pause và resume ngược nhau liên tục (đã thấy khi chạy thật). File nạp sau sẽ bị báo lỗi cấu hình. Một connector ghi bảng của hai pipeline thì nên tách thành hai connector, hoặc gom các bảng vào một pipeline.
- **Engine giữ quyền điều khiển connector đã khai báo.** Đừng resume tay khi bảng đang freeze, vì engine sẽ pause lại. Muốn tự điều khiển thì xoá mục `kafka_connect` khỏi YAML.
- Nên đặt `errors.tolerance=none` cho sink. Từ lúc nguồn đổi schema tới lúc pause (đo được dưới 1 giây) có thể có message schema mới lọt vào sink. Với `none`, task sẽ `FAILED` và giữ offset (được restart khi resume). Với `all`, message đó bị bỏ qua và mất.
- Kiểm chứng ngày 11/11/2026 với JDBC sink thật trên Kafka Connect 3.8:
  - Lúc mở: sink ghi khoảng 3.700 dòng/giây.
  - Freeze: connector bị pause sau 0,17 giây, ghi 0 dòng trong 10 giây.
  - Gỡ freeze: connector chạy lại sau 1,54 giây và ghi tiếp.

**Sink ghi vào bảng có schema cố định (như JDBC sink).** Mẫu dùng trong demo (pipeline `market_tickers_replica`):
- Đặt `schema.evolution: none` cho sink.
- Tạo một pipeline có `target` chính là DB của sink, để engine tự quản lý schema bảng đó (tự `ALTER` khi không breaking, chờ duyệt khi breaking).

Mẫu này đã chạy thật với `add_column`, `widen` và `DROP COLUMN` (cả rollback lẫn approve).

**Hạn chế: RENAME với sink có schema cố định.** Kafka Connect chỉ commit offset định kỳ, nên sau khi resume, sink đọc lại các message trước lúc đổi tên, vẫn mang tên cột cũ. Bảng đích đã đổi tên, nên task chết. Loader tự viết thì tránh được nhờ `column_renames` của Gate API. Với Kafka Connect thì chưa có cách tự động:
- SMT `ReplaceField` không giúp được khi nguồn là Debezium bật `column.propagate.source.type`. Mỗi field mang tham số `__debezium.source.column.name` giữ tên cũ, và Debezium JDBC sink lấy tên cột từ tham số đó (đã kiểm chứng).
- **Cách xử lý tay:** khi duyệt RENAME, thay vì đổi tên trên bảng của sink, hãy thêm cột mới và giữ cột cũ (cho phép NULL). Khi sink đã xử lý hết message cũ (lag về 0), chép dữ liệu từ cột cũ sang cột mới rồi xoá cột cũ.
- Để engine tự làm việc này (migration expand/contract) là việc để sau.

---

## 6. Xác thực API (tuỳ chọn)

Chưa khai báo `auth` thì API mở như trước. Khai báo `auth` trong `config/main.yaml` (nạp lại khi đang chạy) thì:

```yaml
auth:
  users:
    hieu:                                    # tên này được ghi vào lịch sử duyệt và Telegram
      role: admin                            # mọi lệnh ghi: approve, reject, sandbox, sửa cấu hình
      token: ${AUTH_USERS_HIEU_TOKEN}
    loader:
      role: reporter                         # chỉ Reporting API, dùng cho data plane
      token: ${AUTH_USERS_LOADER_TOKEN}
```

- Lệnh ghi (POST, PUT, DELETE) cần header `Authorization: Bearer <token>`. Thiếu hoặc sai token thì trả 401. Token `reporter` gọi lệnh khác thì trả 403.
- Lệnh đọc (GET), gồm cả Gate API và giao diện, vẫn mở.
- Token dài ít nhất 16 ký tự, mỗi người một token. Đặt `${VAR}` trong khối `{...}` thì phải có dấu nháy: `token: '${VAR}'`.
- Trên giao diện, lần đầu bấm Approve, Reject hay Save sẽ có hộp thoại hỏi token. Token được lưu trong trình duyệt.
- Approve và Reject ghi `by <tên>` vào Live Events (lưu trong `_events.jsonl`) và vào tin Telegram. `unfreeze_cli` ghi tên user hệ điều hành.
- Trạng thái component được lưu vào `<registry.dir>/_components.json`, nên khởi động lại vẫn thấy trạng thái cuối (hiện `stale` cho tới khi có báo cáo mới).

---

## 7. Nâng cấp từ bản trước mức 1 (commit `b0596aa`)

Mức 1 đổi cách chuẩn hoá một số kiểu của **nguồn MySQL và MongoDB**, để dữ liệu sang đích không bị sai:

| Nguồn | Kiểu cũ trong baseline | Kiểu mới |
|---|---|---|
| MySQL `INT UNSIGNED` | `int` | `bigint` |
| MySQL `BIGINT UNSIGNED` | `bigint` | `numeric(20,0)` |
| MySQL `MEDIUMINT` | `mediumint` | `int` |
| Mongo field có cả int và double (hoặc int32 và int64) | `json` | `double` (hoặc `bigint`) |

Baseline tạo trước bản này sẽ thấy các cột trên "đổi kiểu" ở lần quét đầu tiên:
- `INT UNSIGNED` (`int` → `bigint`) là nới rộng, nên engine tự `ALTER` đích. Đó cũng chính là bản sửa lỗi `4294967295` thành `-1`.
- Ba trường hợp còn lại bị phân loại là đổi kiểu không tương thích, nên bảng bị freeze để chờ duyệt một lần. Freeze là hướng an toàn, không mất dữ liệu. Bạn có thể Approve (sau sandbox) hoặc xoá baseline của bảng đó trong `registry.dir` để engine khởi tạo lại.

Nguồn Postgres không bị ảnh hưởng.
