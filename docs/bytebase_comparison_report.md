# Báo cáo Đánh giá & So sánh Đối chiếu: Hệ thống đã xây vs. Bytebase (Chương III)

## 1. Tổng quan & Mục đích So sánh

- **Context**: Bytebase là công cụ Database DevOps / Schema Change Management mã nguồn mở (Community Edition). Trong các nhóm công nghệ khảo sát ở Chương III (Database Migration, Schema Registry, Metadata Platform, CDC), Bytebase đứng ở vị trí mở rộng của **Database Migration** với 2 điểm tương đồng cốt lõi:
  1. **Approval Workflow thật**: Thay đổi schema phải qua Issue/Review trước khi áp dụng vào DB.
  2. **Schema Drift Detection**: Phát hiện khi schema DB bị thay đổi trực tiếp ngoài luồng quản lý.
- **Mục đích**: Đối chiếu 2 tính năng cốt lõi trùng hợp trực tiếp với hệ thống đã xây (`Draft/Staging + Approve/Reject` và `compare_schemas()`) để phục vụ làm minh chứng thực nghiệm cho **Chương III đồ án**.

---

## 2. Bảng So sánh Đối chiếu Tiêu chí (Kết quả Kiểm thử Thực tế)

| Tiêu chí | Hệ thống đã xây (`schema-evolution-core`) | Bytebase (Community Edition) | Ghi chú & Đánh giá |
|---|---|---|---|
| **Cơ chế phát hiện thay đổi (Drift Detection)** | Polling định kỳ, so sánh schema snapshot với baseline qua `registry_key` | Schema Sync & Drift Check qua từng mốc snapshot thời gian | Cả 2 đều phát hiện diff khi schema có sự thay đổi |
| **Phân loại breaking / non-breaking** | Phân loại chi tiết theo 14 loại `ChangeType` (`ADD_COLUMN`, `DROP_COLUMN`, `MODIFY_TYPE`...), tự động block auto-sync khi rủi ro cao | Mặc định không phân loại nhãn `ChangeType` hay đánh nhãn breaking/non-breaking tự động (cần cấu hình SQL Review Policies Enterprise) | Hệ thống đã xây chủ động bảo vệ DB đích khỏi câu lệnh nguy hiểm ngay từ đầu |
| **Tự động sinh SQL DDL & Đồng bộ** | Tự động phân tích diff từ Nguồn, sinh DDL tương thích cho Đích (hỗ trợ cross-db) | Người dùng tự viết SQL DDL trong Issue hoặc liên kết GitOps repository | Bytebase đóng vai trò Execution Engine; hệ thống đã xây đóng vai trò Auto-generator |
| **Approval Workflow** | Cơ chế Draft/Staging riêng biệt; khi Approve tự động áp dụng DDL sang Đích và tạo baseline | Issue-based Workflow (`Plan -> Review -> Rollout`) phân cấp theo Environment (Test: Review Skipped; Prod: Approval Required) | Bytebase tích hợp quy trình review kiểu Issue ticket chuyên nghiệp |
| **Quản lý lịch sử phiên bản (Version History)** | Lưu Migration History Record độc lập với từng baseline version sau mỗi lần phê duyệt | Lưu danh sách Issue/Plan đã deployed và Schema Snapshot History qua từng mốc thời gian | Cả 2 đều đáp ứng khả năng truy vết lịch sử thay đổi |
| **Hỗ trợ NoSQL (MongoDB)** | Có — Tự suy luận schema từ document mẫu (MongoDB), hỗ trợ chuyển đổi và đồng bộ sang ClickHouse / RDBMS | Không — Bytebase tập trung vào RDBMS (PostgreSQL, MySQL, Oracle, SQL Server...). Không hỗ trợ Document/NoSQL | Hệ thống đã xây mở rộng phạm vi sang NoSQL |
| **Hỗ trợ đồng bộ dị thể (Heterogeneous DB)** | Có — Đồng bộ dị thể giữa OLTP (Postgres/MySQL) ↔ OLAP/Columnar (ClickHouse) hoặc NoSQL (Mongo) | Không — Bytebase quản lý schema change nội bộ cùng loại DBMS (Homogeneous Change Management) | Khác biệt lớn về kiến trúc đồng bộ dữ liệu/schema |
| **Kênh thông báo kết quả** | Telegram Bot API (gửi thông báo kèm nút bấm phê duyệt/từ chối trực tiếp) | Hỗ trợ 8+ kênh Webhook chính chủ (Slack, Discord, MS Teams, Google Chat, DingTalk, Feishu, Lark, WeCom). **Không có Telegram mặc định** | Bytebase tập trung vào công cụ chat doanh nghiệp; hệ thống đã xây chọn Telegram linh hoạt |
| **Giao diện quản trị (UI/UX)** | Streamlit Web App (tự xây, tập trung trực quan hóa tiến hóa schema và thao tác Approve/Reject) | Web Platform thương mại/mã nguồn mở chuyên nghiệp, tích hợp RBAC, Workspace, Project, Environment, Audit Logs | Bytebase có UI/UX sản phẩm hoàn chỉnh hơn |
| **Phạm vi & Mục tiêu triển khai** | Đồ án nghiên cứu chuyên sâu, tập trung giải quyết bài toán Schema Evolution tự động, đồng bộ dị thể và phân loại rủi ro | Sản phẩm Database DevOps / CI/CD toàn diện cho quản trị viên CSDL (DBA) và đội ngũ Developer trong doanh nghiệp | Trùng hợp ở quy trình duyệt & drift; khác biệt ở bài toán đồng bộ dị thể |

