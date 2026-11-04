-- Identify indexes already created by primary keys,
-- UNIQUE constraints or previous manual changes.
SELECT
    tablename AS table_name,
    indexname AS index_name,
    indexdef AS definition
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN (
      'customers',
      'stores',
      'menu_items',
      'ingredients',
      'orders',
      'order_items'
  )
ORDER BY tablename, indexname;

-- Give the query planner current information about the loaded data.
ANALYZE public.orders;

-- Baseline: retrieve a customer's order history.
EXPLAIN (ANALYZE, BUFFERS)
SELECT
    order_id,
    order_timestamp,
    store_id,
    total_amount
FROM public.orders
WHERE customer_id = 2958
ORDER BY order_timestamp DESC;

SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename = 'orders';

-- Support customer filtering and newest-first order history.
CREATE INDEX idx_orders_customer_timestamp
ON public.orders (customer_id, order_timestamp DESC);

ANALYZE public.orders;

-- Find a store ID
SELECT store_id, city
FROM stores
ORDER BY store_id;

-- Measure retrieval of a store's orders for October 2026.
EXPLAIN (ANALYZE, BUFFERS)
SELECT
    order_id,
    customer_id,
    store_id,
    order_timestamp,
    total_amount
FROM orders
WHERE store_id = 2
  AND order_timestamp >= TIMESTAMP '2026-10-01'
  AND order_timestamp < TIMESTAMP '2026-11-01'
ORDER BY order_timestamp DESC;

-- Support store-specific order history within a date range.
CREATE INDEX idx_orders_store_timestamp
ON public.orders (store_id, order_timestamp DESC);

ANALYZE public.orders;