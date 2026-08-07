// init_mongo_source.js
// Khởi tạo baseline: insert vài document mẫu vào collection "users".
// Chạy 1 lần đầu tiên, TRƯỚC khi chạy scheduler.py lần đầu.
//
// Cách chạy (đứng ngoài container, máy đã cài mongosh, hoặc exec vào
// container mongo_db nếu chưa cài mongosh trên máy host):
//
//   mongosh "mongodb://localhost:27017/sample_db" --file init_mongo_source.js
//
// Hoặc nếu chưa cài mongosh trên máy host, chạy qua Docker luôn:
//
//   docker cp init_mongo_source.js mongo_db:/tmp/init_mongo_source.js
//   docker exec -it mongo_db mongosh sample_db --file /tmp/init_mongo_source.js
//
// Đổi "sample_db" nếu ông dùng tên database khác trong config.yaml.

db = db.getSiblingDB("sample_db");

// Dọn sạch trước khi insert — tránh nhân đôi document nếu chạy lại
// script này nhiều lần trong lúc test.
db.users.deleteMany({});

db.users.insertMany([
  {
    name: "Alice Nguyen",
    email: "alice@example.com",
    age: 30,
    is_vip: true,
    created_at: new Date(),
  },
  {
    name: "Bob Tran",
    email: "bob@example.com",
    age: 25,
    is_vip: false,
    created_at: new Date(),
  },
  {
    name: "Carol Le",
    email: "carol@example.com",
    age: 28,
    is_vip: true,
    created_at: new Date(),
  },
]);

print("Da insert " + db.users.countDocuments() + " document vao collection 'users'");
