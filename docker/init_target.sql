CREATE TABLE customers (
    id INT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL,          -- WIDEN_TYPE: 100 -> 150 (non-breaking)
    phone VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    loyalty_tier VARCHAR(20)              -- ADD_COLUMN mới (non-breaking)
);

CREATE TABLE orders (
    id INT PRIMARY KEY,
    customer_id INT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- note VARCHAR(255) đã bị xóa               -- DROP_COLUMN (breaking)
    total_amount INT NOT NULL
    -- FK fk_orders_customer đã bị xóa            -- DROP_FOREIGN_KEY (non-breaking)
);