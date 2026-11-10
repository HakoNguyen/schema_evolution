CREATE TABLE customers (
    id INT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL,
    phone VARCHAR(20),                -- nullable, test cột nullable
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- test cột có default
);

CREATE TABLE orders (
    id INT PRIMARY KEY,
    customer_id INT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    note VARCHAR(255),                -- nullable, VARCHAR dài để test WIDEN_TYPE sau này
    total_amount INT NOT NULL,
    CONSTRAINT fk_orders_customer
        FOREIGN KEY (customer_id) REFERENCES customers(id)
        ON DELETE CASCADE
);