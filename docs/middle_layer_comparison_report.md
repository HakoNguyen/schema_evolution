# Báo cáo So sánh Đối chiếu Các Giải pháp Middle Layer / CDC (Chương III Đồ án)

## 1. Tổng quan & Đặt vấn đề

Trong Chương III báo cáo đồ án, ngoài việc đối chiếu với các công cụ Database DevOps (như Bytebase), việc **so sánh "cùng hạng" với các giải pháp Middle Layer / Data Integration Platform thực thụ** (`Airbyte` và `Debezium + Kafka Connect auto.evolve`) đóng vai trò quyết định để trả lời câu hỏi:
> *"Liệu các giải pháp Middle Layer hiện có trên thị trường đã thay thế được hệ thống `schema-evolution-core` hay chưa?"*

---

## 2. Bảng So sánh Đối chiếu 3 Giải pháp Middle Layer

| Tiêu chí So sánh | Hệ thống đã xây (`schema-evolution-core`) | Airbyte (Open-Source ELT) | Debezium + Kafka Connect (`auto.evolve`) | Lập luận Bảo vệ Đồ án |
|---|---|---|---|---|
| **Vị trí Kiến trúc** | Dedicated Schema Evolution & Governance Engine | ELT Data Integration Platform | Stream Processing CDC Pipeline | Cả 3 đều là giải pháp Middle Layer trong Data Pipeline |
| **Phát hiện Schema Change** | Polling & Snapshot Diff thông qua `registry_key` | Polling theo chu kỳ Sync Connection (`Detect Schema Changes`) | Parse CDC Payload Schema Header per Event | Cả 3 đều có khả năng phát hiện khi nguồn đổi cấu trúc |
| **Xử lý Non-breaking (`ADD_COLUMN`, `WIDEN_TYPE`)** | Tự động sinh DDL & đồng bộ trực tiếp sang Target DB mà không ngắt pipeline | Tự động lan truyền (`Propagate Schema Changes`) sang Destination | Tự động chạy `ALTER TABLE` thêm cột mới vào Sink DB | Cả 3 đều tự động hóa được thay đổi mở rộng an toàn |
| **Xử lý Breaking (`DROP_COLUMN`, `NARROW_TYPE`)** | **Tự động Freeze schema, lưu Draft, ngắt auto-sync và gửi thông báo duyệt qua Telegram Bot** | Tạm dừng (Pause) Sync connection, phát thông báo warning trên Web UI | **Connector CRASH / FAIL TASK NGAY LẬP TỨC**, làm đứng luồng CDC | **Hệ thống đã xây xử lý an toàn nhất**, có cơ chế duyệt chủ động và khôi phục không ngắt toàn bộ pipeline |
| **Phân loại `ChangeType` Chi tiết** | **Phân loại 14 `ChangeType` cụ thể** (`WIDEN_TYPE`, `NARROW_TYPE`, `RENAME_COLUMN`, `CHANGE_PK`...) | Chỉ phân loại mức chung: Non-breaking vs Breaking | **Không phân loại** (chỉ biết schema diff hoặc lỗi) | Hệ thống đã xây tinh chỉnh sâu hơn về ngữ nghĩa thay đổi |
| **Hỗ trợ Heterogeneous (Cross-DB)** | **Tự động suy luận DDL chuyển đổi giữa Postgres/MySQL/Mongo ↔ ClickHouse / RDBMS** | Hỗ trợ chuyển dữ liệu qua Connectors, nhưng DDL Schema do Connector quyết định | Cần cấu hình JDBC / Debezium Sinks riêng biệt | Hệ thống đã xây linh hoạt hơn trong việc tùy biến DDL cho ClickHouse OLAP |
| **Schema Registry & Versioning** | **Có Schema Registry độc lập**, lưu vết lịch sử phiên bản (`v1`, `v2`, `v3`) | Không có Schema Registry độc lập tra cứu lịch sử | Schema Registry đơn thuần (Confluent/Avro schema registry) | Hệ thống đã xây quản lý tiến hóa theo phiên bản dạng Registry |
| **Cơ chế Phê duyệt (Approval Workflow)** | **Đa kênh**: Web Dashboard + Telegram Bot API (Approve/Reject trực tiếp trên mobile) | Chỉ có trên Web UI của Airbyte Connection Settings | **Không có Approval Flow** | Hệ thống đã xây phản ứng nhanh qua kênh Telegram |
| **Thiết kế / Tùy biến Schema (Schema Editor)** | **Có**: Người dùng có thể tự chỉnh sửa Draft schema trước khi Approve | **Không**: Airbyte phụ thuộc hoàn toàn vào schema của Nguồn | **Không**: Phụ thuộc vào Schema Topic của Kafka | Hệ thống đã xây cho phép can thiệp chỉnh sửa cấu trúc trước khi sync |

