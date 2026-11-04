-- Inspect existing table constraints.
-- Includes primary keys, foreign keys, UNIQUE and CHECK constraints.
SELECT
    t.relname AS table_name,
    c.conname AS constraint_name,
    CASE c.contype
        WHEN 'p' THEN 'PRIMARY KEY'
        WHEN 'f' THEN 'FOREIGN KEY'
        WHEN 'u' THEN 'UNIQUE'
        WHEN 'c' THEN 'CHECK'
        ELSE c.contype::text
    END AS constraint_type,
    pg_get_constraintdef(c.oid) AS definition
FROM pg_constraint AS c
JOIN pg_class AS t
    ON t.oid = c.conrelid
JOIN pg_namespace AS n
    ON n.oid = t.relnamespace
WHERE n.nspname = 'public'
  AND t.relname IN (
      'customers',
      'stores',
      'menu_items',
      'ingredients',
      'orders',
      'order_items'
  )
ORDER BY table_name, constraint_type, constraint_name;


-- Inspect NOT NULL settings, data types and defaults separately.
SELECT
    table_name,
    column_name,
    data_type,
    character_maximum_length,
    numeric_precision,
    numeric_scale,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN (
      'customers',
      'stores',
      'menu_items',
      'ingredients',
      'orders',
      'order_items'
  )
ORDER BY table_name, ordinal_position;

-- Check existing data before adding non-negative constraints.
SELECT
    'negative ingredient stock' AS issue,
    COUNT(*) AS invalid_rows
FROM ingredients
WHERE stock_quantity < 0

UNION ALL

SELECT
    'negative order total',
    COUNT(*)
FROM orders
WHERE total_amount < 0;

--------------------------------------------------------------------

-- Test 1: reject negative ingredient stock
BEGIN;

UPDATE ingredients
SET stock_quantity = -1
WHERE ingredient_id = (
    SELECT MIN(ingredient_id)
    FROM ingredients
);


-- Test 2: reject a negative order total
BEGIN;

UPDATE orders
SET total_amount = -1
WHERE order_id = (
    SELECT MIN(order_id)
    FROM orders
);


-- Test 3: reject a zero order-item quantity
BEGIN;

UPDATE order_items
SET quantity = 0
WHERE (order_id, item_id) = (
    SELECT order_id, item_id
    FROM order_items
    ORDER BY order_id, item_id
    LIMIT 1
);

-- Test 4: Customer deletion: ON DELETE SET NULL
SELECT customer_id
FROM orders
WHERE customer_id IS NOT NULL
LIMIT 1;


-- Note these order IDs before deleting the customer. 1, 4016, 4546, 18542
BEGIN;

SELECT order_id, customer_id
FROM orders
WHERE customer_id = 2958;

DELETE FROM customers
WHERE customer_id = 2958;

-- The same orders should remain, with customer_id now NULL.
SELECT order_id, customer_id
FROM orders
WHERE customer_id IS NULL;

ROLLBACK;


-- Test 5: Store deletion: ON DELETE RESTRICT
BEGIN;

DELETE FROM stores
WHERE store_id = (
    SELECT store_id
    FROM orders
    WHERE store_id IS NOT NULL
    LIMIT 1
);

-- Test 6: Order deletion: ON DELETE CASCADE
SELECT order_id
FROM order_items
LIMIT 1;


BEGIN;

-- Confirm the order has item rows.
SELECT COUNT(*) AS items_before
FROM order_items
WHERE order_id = 1;

DELETE FROM orders
WHERE order_id = 1;

-- Its item rows should have been deleted automatically.
SELECT COUNT(*) AS items_after
FROM order_items
WHERE order_id = 1;

-- Test 7: Menu-item deletion: ON DELETE RESTRICT
BEGIN;

DELETE FROM menu_items
WHERE item_id = (
    SELECT item_id
    FROM order_items
    LIMIT 1
);


-- Population summary for all six tables.
SELECT 'customers' AS table_name, COUNT(*) AS row_count
FROM public.customers

UNION ALL
SELECT 'stores', COUNT(*)
FROM public.stores

UNION ALL
SELECT 'menu_items', COUNT(*)
FROM public.menu_items

UNION ALL
SELECT 'ingredients', COUNT(*)
FROM public.ingredients

UNION ALL
SELECT 'orders', COUNT(*)
FROM public.orders

UNION ALL
SELECT 'order_items', COUNT(*)
FROM public.order_items;