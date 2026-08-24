-- Script khởi tạo database và schema độc lập cho Bytebase test
CREATE TABLE IF NOT EXISTS customers (
    id INT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL,
    phone VARCHAR(20),                -- nullable
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- test default
);

CREATE TABLE IF NOT EXISTS orders (
    id INT PRIMARY KEY,
    customer_id INT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    note VARCHAR(255),                -- nullable
    total_amount INT NOT NULL,
    CONSTRAINT fk_orders_customer
        FOREIGN KEY (customer_id) REFERENCES customers(id)
        ON DELETE CASCADE
);
