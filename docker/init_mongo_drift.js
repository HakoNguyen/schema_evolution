// init_mongo_drift.js
// Giả lập Schema Drift kiểu Mongo: KHÔNG DROP/ALTER gì cả — chỉ insert
// 1 document MỚI có thêm field "phone" mà các document cũ không có.
// Đây đúng bản chất schema-less thật của Mongo (khác hẳn cách SQL giả
// lập drift bằng DROP TABLE + CREATE TABLE lại).
//
// Chạy SAU khi đã chạy init_mongo_source.js và scheduler.py đã quét
// baseline ít nhất 1 lần (status "initialized").
//
//   mongosh "mongodb://localhost:27017/sample_db" --file init_mongo_drift.js
//
// Sau khi chạy xong, đợi 1 chu kỳ scheduler.py — kỳ vọng phát hiện
// ADD_COLUMN "phone" (non-breaking, vì field mới luôn nullable=True do
// document cũ không có) và tự động ALTER TABLE bên ClickHouse.

db = db.getSiblingDB("sample_db");

db.users.insertOne({
  name: "David Pham",
  email: "david@example.com",
  age: 35,
  is_vip: false,
  created_at: new Date(),
  phone: "0901234567",   // field MỚI, document cũ không có field này
});

print("Da them 1 document moi co field 'phone' (gia lap schema drift)");
