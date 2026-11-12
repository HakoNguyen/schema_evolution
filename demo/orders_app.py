"""
App bán hàng giả lập (vai team ứng dụng): ghi đơn hàng vào MongoDB shop.orders, khoảng 5 đơn/giây.

    python -m demo.orders_app

Mongo không có ALTER TABLE: "đổi schema" là app ra bản mới, ghi document có hình dạng khác.
Bản đang chạy nằm trong document shop.app_release {_id: "orders-app"}; demo.scenario sửa nó,
app đọc lại trước MỖI lần ghi nên thay đổi có hiệu lực ngay, giống vừa deploy bản mới.
"""
import random
import time
from datetime import datetime, timezone

import pymongo
from bson import ObjectId

import demo  # noqa: F401  (UTF-8 console)
from demo import config as c

# Bản v1 (baseline). Các cờ khác chỉ do demo.scenario bật.
DEFAULT_RELEASE = {"coupon_code": False, "note": True, "amount_as_string": False, "paused": False}
CUSTOMERS = ["an", "binh", "chi", "dung", "giang", "hoa", "khanh", "linh"]
NOTES = ["giao giờ hành chính", "gọi trước khi giao", "để ở bảo vệ", "không cần hoá đơn"]


def make_order(release: dict) -> dict:
    amount = round(random.uniform(5, 500), 2)
    doc = {
        # _id chuỗi tăng dần theo thời gian (ObjectId bắt đầu bằng timestamp): engine lấy mẫu document mới nhất theo _id.
        "_id": f"ord-{ObjectId()}",
        "customer": random.choice(CUSTOMERS),
        "amount": f"{amount:.2f}" if release.get("amount_as_string") else amount,
        "status": random.choice(["paid", "pending", "shipped"]),
        "created_at": datetime.now(timezone.utc),
    }
    if release.get("note", True):
        doc["note"] = random.choice(NOTES)
    if release.get("coupon_code"):
        doc["coupon_code"] = random.choice(["NONE", "SALE10", "FREESHIP"])
    return doc


def main():
    db = pymongo.MongoClient(**c.MONGO)[c.MONGO_DB]
    print(f"[orders-app] ghi đơn hàng vào mongo {c.MONGO_DB}.{c.ORDERS_TABLE} (localhost:{c.MONGO['port']})")
    written, last_report, last_release = 0, time.monotonic(), None
    while True:
        release = db[c.RELEASE_COLLECTION].find_one({"_id": c.ORDERS_APP}) or DEFAULT_RELEASE
        flags = {k: v for k, v in release.items() if k != "_id"}
        if flags != last_release:
            print(f"[orders-app] bản đang chạy: {flags}")
            last_release = flags
        if not release.get("paused"):
            db[c.ORDERS_TABLE].insert_one(make_order(release))
            written += 1
        now = time.monotonic()
        if now - last_report >= 5:
            print(f"[orders-app] {written / (now - last_report):4.1f} đơn/s")
            written, last_report = 0, now
        time.sleep(0.2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[orders-app] stopped")
