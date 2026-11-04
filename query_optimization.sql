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

