# Báo Cáo So Sánh Chi Tiết: Liquibase vs. Atlas (arigaio) vs. Schema Evolution Engine

> **Mục đích**: Báo cáo tổng hợp, đánh giá kỹ thuật và so sánh chuyên sâu giữa hai công cụ quản trị Schema hàng đầu thế giới (**Liquibase** và **Atlas by Ariga**) với hệ thống **Schema Evolution Engine (Dự án hiện tại)** để phục vụ thuyết minh đồ án / báo cáo tốt nghiệp.

---

## 1. Tổng Quan Về 3 Hệ Thống

```
+-----------------------------------------------------------------------------------+
|                            GIAO DIỆN & CÁCH TIẾP CẬN                              |
+--------------------------+--------------------------+-----------------------------+
|        LIQUIBASE         |      ATLAS (ARIGA)       |   SCHEMA EVOLUTION ENGINE   |
| (Migration-Based / Java) |  (Declarative / Golang)  | (Real-time CDC / Python)    |
+--------------------------+--------------------------+-----------------------------+
| - Viết chuỗi changeset   | - Khai báo mong muốn     | - Bắt DDL từ WAL/Binlog     |
| - XML, YAML, JSON, SQL   | - HCL, SQL, ORM          | - Redpanda Event Stream     |
| - Bảng DATABASECHANGELOG | - Schema Diff Engine     | - SchemaRegistry & Sandbox  |
+--------------------------+--------------------------+-----------------------------+
```

1. **Liquibase (v5.0.4)**: Công cụ lâu đời (ra đời từ 2006), rất phổ biến trong hệ sinh thái Java / Enterprise. Vận hành theo mô hình **Imperative / Versioned Migrations**, lưu vết bằng 2 bảng hệ thống (`DATABASECHANGELOG` và `DATABASECHANGELOGLOCK`) trực tiếp trong cơ sở dữ liệu.
2. **Atlas by Ariga (v1.3.4)**: Công cụ thế hệ mới (mã nguồn mở Golang). Vận hành theo mô hình **Declarative (Schema as Code)** giống như Terraform dành cho Database.
3. **Schema Evolution Engine (Dự án hiện tại)**: Hệ thống quản trị Schema thời gian thực theo kiến trúc **Event-Driven CDC**. Tự động bắt sự kiện DDL từ DB Nguồn (PostgreSQL, MySQL, MongoDB), đóng băng an toàn (Gatekeeper Isolation), cung cấp Sandbox Test trên Web UI và đồng bộ sang Data Warehouse (ClickHouse).

---

## 2. Bảng So Sánh Kỹ Thuật (3-Way Comparison Matrix)

| Tiêu Chí So Sánh | Liquibase (Enterprise Standard) | Atlas by Ariga (Modern DevOps) | Schema Evolution Engine (Dự án hiện tại) |
| :--- | :--- | :--- | :--- |
| **Triết lý thiết kế** | **Imperative / ChangeSet**: Định nghĩa chuỗi các bước thay đổi thủ công. | **Declarative / State-Based**: Định nghĩa trạng thái mong muốn (Desired State). | **Event-Driven Streaming**: Lắng nghe & phản ứng với DDL phát sinh ở Runtime. |
| **Định dạng file cấu hình** | SQL, XML, YAML, JSON | HCL, SQL, ORM (Ent, Prisma, GORM) | YAML Pipeline Config + JSON Registry Snapshots |
| **Cơ chế lưu trữ vết** | Bảng `DATABASECHANGELOG` nằm trong chính DB đích. | State Diffing / Migration Directory | Tệp JSON Snapshot (`v1`, `v2`...) trong `SchemaRegistry`. |
| **Khả năng Rollback** | Rất mạnh (`liquibase rollback`) qua SQL rollback script. | Hỗ trợ Down-migrations qua HCL/SQL. | Khôi phục phiên bản schema snapshot trước đó từ Registry. |
| **Xử lý Breaking Changes** | Kiểm tra Preconditions / Fail on error khi chạy lệnh `update`. | Linting kiểm tra rủi ro trong luồng CI/CD (GitHub Actions). | **Runtime Isolation**: Tự động đóng băng luồng (`is_frozen`), bắt buộc Sandbox Test & Approve trên Web UI. |
| **Khả năng đồng bộ Đa DB** | Thực thi DDL riêng cho từng DB. | Thực thi DDL riêng cho từng DB. | **Cross-Engine Translation**: Dịch & đồng bộ DDL giữa các DB khác loại (Postgres/MySQL ➔ ClickHouse). |
| **Môi trường phù hợp nhất** | Enterprise Java Apps, CI/CD Deployment cho DB đơn lẻ. | Modern Cloud-Native Apps, Kubernetes, Microservices. | Data Engineering, CDC Data Ingestion & Data Warehouse Pipelines. |

