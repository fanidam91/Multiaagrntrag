-- Azure Databricks DDL Setup
-- Run this script in your Databricks SQL Warehouse editor or notebook to initialize the Delta Table.

CREATE TABLE IF NOT EXISTS orders (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    order_id STRING NOT NULL,
    customer_name STRING NOT NULL,
    email STRING NOT NULL,
    phone STRING NOT NULL,
    order_date TIMESTAMP NOT NULL,
    status STRING NOT NULL,
    total_amount DOUBLE NOT NULL,
    shipping_address STRING NOT NULL,
    city STRING NOT NULL,
    zip_code STRING NOT NULL,
    country STRING NOT NULL,
    carrier STRING,
    tracking_number STRING,
    estimated_delivery DATE,
    items STRING NOT NULL, -- Stored as JSON string
    support_notes STRING   -- Multiline trace history logs
)
USING delta;

-- Optimization for RAG / Search:
-- OPTIMIZE orders ZORDER BY (order_id, customer_name, status);