---

## 3. Nhật ký Kiểm thử Thực tế (4 Test Workflows)

### 🧪 Test 1: Change Management Workflow
- **Thao tác**: Tạo Issue trong Bytebase đề xuất DDL `ALTER TABLE customers ADD COLUMN vip_note2 VARCHAR(100);`.
- **Kết quả quan sát**:
  1. **Quy trình qua Issue**: Mọi thay đổi schema đều được đóng gói thành 1 Issue / Plan có mã số theo dõi (ví dụ: `ADD COLUMN`).
  2. **Automated Checks**: Bytebase tự động chạy kiểm tra an toàn SQL (`CHECKS Success 2`) kiểm tra cú pháp và quy tắc trước khi cho phép triển khai.
  3. **Approval Flow theo Môi trường**: Ở môi trường `Test`, quy trình review được thiết lập linh hoạt (`No approval required / Review Skipped`). Nếu chuyển sang `Prod`, Issue sẽ bắt buộc bước duyệt của Administrator.
  4. **Thực thi Tự động (Rollout)**: Ngay khi được duyệt/chấp nhận, Bytebase tự động chạy câu lệnh SQL DDL lên database đích `bytebase_test` và chuyển trạng thái sang `Deployed - Done`.

### 🧪 Test 2: Schema Drift Detection
- **Thao tác**: Chạy trực tiếp `ALTER TABLE customers ADD COLUMN drift_test_col VARCHAR(50);` qua SQL client/Terminal ngoài Bytebase.
- **Kết quả quan sát**:
  1. **Tự động cập nhật Schema History**: Bytebase cập nhật cấu trúc schema mới nhất khi thực hiện sync schema/schema snapshot.
  2. **Không tự động phân loại rủi ro drift**: Với các thay đổi non-breaking như `ADD COLUMN`, Bytebase cập nhật diff danh sách cột nhưng không cảnh báo rủi ro cao hay chặn công việc tự động.

### 🧪 Test 3: SQL Review & Phân loại rủi ro (Breaking Changes)
- **Thao tác**: Đề xuất câu lệnh rủi ro cao gây mất dữ liệu `ALTER TABLE orders DROP COLUMN note;` qua Issue của Bytebase.
- **Kết quả quan sát**:
  1. **Không tự động cảnh báo rủi ro mặc định**: Ở bản Community Edition với cấu hình chuẩn, ô `CHECKS` vẫn báo `Success` cho câu lệnh `DROP COLUMN` mà không hiển thị cảnh báo đỏ/cam về mất dữ liệu.
  2. **Không tự động phân loại ChangeType**: Bytebase không phân loại cụ thể như `ChangeType.DROP_COLUMN` hay nhãn `breaking` trừ khi người dùng tự bật và cấu hình bộ quy tắc SQL Review Policy nâng cao.
  3. **Không tự động chặn thực thi (ở môi trường Test)**: Do quy trình review mặc định ở môi trường Test là `Review Skipped`, Bytebase cho phép thực thi câu lệnh xóa cột này trực tiếp mà không bắt buộc có bước xác nhận rủi ro mất dữ liệu.

### 🧪 Test 4: Cơ chế thông báo (Notifications & Integrations)
- **Thao tác**: Mở giao diện `Project Settings -> Webhooks` kiểm tra các kênh thông báo được hỗ trợ.
- **Kết quả quan sát**:
  1. **Các kênh hỗ trợ sẵn**: Hỗ trợ 8 kênh chính chủ: Slack, Discord, MS Teams, Google Chat, DingTalk, Feishu, Lark, WeCom.
  2. **Không có Telegram trực tiếp**: Không hỗ trợ sẵn tùy chọn tích hợp Telegram Bot (để dùng Telegram phải cấu hình qua Custom Webhook adapter trung gian).
  3. **Trigger đa dạng**: Hỗ trợ bắn thông báo theo các sự kiện: `Issue creation`, `Issue approval needed`, `Issue approved`, `Pipeline failed`, `Pipeline completed`.

---

## 4. Kết luận Đánh giá cho Chương III Đồ án

1. **Điểm mạnh tương đồng**: Bytebase thể hiện rất tốt vai trò một công cụ Database DevOps chuyên nghiệp với quy trình duyệt Issue rõ ràng và khả năng lưu trữ lịch sử snapshot schema chi tiết.
2. **Giá trị nổi bật của Hệ thống Đã Xây (`schema-evolution-core`)**:
   - **Tự động hóa sinh DDL & Đồng bộ dị thể**: Bytebase chỉ chạy SQL DDL do người dùng nhập hoặc có sẵn trên Git cho cùng loại DB. Trong khi đó, hệ thống đã xây có khả năng **tự suy luận diff và tự sinh DDL chuyển đổi giữa các hệ CSDL khác loại (Heterogeneous Sync: Postgres/MySQL ↔ ClickHouse / MongoDB)**.
   - **Phân loại rủi ro thông minh**: Hệ thống đã xây tích hợp sẵn cơ chế phân loại 14 loại `ChangeType` để chủ động bảo vệ database đích khỏi các thay đổi `breaking_changes` (như `DROP COLUMN`, `MODIFY_TYPE`), trong khi Bytebase bản Community tiêu chuẩn cần cấu hình thủ công phức tạp hơn để chặn các câu lệnh này.
   - **Tích hợp Telegram linh hoạt**: Cho phép duyệt/từ chối thay đổi trực tiếp qua chat Telegram mà không bắt buộc mở Web Admin.