---

## 3. Phân Tích Chi Tiết 4 Luồng Nghiệp Vụ Về Liquibase

### 3.1. Quản Lý Changeset & Changelog
Liquibase chia các thay đổi thành từng `changeSet` được định danh bằng cặp `id` + `author`. Khi chạy `update`, Liquibase tính mã băm MD5 của từng changeset và đối chiếu với bảng `DATABASECHANGELOG`. Nếu changeset đã chạy, Liquibase sẽ bỏ qua; nếu là changeset mới, Liquibase mới thực thi SQL.

### 3.2. Tính Năng Reverse Engineering (`generate-changelog`)
Liquibase có khả năng đọc cơ sở dữ liệu hiện tại và xuất thành file changelog (XML/YAML/SQL). Lệnh này giúp nhanh chóng đóng gói cấu trúc DB legacy vào hệ thống quản lý phiên bản.

### 3.3. Tính Năng So Sánh Cấu Trúc (`diff` & `diff-changelog`)
So sánh giữa 2 Database (VD: Dev vs Prod) hoặc giữa Database và Snapshot để phát hiện sự lệch cấu trúc (Schema Drift), từ đó tự động sinh tệp changelog bổ sung.

---

## 4. Kịch Bản Demo Thực Tế Với Liquibase 5.0.4 (Đã Chạy Trên Máy Ổ D:)

Các câu lệnh sau đã được chạy thử nghiệm thành công với bộ cài `D:\liquibase\liquibase.bat`:

### Bước 1: Kiểm tra phiên bản Liquibase
```powershell
D:\liquibase\liquibase.bat --version
```
*Kết quả*: Liquibase Version 5.0.4 chạy trên Java 17.

### Bước 2: Thực thi nâng cấp Schema (Update Changelog)
Sử dụng file changelog YAML (`d:\schema-evolution-core\liquibase_demo\db.changelog.yaml`):
```powershell
D:\liquibase\liquibase.bat `
  --url="jdbc:h2:file:./liquibase_demo/testdb" `
  --username=sa --password="" `
  --changelog-file="./liquibase_demo/db.changelog.yaml" `
  update
```
*Kết quả*: Liquibase tự động khởi tạo bảng `DATABASECHANGELOG` và thực thi thành công 2 `changeSet` (`1-create-users` và `2-add-age-column`).

### Bước 3: Reverse Engineer xuất Schema DB thành XML Changelog
```powershell
D:\liquibase\liquibase.bat `
  --url="jdbc:h2:file:./liquibase_demo/testdb" `
  --username=sa --password="" `
  --changelog-file="./liquibase_demo/generated.changelog.xml" `
  generate-changelog
```
*Kết quả*: Tạo ra file [generated.changelog.xml](file:///d:/schema-evolution-core/liquibase_demo/generated.changelog.xml) chứa đầy đủ cấu trúc bảng `USERS` chuẩn XML.

---

## 5. Đánh Giá Tổng Kết & Kiến Nghị Cho Báo Cáo Đồ Án

1. **Liquibase**: Là đại diện tiêu biểu cho giải pháp **Imperative Database Migration cổ điển**, cực kỳ ổn định trong môi trường Enterprise, quản lý chặt chẽ theo từng tệp changeset.
2. **Atlas**: Là đại diện cho giải pháp **Declarative Schema as Code hiện đại**, tối ưu cho môi trường DevOps và Cloud-Native.
3. **Schema Evolution Engine (Dự án hiện tại)**: Là giải pháp chuyên biệt cho **Real-time Data Streaming & Warehouse Ingestion**, giải quyết bài toán chống gãy pipeline dữ liệu khi DB Nguồn thay đổi DDL bất ngờ ở môi trường Runtime.
