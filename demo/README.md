# Demo: pipeline giao dịch crypto realtime

Bộ demo dùng **dữ liệu thật**: trade từ Binance WebSocket chảy liên tục qua CDC vào data warehouse.
Trong lúc dữ liệu đang chảy, ta thay đổi schema của nguồn để chứng minh ba điều:

1. Thay đổi an toàn (non-breaking) được engine đồng bộ sang warehouse một cách tự động.
2. Thay đổi nguy hiểm (breaking) bị chặn lại để chờ người duyệt.
3. **Không mất dòng dữ liệu nào** trong suốt quá trình.

> Trạng thái: **Phase 0 đến 3 đã xong** (cập nhật 10/11/2026). Xem [Lộ trình](#lộ-trình) ở cuối file.

---

## Kiến trúc

```
Binance WebSocket ──► ingestor ──► Postgres  exchange.public.trades      (OLTP nguồn)
 (trade thật)                          │ Debezium (pgoutput, slot market_slot)
                                       ▼
                                  Redpanda  topic market.public.trades
                        ┌──────────────┴──────────────┐
                        ▼                              ▼
         Schema Evolution Engine              loader ──► ClickHouse  analytics.trades
         (control plane: fingerprint ->         ▲          (warehouse)
          crawl nguồn, phân loại,               │  PAUSE khi bảng bị freeze
          ALTER đích, freeze) ─ ALTER TABLE ────┘  HOLD khi đích thiếu cột

                                  Redpanda ──► loader --naive ──► ClickHouse analytics_naive.trades
                                  (đối chứng: sink thông thường, không có engine -> vỡ khi có ADD COLUMN)
```

| File | Vai trò |
|---|---|
| [`config.py`](config.py) | Thông tin kết nối dùng chung (host, port, topic, tên connector) |
| [`sql/source.sql`](sql/source.sql) | Bảng `trades` ở nguồn Postgres, schema v1 |
| [`sql/warehouse.sql`](sql/warehouse.sql) | Bảng `analytics.trades` ở ClickHouse, schema v1 |
| [`connector.json`](connector.json) | Cấu hình Debezium Postgres connector |
| [`setup.py`](setup.py) | Tạo DB, bảng và connector. Thêm `--reset` để xóa sạch rồi dựng lại |
| [`ingestor.py`](ingestor.py) | Binance → Postgres. Có `--record` (ghi lại) và `--replay` (phát lại) |
| [`loader.py`](loader.py) | Kafka → ClickHouse (data plane). Có `--naive` cho pipeline đối chứng |
| [`check.py`](check.py) | Đối chiếu nguồn với đích: số dòng, mất dòng, độ trễ, kèm pipeline đối chứng |
| [`scenario.py`](scenario.py) | Các bước kịch bản: chạy `ALTER` trên nguồn và đo thời gian engine phản ứng |
| [`bench.py`](bench.py) | Đo cho báo cáo: `schema` (lặp N lần, p50/p95) và `soak` (chạy liên tục M phút) |
| [`results/`](results/) | Kết quả đo dạng JSON, dùng làm bằng chứng cho báo cáo |
| [`start.ps1`](start.ps1) | Khởi động toàn bộ demo bằng một lệnh, mỗi tiến trình một cửa sổ |
| Gate API `GET /api/gate/market_trades/trades` | Loader hỏi engine bảng đang `open` hay `frozen` (kèm `column_renames`) trước khi ghi |
| Reporting API `POST /api/pipelines/market_trades/components/<tên>` | `loader`, `naive-loader`, `reconciler` (`check --report`) tự báo trạng thái + chỉ số để hiện trên UI |
| [`../frontend/src/components/PipelinesOverview.jsx`](../frontend/src/components/PipelinesOverview.jsx) | Trang **Pipelines Overview**: mọi pipeline + thành phần tự báo cáo, là màn hình chính của buổi demo |
| [`../config/pipelines/market_trades.yaml`](../config/pipelines/market_trades.yaml) | Khai báo pipeline cho engine |

---

## Chạy demo

**Cách nhanh (dùng cho ngày demo):** bật Docker Desktop, rồi chạy

```powershell
powershell -ExecutionPolicy Bypass -File demo\start.ps1 -Reset
# mất mạng: thêm  -Replay demo\recordings\binance_trades.jsonl
```

Script này bật hạ tầng, reset về schema v1, rồi mở 6 cửa sổ: backend, frontend, ingestor, loader, naive-loader và check. **Backend được bật trước** để consumer group của engine ổn định trước khi dữ liệu chảy vào. Sau đó **chờ khoảng 60 giây** rồi mới mở http://localhost:5173.

**Cách thủ công:** mọi lệnh chạy từ thư mục gốc repo, với venv đã kích hoạt (`.\venv\Scripts\Activate.ps1`). Cài thư viện bằng `pip install -r requirements.txt`. **Bắt buộc phải có `crc32c`**, xem phần [Kết quả phase 4](#kết-quả-phase-4-đo-đạc-và-tập-dượt).

```powershell
# 1. Hạ tầng. Chỉ cần Postgres, ClickHouse và stack Redpanda/Debezium
docker compose up -d postgres_db clickhouse_db
docker compose -f debezium/docker-compose.yml up -d

# 2. Tạo DB, bảng và connector. Chạy lại nhiều lần không sao
python -m demo.setup

# 3. Mỗi lệnh dưới đây chạy trong một terminal riêng, theo đúng thứ tự (backend trước)
uvicorn api.main:app --port 8000         # engine + API
cd frontend; npm run dev                 # UI tại http://localhost:5173
python -m demo.ingestor                  # trade thật -> Postgres
python -m demo.loader                    # Kafka -> ClickHouse (có engine bảo vệ)
python -m demo.loader --naive            # pipeline đối chứng (không có engine)
python -m demo.check --watch --report    # đối chiếu mỗi 2s, báo lên engine (hiện trên UI)
```

Các trang hữu ích:
- Redpanda Console (xem message CDC): http://localhost:8086
- Debezium Connect: http://localhost:8083/connectors/market-trades-source/status

### Cảnh báo Telegram khi có thay đổi breaking (tùy chọn)

1. Trên Telegram, chat với **@BotFather**, gõ `/newbot` để lấy token. Sau đó nhắn một tin bất kỳ cho bot vừa tạo.
2. Lấy `chat_id` của bạn: mở `https://api.telegram.org/bot<TOKEN>/getUpdates`, tìm `"chat":{"id":...}`.
3. Ghi vào **`config/secrets.env`** (đã gitignore; copy từ `config/secrets.env.example` nếu chưa có file):
   ```ini
   TELEGRAM_BOT_TOKEN=<token>
   TELEGRAM_CHAT_ID=<chat_id>
   ```
   `config/main.yaml` chỉ tham chiếu `${TELEGRAM_BOT_TOKEN}`. Engine tự áp dụng trong khoảng 3 giây, không cần khởi động lại.

Không đặt token cũng không sao: engine sẽ bỏ qua bước gửi cảnh báo, không làm chậm luồng xử lý. **Không ghi token thẳng vào `config/main.yaml`**, vì file này được commit lên git.

### Đưa về trạng thái sạch (trước mỗi lần tập dượt)

Tắt ingestor, loader và backend trước, rồi chạy:

```powershell
python -m demo.setup --reset
```

Lệnh này xóa: connector, replication slot, DB `exchange`, DB `analytics`, topic CDC, consumer group của loader, và registry của pipeline. Sau đó dựng lại schema v1.

### Dự phòng mất mạng: ghi lại rồi phát lại

```powershell
python -m demo.ingestor --record demo/recordings/binance_trades.jsonl   # ghi trong lúc chạy live
python -m demo.ingestor --replay demo/recordings/binance_trades.jsonl   # phát lại với tốc độ thật
python -m demo.ingestor --replay demo/recordings/binance_trades.jsonl --speed 5
```

- Khi replay, `trade_time` được dời về thời điểm hiện tại, nên độ trễ trên dashboard trông giống dữ liệu live.
- Phải chạy `--reset` trước khi replay lại cùng một file. `trade_id` trùng sẽ bị `ON CONFLICT DO NOTHING` bỏ qua.
- Thư mục `demo/recordings/` không được đưa lên git (xem `.gitignore`). Nên ghi khoảng 1 giờ dữ liệu trước ngày demo.
- Nếu `data-stream.binance.vision` bị chặn, dùng tham số `--ws wss://stream.binance.com:9443`.

---

## Cơ chế đảm bảo dữ liệu

**Ingestor thích ứng với schema.** Mỗi trade được ánh xạ ra *mọi* trường mà ứng dụng biết, gồm `qty` và `quantity`, `is_buyer_maker`, `quote_qty`. Nhưng câu INSERT chỉ ghi những cột **đang có** trong bảng; danh sách cột được đọc lại mỗi 2 giây và ngay khi gặp lỗi `UndefinedColumn`. Vì vậy `ALTER TABLE ... ADD COLUMN` hay `RENAME COLUMN qty TO quantity` có hiệu lực ngay, giống một ứng dụng thật vừa deploy phiên bản mới, mà không phải khởi động lại ingestor.

**Engine chỉ phản ứng khi schema thực sự đổi (fingerprint).** Kafka consumer của engine hash phần `schema.after` của mỗi message Debezium. Chỉ khi hash này khác lần trước thì engine mới crawl lại nguồn và chạy `run_evolution_check`. Trước đây engine crawl metadata với **mọi** message; giờ chỉ crawl **1 lần cho mỗi lần thay đổi schema** (đã đo: 288 message thì chỉ có 1 lần kiểm tra). Quét định kỳ 60 giây vẫn chạy để làm lưới an toàn.

**Loader tạm dừng (PAUSE) khi bảng bị freeze.** Loader đọc trạng thái `is_frozen` trong registry. Khi engine đóng băng bảng vì một thay đổi breaking, loader ngừng ghi và ngừng commit, toàn bộ dữ liệu được giữ trong Kafka cho tới khi Approve, Reject, hoặc rollback. Cơ chế này cần cho các thay đổi **không** làm phát sinh cột mới, như DROP hoặc thu hẹp kiểu, là những trường hợp mà HOLD không bắt được.

**Engine tự gỡ freeze khi nguồn quay về baseline.** Nếu bảng đang bị freeze mà nguồn đã khớp lại với baseline (dev rollback), engine bỏ draft và gỡ freeze (`resolved_at_source`). Trước bản sửa này, bảng bị **đóng băng vĩnh viễn** với một draft đã lỗi thời.

**Loader chờ (HOLD) thay vì bỏ cột.** Nếu message có cột mà bảng đích chưa có, loader:
1. **không** bỏ cột đó đi và **không** commit offset;
2. dừng lại và in log `HOLD`, kiểm tra lại schema đích mỗi giây;
3. khi engine đã `ALTER` xong bảng đích thì in `RESUME` và xử lý tiếp. Message trong lúc chờ vẫn nằm an toàn trong Kafka.

**Ghi ít nhất một lần (at-least-once) và loại bản ghi trùng.** Loader chỉ commit offset *sau khi* đã ghi ClickHouse thành công. Bản ghi bị ghi lặp (khi loader khởi động lại) được `ReplacingMergeTree ORDER BY (symbol, trade_id)` gộp lại. Vì vậy mọi phép đếm đều dùng `FINAL`.

**Đối chiếu theo mốc (watermark) trong `check.py`.** Nếu chỉ so số dòng tổng thì hai phía luôn lệch, vì có dữ liệu đang trên đường đi. Cách làm:
- Lấy `ingested_at` lớn nhất đã có trong ClickHouse làm **mốc**.
- Lý do mốc này đáng tin: mỗi lô INSERT của ingestor có cùng một `ingested_at`, các lô commit tuần tự, và Debezium cùng loader giữ đúng thứ tự commit. Vì vậy mọi dòng nguồn có `ingested_at < mốc` **bắt buộc** đã có mặt ở đích.
- Đếm số dòng dưới mốc ở cả hai phía. Hai con số bằng nhau tức là không mất dòng nào, kể cả khi dữ liệu vẫn đang chảy.

---

## Kết quả phase 0: định dạng message Debezium

Kiểm tra trên Postgres 15 + Debezium 3.0 + Redpanda (script thử nghiệm: ghi dữ liệu rồi chạy `ALTER` xen giữa).

| Kiểu ở nguồn | Trong message CDC | Cách loader giải mã |
|---|---|---|
| `NUMERIC(18,8)` | `bytes` base64, `name=org.apache.kafka.connect.data.Decimal`, `parameters={scale:8, connect.decimal.precision:18}` | `int.from_bytes(..., signed=True)` rồi dịch dấu thập phân theo `scale` |
| `TIMESTAMPTZ` | chuỗi ISO, `io.debezium.time.ZonedTimestamp`, ví dụ `2026-11-10T08:34:03.777380Z` | `datetime.fromisoformat` |
| `VARCHAR(20)` | `string`. Nếu không bật thêm tùy chọn thì **không có độ dài** (xem bên dưới) | giữ nguyên |
| `BIGINT` / `BOOLEAN` | `int64` / `boolean` | giữ nguyên |

**Fingerprint của schema** (đầu vào cho phase 2): lấy hash phần `schema.fields[after]` của message.

| Bước | Fingerprint |
|---|---|
| Ghi dữ liệu, schema v1 | `86c1bb59af` |
| Sau `ADD COLUMN is_buyer_maker` | `5a94d8b25c`, **đổi** |
| Sau `ALTER price TYPE NUMERIC(24,8)` | `9bc202df1a`, **đổi** (`precision` từ 18 lên 24) |
| Ghi dữ liệu, không có DDL | `9bc202df1a`, giữ nguyên |

Kết luận: chỉ cần so fingerprint là biết *khi nào* phải crawl lại nguồn, thay vì crawl với mọi message.

**Độ dài `varchar`.** Mặc định Debezium không đưa độ dài vào schema, nên kịch bản thu hẹp `varchar(20)→varchar(5)` sẽ không làm fingerprint đổi. Cách xử lý: bật `"column.propagate.source.type": ".*"` trong [`connector.json`](connector.json). Khi đó schema có thêm `__debezium.source.column.type=VARCHAR` và `__debezium.source.column.length=12`.

Lưu ý: Debezium đọc lại catalog *sau khi* `ALTER` đã chạy, nên message ghi ngay trước `ALTER` có thể đã mang độ dài mới. Điều này không ảnh hưởng, vì fingerprint chỉ dùng để *kích hoạt* kiểm tra, còn engine luôn crawl lại nguồn thật.

**Bug phát hiện và đã sửa:** ClickHouse engine biến `varchar(n)` thành `FixedString(n)`, mà kiểu này đệm byte `\0` vào cuối chuỗi ngắn. Giờ chỉ `char(n)` mới dùng `FixedString`. Có test trong [`tests/test_demo_loader.py`](../tests/test_demo_loader.py).

---

## Kết quả phase 1: luồng chạy từ đầu đến cuối

Đo ngày 10/11/2026, khoảng 08:40 UTC (thị trường yên ắng), 6 cặp coin, chạy trên laptop phát triển.

| Chỉ số | Kết quả |
|---|---|
| Thông lượng ingestor | 7 đến 18 trade/giây (thay đổi theo thị trường) |
| Độ trễ end-to-end (từ `trade_time` đến khi vào ClickHouse) | **khoảng 2 giây** (1,8 đến 2,6 giây) |
| Đối chiếu theo mốc khi dữ liệu đang chảy | KHỚP ở mọi lần đo, **mất 0 dòng** |

**Thử nghiệm `ADD COLUMN is_buyer_maker BOOLEAN` trên nguồn khi dữ liệu đang chảy:**
1. Ingestor bắt đầu ghi cột mới ngay lập tức.
2. Loader in `HOLD: bảng đích chưa có cột ['is_buyer_maker']`.
3. Engine (đang ở chế độ quét định kỳ 60 giây) phát hiện thay đổi non-breaking và tự chạy `ALTER TABLE trades ADD COLUMN is_buyer_maker Nullable(Bool)` trên ClickHouse. Registry lên v2.
4. Loader in `RESUME` **sau 44 giây**, xử lý hết phần tồn, độ trễ từ 28,7 giây về 2,3 giây.
5. Đối chiếu: **KHỚP, mất 0 dòng**.

Khoảng chờ 44 giây là do engine đang ở chế độ quét định kỳ. Phase 2 sẽ chuyển sang event-driven có fingerprint để rút xuống dưới 1 giây.

---

## Kết quả phase 2: kịch bản đầy đủ với dữ liệu thật

Đo ngày 10/11/2026, 08:49 đến 08:57 UTC. Có 4 tiến trình chạy song song: ingestor, loader, loader `--naive` và backend. Pipeline ở chế độ `event_driven` có fingerprint.

| Bước | Kết quả | Thời gian engine phản ứng |
|---|---|---|
| `add_column` | Có engine: ClickHouse tự có `is_buyer_maker Nullable(Bool)`, loader HOLD 1 giây rồi chạy tiếp. **Đối chứng: `FAILED: Unrecognized column 'is_buyer_maker'`, dừng hẳn** | **1,08 giây** (phase 1, quét định kỳ: 44 giây) |
| `widen` | ClickHouse `price` thành `Decimal(24, 8)` | **1,39 giây** |
| `rename` | Freeze, loader HOLD. Sandbox `passed`, Approve thì ClickHouse `RENAME qty→quantity`, loader xử lý phần tồn với tốc độ **529 row/s**, độ trễ về 1,6 giây | 33 giây (*) |
| `narrow` | Freeze `narrow_type(symbol)`, loader **PAUSE**, dữ liệu giữ trong Kafka | **0,81 giây** và 1,42 giây |
| `rollback` | Engine thấy nguồn khớp baseline, **tự gỡ freeze**, loader chạy tiếp sau 6 giây | dưới 3 giây |
| `check` sau mỗi bước | **KHỚP, mất 0 dòng** (hơn 22.000 dòng) | |

(*) Riêng lần `rename` này, backend vừa được khởi động lại ngay trước đó. Kafka phải chờ hết thời gian timeout của consumer cũ (bị tắt đột ngột) rồi mới giao partition cho consumer mới. Khi chạy ổn định, các thay đổi breaking bị freeze trong khoảng 1 giây (xem `narrow`). **Đừng khởi động lại backend ngay trước khi demo.**

### Bug phát hiện và đã sửa trong phase 2 (xem bảng dưới); phase 3 ở mục tiếp theo

| Bug | Ảnh hưởng | Cách sửa |
|---|---|---|
| Consumer crawl metadata nguồn với **mọi** message | Vài chục query catalog mỗi giây khi có dữ liệu thật | Fingerprint ([`app/kafka_consumer.py`](../app/kafka_consumer.py)) |
| Notifier gọi Telegram API 3 lần dù token trống | Mỗi sự kiện chặn consumer thêm vài giây vì HTTP 404 | Bỏ qua khi chưa cấu hình ([`notification.py`](../src/schema_evolution/notification.py)) |
| `print` tiếng Việt khi stdout không phải UTF-8 (Windows, cp1258) | `UnicodeEncodeError` **sau khi** đã ALTER đích, nên sự kiện không được ghi vào Live Stream | stdout UTF-8 trong [`src/schema_evolution/__init__.py`](../src/schema_evolution/__init__.py) |
| Bảng đang freeze thì không bao giờ được kiểm tra lại | Rollback nguồn xong bảng vẫn đóng băng vĩnh viễn | `resolved_at_source` ([`core.py`](../src/schema_evolution/core.py)), có [test](../tests/test_freeze_resolution.py) |
| Loader khởi động trước khi topic CDC tồn tại | Đứng ở 0 row/s tới 5 phút | `metadata_max_age_ms=5000` |
| Consumer in một dòng log cho mỗi message | Log ồn, tốn tài nguyên | Bỏ dòng log đó |

---

## Phase 3: trang Live Data Flow (đã thay bằng Pipelines Overview, xem mục Hợp đồng tích hợp)

Trang mặc định của UI tại http://localhost:5173. Mọi thứ cần cho buổi demo nằm trên **một màn hình**, tự cập nhật mỗi 1,5 giây.

| Khu vực | Hiển thị |
|---|---|
| Tiêu đề | Đường đi của dữ liệu (Binance → Postgres → Debezium → Redpanda → ClickHouse) và **giá thật mới nhất** của 6 coin, đổi màu xanh hoặc đỏ khi giá lên hoặc xuống |
| 5 thẻ số liệu | Số dòng nguồn, số dòng warehouse, **dòng bị mất** (kèm "đã đối chiếu tới mốc X: a = b"), độ trễ end-to-end, thông lượng kèm sparkline 2 phút (rê chuột để xem giá trị) |
| Làn "Có Schema Evolution Engine" | Trạng thái loader: Đang chạy / Chờ đồng bộ schema (kèm tên cột đang chờ) / **Tạm dừng: chờ duyệt, kèm nút Review & Approve** / Đã dừng |
| Làn "Đối chứng" | Đang chạy, rồi **Đã hỏng kèm thông báo lỗi thật**; số dòng chưa tới warehouse tăng dần |
| Live CDC Event Stream | Timeline sự kiện: Auto Synced / Requires Approval / **Approved / Rejected / Resolved at source** |

Đã kiểm chứng bằng cách điều khiển trình duyệt (Playwright) theo đúng thao tác của người trình bày, khi dữ liệu thật đang chảy:
1. Chạy `scenario rename`: bảng bị freeze sau **0,72 giây**, làn chính chuyển sang "Tạm dừng: chờ duyệt".
2. Bấm **Review & Approve**, chạy sandbox (passed), rồi Approve.
3. Quay lại Live Data Flow: làn chính "Đang chạy", **dòng bị mất = 0**; làn đối chứng "Đã hỏng" và thiếu 18.004 dòng.

Chi tiết cài đặt:
- Loader ghi `data/flow/loader.json` và `data/flow/naive-loader.json` (trạng thái, số dòng/giây, các cột đang chờ, lỗi). Nếu file không được cập nhật quá 5 giây thì loader bị coi là đã dừng.
- Khi loader đang chờ một cột mà bảng lại đang bị freeze (trường hợp rename), trạng thái được báo là "paused" chứ không phải "hold", để UI hiện nút duyệt.
- Approve và Reject trên API giờ ghi sự kiện vào timeline. Nút "Review & Approve" của một sự kiện cũ tự ẩn khi đã có kết quả duyệt.
- Event log chỉ lưu **trong bộ nhớ**, nên khởi động lại backend sẽ xóa timeline. Đây là thêm một lý do để không khởi động lại backend trong lúc demo.

---

## Hợp đồng tích hợp: demo chỉ là một client của engine

Engine là framework trung gian và **không import hay đọc gì của demo**. Demo cũng **không đọc file nội bộ của engine**. Hai bên chỉ nói chuyện qua HTTP:

| Hướng | API | Demo dùng để |
|---|---|---|
| data plane → engine | `GET /api/gate/{pipeline}/{table}` → `{state: open\|frozen, schema_version, pending_changes, column_renames}` | Loader hỏi trước mỗi lô; `frozen` thì PAUSE |
| data plane → engine | `POST /api/pipelines/{pipeline}/components/{name}` `{state, role, metrics{}, message}` | `loader`, `naive-loader`, `reconciler` báo trạng thái và chỉ số; trang Overview hiển thị nguyên các chỉ số đó |
| UI → engine | `GET /api/topology` (mỗi pipeline kèm `components`) | Trang Pipelines Overview |

Một thành phần im lặng quá 15 giây sẽ bị coi là `stale` (riêng `failed` thì giữ nguyên). Khi không liên lạc được Gate API, loader **giữ trạng thái đã biết gần nhất** (fail-static); cơ chế HOLD với cột lạ vẫn bảo vệ dữ liệu.

**Lỗi phát hiện ở tốc độ cao (khoảng 1.000 dòng/giây) và đã sửa: đổi tên cột làm loader chết.** Khi duyệt `RENAME qty → quantity`, trong Kafka vẫn còn message cũ mang tên `qty` chưa được ghi. Warehouse đổi tên xong, loader ghi các message cũ đó và gặp lỗi `Unrecognized column 'qty'`, rồi dừng hẳn (không mất dữ liệu nhưng luồng đứng yên). Cách sửa:
- Engine **ghi lại các lần đổi tên đã duyệt** (`column_renames`, có nối chuỗi `a→b→c`) **trước** khi gỡ freeze, và trả về qua Gate API.
- Loader **ánh xạ tên cột cũ sang tên mới**. Nếu warehouse vừa đổi schema sau lần đọc trước, loader đọc lại rồi ghi lại cả lô (bản ghi trùng được `ReplacingMergeTree` gộp lại).

Đã kiểm chứng ở khoảng 340 trade/giây: loader gặp đúng lỗi cũ, tự xử lý rồi chạy tiếp, **mất 0 dòng**.

---

## Xử lý sự cố

| Triệu chứng | Cách xử lý |
|---|---|
| `setup` báo `connector FAILED` | Xem `trace` trong thông báo lỗi. Thường do slot `market_slot` còn sót lại: chạy `--reset` |
| Loader `HOLD` mãi không dừng | Engine chưa đồng bộ đích: kiểm tra backend có đang chạy không, và bảng có đang bị freeze không (vào UI, Approve hoặc Reject) |
| Loader `PAUSE` mãi, hoặc tự `PAUSE` lại khoảng 60 giây sau khi Reject | Reject không sửa được nguồn. Lần quét kế tiếp sẽ phát hiện lại và freeze tiếp. Hãy rollback nguồn (`python -m demo.scenario rollback`), engine sẽ tự gỡ freeze |
| Engine phản ứng chậm (khoảng 30 giây) ngay sau khi khởi động lại backend | Consumer group đang chờ timeout của consumer cũ. Đợi khoảng 30 giây, hoặc khởi động backend sớm trước buổi demo |
| Pipeline đối chứng đã `FAILED` | Đó là kịch bản. Muốn chạy lại từ đầu thì dùng `--reset` |
| Ingestor không kết nối được | Thử `--ws wss://stream.binance.com:9443`, hoặc dùng `--replay` |
| `UnicodeEncodeError` trên console Windows | Package `demo` đã tự chuyển stdout sang UTF-8. Nếu chạy script ngoài package, đặt `PYTHONIOENCODING=utf-8` |
| Postgres phình WAL | Replication slot bị bỏ lại khi connector đã xóa: `--reset` sẽ xóa slot |

---

## Lộ trình

- [x] **Phase 0**: kiểm tra định dạng message, fingerprint, độ dài varchar, sửa bug FixedString
- [x] **Phase 1**: ingestor (live, record, replay), bảng nguồn và đích, connector, loader có HOLD, đối chiếu theo mốc, setup/reset
- [x] **Phase 2**: fingerprint và chế độ `event_driven`, loader PAUSE theo freeze, pipeline đối chứng `--naive`, `scenario.py`, tự gỡ freeze khi nguồn rollback, cùng 6 bug đã sửa (xem bên trên)
- [x] **Phase 3**: trang Live Data Flow (sau đó thay bằng Pipelines Overview + Gate/Reporting API) (thẻ số liệu, sparkline, 2 làn pipeline, nút duyệt, timeline có cả Approved/Rejected/Resolved)
- [ ] **Phase 4**: đo p50/p95 qua nhiều lần chạy, thử replay, chạy liên tục lâu, tập dượt

### Kịch bản cho ngày demo (thứ Năm)

Trước buổi demo: chạy `--reset`, khởi động 4 tiến trình cùng UI, rồi **để chạy ít nhất 1 phút** cho consumer group ổn định.

| Bước | Lệnh | Kết quả mong đợi (đã kiểm chứng trong phase 2) |
|---|---|---|
| 0 | Mở **Pipelines Overview** trên UI | `loader` và `naive-loader` đều `running`, `reconciler` báo `ok`, Lost rows = 0 |
| 1 | `python -m demo.scenario add_column` | **Làn đối chứng chuyển sang "Đã hỏng".** Có engine: tự thêm cột sau khoảng 1 giây, không gián đoạn |
| 2 | `python -m demo.scenario widen` | WIDEN, tự áp dụng sau khoảng 1,4 giây |
| 3 | `python -m demo.scenario rename` | Làn chính "Tạm dừng: chờ duyệt". Bấm **Review & Approve**, chạy sandbox, Approve, quay lại Data Flow: loader xử lý phần tồn |
| 4 | `python -m demo.scenario narrow` | Thu hẹp kiểu bị bắt sau khoảng 1 giây, loader PAUSE |
| 5 | `python -m demo.scenario rollback` | Engine tự gỡ freeze, loader chạy tiếp |
| 6 | `python -m demo.check` | **KHỚP, mất 0 dòng.** Pipeline đối chứng: thiếu hàng nghìn dòng |

Với bước 4, nếu muốn trình diễn nút Reject trên UI, hãy chạy `rollback` **ngay sau** khi Reject (trong vòng 60 giây).
