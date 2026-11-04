-- Enforce non-negative values regardless of the insertion tool.
BEGIN;

ALTER TABLE ingredients
ADD CONSTRAINT ingredients_stock_nonnegative
CHECK (stock_quantity >= 0);

ALTER TABLE orders
ADD CONSTRAINT orders_total_nonnegative
CHECK (total_amount >= 0);

COMMIT;