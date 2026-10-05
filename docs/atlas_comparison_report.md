# Báo Cáo So Sánh Chi Tiết: Atlas by Ariga (atlasgo.io) vs. Schema Evolution Engine

> **Mục đích**: Báo cáo tổng hợp, đánh giá kỹ thuật và so sánh giữa công cụ **Atlas (by Ariga)** và **Schema Evolution Engine (Dự án hiện tại)** để phục vụ việc viết báo cáo / thuyết minh đồ án.

---

## 1. Tổng Quan Về Hai Hệ Thống

| Tiêu Chí | Atlas by Ariga (`atlasgo.io`) | Schema Evolution Engine (Dự án hiện tại) |
| :--- | :--- | :--- |
| **Đơn vị phát triển** | Ariga (Đội ngũ đứng sau Ent ORM trong Golang) | Dự án nghiên cứu & phát triển hiện tại |
| **Triết lý cốt lõi** | **Database Schema as Code** (Mô hình Declarative / Versioned DevOps giống Terraform) | **Real-time Event-Driven CDC Schema Evolution** (Tự động phát hiện, cách ly & đồng bộ DDL) |
| **Phạm vi ứng dụng** | Quản lý migration DB ứng dụng trong quy trình Lập trình & CI/CD | Theo dõi & bảo vệ luồng đồng bộ dữ liệu Real-time (Data Engineering & Warehouse) |
| **Hình thức giao diện** | Command Line Interface (CLI), Atlas Cloud, Terraform Provider, K8s Operator | Enterprise Web UI (React Dark Mode), Topology Visualizer, Live CDC Stream Monitor |

---

## 2. Bảng So Sánh Tính Năng Kỹ Thuật (Technical Feature Comparison Matrix)

| Tính Năng / Đặc Điểm | Atlas by Ariga (`atlasgo.io`) | Schema Evolution Engine |
| :--- | :--- | :--- |
| **1. Cơ chế thu thập sự thay đổi** | **Static / State-based**: So sánh file code HCL/SQL hoặc Snapshot DB với trạng thái mong muốn. | **Real-time Streaming**: Lắng nghe sự kiện DDL / CDC thay đổi trực tiếp từ WAL/Binlog qua Redpanda (Kafka). |
| **2. Xử lý Breaking Changes** | **Shift-Left Security**: Chặn file migration có lỗi/rủi ro ngay từ bước CI/CD (GitHub Actions / GitLab CI). | **Runtime Isolation & Gatekeeper**: Tự động đóng băng luồng (`is_frozen = True`), ngăn gãy Data Warehouse. |
| **3. Kiểm thử an toàn DDL** | `--dry-run` hoặc mô phỏng trên Dev Database tạm thời (`--dev-url`). | **Sandbox Isolation Testing**: Khởi tạo môi trường cách ly trên Web UI để chạy thử DDL trước khi Duyệt. |
| **4. Đồng bộ Đa Cơ sở dữ liệu** | Thực thi DDL trên từng DB đơn lẻ (PostgreSQL, MySQL, SQLite, MariaDB, ClickHouse...). | **Cross-Engine Sync**: Tự động dịch và đồng bộ DDL giữa các DB khác nhau (Postgres/MySQL/Mongo ➔ ClickHouse). |
| **5. Quản lý phiên bản Schema** | Lưu trữ dưới dạng chuỗi các tệp `.sql` migration có mốc thời gian (Versioned Migrations). | Lưu trữ các bản ghi JSON Snapshot theo từng phiên bản (`v1`, `v2`, `v3`...) trong `SchemaRegistry`. |
| **6. Cảnh báo & Thông báo** | Email / GitHub Comment / Atlas Cloud Dashboard. | Telegram Notifier Bot (Real-time alert) + Web Notification Toasts. |

---

## 3. Phân Tích Chi Tiết 4 Luồng Nghiệp Vụ Cốt Lõi

### 3.1. Trích Xuất & Kiểm Tra Cấu Trúc (Schema Inspection)
* **Atlas**: Sử dụng lệnh `atlas schema inspect -u "sqlite://db.sqlite"` để đọc DB thực tế và xuất thành mã HCL hoặc SQL DDL.
* **Schema Evolution Engine**: Hệ thống chủ động kiểm tra (scan) các bảng nguồn, sinh ra tệp `table_v1.json` lưu trong `SchemaRegistry`, giúp duy trì lịch sử cấu trúc chính xác theo thời gian.