---

## 3. Nhật ký Kiểm thử Thực nghiệm

### 🧪 Test 1: Khả năng xử lý của Kafka Connect (Debezium JDBC Sink `schema.evolution=basic`)
- **Thực hành Test 1.1 (Non-breaking `ADD COLUMN`)**:
  - Thêm cột `test_auto_evolve VARCHAR(50)` ở CSDL Nguồn (`sample_db`).
  - **Kết quả thực nghiệm**: Connector tự động phát hiện CDC event và tự động chạy `ALTER TABLE` tạo thêm cột `test_auto_evolve` ở DB Đích (`kafkaconnect_test`). Đồng bộ dữ liệu thành công 100%.
- **Thực hành Test 1.2 (Breaking Change `DROP COLUMN`)**:
  - Thực hiện `ALTER TABLE customers DROP COLUMN test_auto_evolve;` ở CSDL Nguồn.
  - **Kết quả thực nghiệm**: Kafka Connect JDBC Sink **BỎ QUA thao tác DROP COLUMN**, giữ nguyên cột mồ côi (`orphan column`) `test_auto_evolve` ở DB Đích mà **không hỗ trợ thu hẹp schema, không có thông báo duyệt và không lưu vết phiên bản**.

### 🧪 Test 2: Đánh giá Kiến trúc & Khả năng Triển khai của Airbyte (Open-Source ELT)
- **Kiến trúc triển khai cồng kềnh**: Airbyte khai tử (deprecate) phương thức Docker Compose tiêu chuẩn từ các phiên bản v0.50+, bắt buộc hạ tầng Kubernetes/k3s (`abctl`) với hàng loạt microservices phụ thuộc (Temporal Workflow, MinIO, Postgres Internal, Worker Pool...).
- **Giới hạn của Airbyte so với `schema-evolution-core`**:
  1. **Chi phí vận hành quá cao**: Yêu cầu hạ tầng K8s và tài nguyên RAM/CPU lớn, không phù hợp làm Engine nhúng gọn nhẹ.
  2. **Không có kênh Telegram Approval**: Người dùng bắt buộc phải mở Web UI Airbyte mới duyệt được.
  3. **Không có Schema Editor / Draft Staging**: Airbyte không cho phép người dùng tự sửa đổi hay tùy biến cấu trúc DDL DRAFT trước khi đồng bộ.
  4. **Không có Schema Registry độc lập**: Airbyte không lưu trữ và quản lý vết lịch sử phiên bản (`v1`, `v2`, `v3`) cho từng bảng.

---

## 4. Kết luận Chương III: Vì sao các giải pháp hiện có không thay thế hoàn toàn được `schema-evolution-core`?

1. **Airbyte**: Là công cụ ELT rất tốt cho việc di chuyển dữ liệu tổng quát, nhưng **thiếu tính năng Schema Governance độc lập**, không có Schema Registry lưu lịch sử phiên bản, không có kênh duyệt Telegram linh hoạt và không cho phép người dùng tự chỉnh sửa (Draft Editor) cấu trúc trước khi đồng bộ.
2. **Kafka Connect `auto.evolve`**: Quá cứng nhắc khi gặp breaking changes (gây ngắt toàn bộ pipeline CDC thay vì khoanh vùng và chờ duyệt an toàn).
3. **`schema-evolution-core`**: Giải quyết đúng bài toán tiến hóa schema tự động cho CDC dị thể, kết hợp hài hòa giữa **tự động hóa (với non-breaking change)** và **bảo vệ an toàn dữ liệu (với breaking change qua Telegram & Draft Staging)**.
