CREATE TABLE stores (
	store_id SERIAL PRIMARY KEY,
	address VARCHAR(255) NOT NULL,
	city VARCHAR(100) NOT NULL,
	phone_number VARCHAR(20) UNIQUE NOT NULL,
	opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create Customers Table
CREATE TABLE customers (
	customer_id SERIAL PRIMARY KEY,
	first_name VARCHAR(100) NOT NULL,
	last_name VARCHAR(100) NOT NULL,
	email VARCHAR(255) UNIQUE NOT NULL,
	phone_number VARCHAR(20) UNIQUE NOT NULL,
	created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create Ingredients Table
CREATE TABLE ingredients (
	ingredient_id SERIAL PRIMARY KEY,
	name VARCHAR(100) UNIQUE NOT NULL,
	stock_quantity NUMERIC(10,2) NOT NULL DEFAULT 0,
	unit VARCHAR(20) NOT NULL
);

-- Create Menu_Items Table
CREATE TABLE menu_items (
	item_id SERIAL PRIMARY KEY,
	name VARCHAR(150) NOT NULL,
	category VARCHAR(50) NOT NULL,
	size VARCHAR(20)
);

--Create Orders Table
CREATE TABLE orders (
	order_id SERIAL PRIMARY KEY,
	customer_id INT REFERENCES customers(customer_id)
	ON DELETE SET NULL,
	store_id INT REFERENCES stores(store_id)
	ON DELETE RESTRICT,
	order_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
	total_amount NUMERIC(10,2) NOT NULL
);

-- Create Order_Items Table
CREATE TABLE order_items (
    order_id INTEGER NOT NULL
        REFERENCES orders(order_id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL
        REFERENCES menu_items(item_id) ON DELETE RESTRICT,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    PRIMARY KEY (order_id, item_id)
);