### 3.2. Tính Toán Sự Khác Biệt (Schema Diff Engine)
* **Atlas**: So sánh 2 tệp HCL/SQL (`v1.hcl` và `v2.hcl`) bằng thuật toán Declarative Diff. Với SQLite (vốn hạn chế lệnh DDL), Atlas tự tạo ra kịch bản 6 bước:
  1. `PRAGMA foreign_keys = off;`
  2. `CREATE TABLE new_users (...);`
  3. `INSERT INTO new_users SELECT id, email FROM users;`
  4. `DROP TABLE users;`
  5. `ALTER TABLE new_users RENAME TO users;`
  6. `PRAGMA foreign_keys = on;`
* **Schema Evolution Engine**: Bắt trực tiếp sự kiện DDL từ CDC Stream hoặc Baseline Checker, phân tích chi tiết loại thay đổi (`ADD_COLUMN`, `DROP_COLUMN`, `RENAME_COLUMN`, `CHANGE_TYPE`) và đánh giá mức độ rủi ro (Breaking vs Non-Breaking).

### 3.3. Kiểm Soát Rủi Ro & Phê Duyệt (Risk Governance)
* **Atlas**: Tích hợp `atlas migrate lint` vào luồng CI/CD. Nếu developer cố tình xóa cột (`DROP COLUMN`), Atlas Linter sẽ cảnh báo nguy cơ mất dữ liệu và chặn merge Pull Request.
* **Schema Evolution Engine**: Bảo vệ môi trường **Runtime Streaming**. Khi phát hiện sự kiện CDC làm thay đổi DDL nguy hiểm ở DB Nguồn, Gatekeeper ngay lập tức đưa bảng vào trạng thái **Frozen**. Hệ thống cung cấp công cụ **Sandbox Test** trên Web UI để Admin kiểm thử tính tương thích trước khi bấm nút **Approve & Sync** sang ClickHouse.

### 3.4. Môi Trường Vận Hành (Operational Environment)
* **Atlas**: Phù hợp cho đội ngũ **Software Software Engineers & DevOps** quản lý cấu trúc cơ sở dữ liệu của ứng dụng theo quy trình GitOps.
* **Schema Evolution Engine**: Phù hợp cho đội ngũ **Data Platform / Data Engineers** duy trì các luồng ETL/ELT streaming liên tục mà không bị gián đoạn khi DB Nguồn bị thay đổi cấu trúc đột ngột.

---

## 4. Kịch Bản Demo Thực Tế Bằng Docker (Đã Kiểm Thử Thành Công)

Dưới đây là các câu lệnh Docker CLI thực tế đã được chạy kiểm thử thành công trong dự án (`d:\schema-evolution-core\atlas_demo`):

```powershell
# 1. Kiểm tra phiên bản Atlas Docker
docker run --rm arigaio/atlas version

# 2. So sánh Diff giữa 2 phiên bản v1.hcl và v2_breaking.hcl
docker run --rm -v "${PWD}/atlas_demo:/workspace" arigaio/atlas schema diff `
  --from "file://workspace/v1.hcl" `
  --to "file://workspace/v2_breaking.hcl" `
  --dev-url "sqlite://file?mode=memory"

# 3. Khởi tạo v1 vào Database SQLite
docker run --rm -v "${PWD}/atlas_demo:/workspace" arigaio/atlas schema apply `
  -u "sqlite://workspace/demo.db" `
  --to "file://workspace/v1.hcl" `
  --auto-approve

# 4. Chạy Dry-Run thử nghiệm nâng cấp lên v2_breaking (Xem trước lệnh SQL)
docker run --rm -v "${PWD}/atlas_demo:/workspace" arigaio/atlas schema apply `
  -u "sqlite://workspace/demo.db" `
  --to "file://workspace/v2_breaking.hcl" `
  --dry-run

# 5. Reverse Engineer (Trích xuất) cấu trúc DB thực tế ra code HCL
docker run --rm -v "${PWD}/atlas_demo:/workspace" arigaio/atlas schema inspect `
  -u "sqlite://workspace/demo.db"
```

---

## 5. Kết Luận Điểm Mạnh Tương Hỗ

* **Atlas by Ariga** là giải pháp xuất sắc cho bài toán **"Schema as Code & Migration CI/CD"** ở tầng ứng dụng (Application Level).
* **Schema Evolution Engine (Dự án hiện tại)** giải quyết bài toán **"Real-time CDC Streaming Isolation & Cross-Engine Target Sync"** ở tầng hạ tầng dữ liệu (Data Infrastructure Level). Việc kết hợp cả hai tư tưởng giúp bức tranh tổng thể về Quản trị Cấu trúc Cơ sở dữ liệu (Database Governance) trở nên hoàn chỉnh và chặt chẽ hơn.
