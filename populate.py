# Imports and Faker setup
import yaml
import json
import psycopg2
from pathlib import Path
from faker import Faker
from decimal import Decimal
from psycopg2.extras import execute_values
from datetime import datetime

fake = Faker()

# Read private connection settings and connect to Azure PostgreSQL.
def create_connection():
    config_path = Path(__file__).resolve().parent / "config.yaml"

    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    connection = psycopg2.connect(
        host=config['host'],
        user=config['user'],
        dbname=config['database'],
        password=config['password'],
        port=config['port'],
        sslmode='require',
        connect_timeout=10
    )

    print("Connected to PostgreSQL.")
    return connection


# Generate customer records
def generate_customers(number_of_customers):
    records = []

    for _ in range(number_of_customers):
        phone_number = fake.unique.phone_number()

        while len(phone_number) > 20:
            phone_number = fake.unique.phone_number()

        row = {
            'first_name': fake.first_name(),
            'last_name': fake.last_name(),
            'email': fake.unique.email(),
            'phone_number': phone_number,
            'created_at': fake.date_time_this_year()
        }

        records.append(row)
    return records


# Generate Store records
def generate_stores(number_of_stores):
    records = []

    for _ in range(number_of_stores):
        phone_number = fake.unique.phone_number()

        while len(phone_number) > 20:
            phone_number = fake.unique.phone_number()

        row = {
            'address': fake.street_address(),
            'city': fake.city(),
            'phone_number': phone_number,
            'opened_at': fake.date_time_between(
                start_date='-5y',
                end_date='-2y'
            )
        }

        records.append(row)
    return records


# Read the fixed menu catalogue from the JSON file
# This loads records into Python, not into PostgreSQL.
def load_menu_items():
    file_path = (
        Path(__file__).resolve().parent / "data" / "menu_items.json"
    )

    with file_path.open("r", encoding="utf-8") as file:
        return json.load(file)


# Read the ingredient catalogue and generate stock quantities.
def generate_ingredients():
    file_path = (
        Path(__file__).resolve().parent / "data" / "ingredients.json"
    )

    with file_path.open("r", encoding="utf-8") as file:
        catalogue = json.load(file)

    records = []

    for ingredient in catalogue:
        # Countable supplies use whole numbers.
        if ingredient['unit'] == 'units':
            stock_quantity = fake.random_int(min=0, max=500)
        else:
            # Weight and volume can include two decimal places.
            # Decimal values fit PostgreSQL NUMERIC without float rounding.
            stock_quantity = fake.pydecimal(
                left_digits=3,
                right_digits=2,
                min_value=0,
                max_value=200
            )

        # Match the columns in the ingredients table.
        # PostgreSQL generates ingredient_id automatically.
        row = {
            'name': ingredient['name'],
            'stock_quantity': stock_quantity,
            'unit': ingredient['unit']
        }

        records.append(row)

    return records


# Generate orders using existing customer and store records.
def generate_orders(number_of_orders, customers, stores):
    if not customers or not stores:
        raise ValueError("Orders require existing customers and stores.")

    records = []

    for _ in range(number_of_orders):
        customer = fake.random_element(elements=customers)
        store = fake.random_element(elements=stores)

        # An order cannot precede registration or store opening.
        earliest_order_date = max(
            customer['created_at'],
            store['opened_at']
        )

        row = {
            'customer_id': customer['customer_id'],
            'store_id': store['store_id'],
            'order_timestamp': fake.date_time_between(
                start_date=earliest_order_date,
                end_date='now'
            ),
            # Simulated total because the schema has no item prices.
            'total_amount': fake.pydecimal(
                left_digits=3,
                right_digits=2,
                min_value=5,
                max_value=150
            )
        }

        records.append(row)

    return records


# Generate three distinct menu-item lines for each order.
def generate_order_items(orders, menu_items):
    if not orders:
        raise ValueError("Order items require existing orders.")

    if len(menu_items) < 3:
        raise ValueError("At least three menu items are required.")

    records = []

    for order in orders:
        # Sampling without replacement prevents duplicate items per order.
        selected_items = fake.random_elements(
            elements=menu_items,
            length=3,
            unique=True
        )

        for item in selected_items:
            row = {
                'order_id': order['order_id'],
                'item_id': item['item_id'],
                'quantity': fake.random_int(min=1, max=3)
            }

            records.append(row)

    return records


# Check required text fields, column lengths and unique values.
def validate_text_fields(records, table_label, field_limits, unique_fields):
    if not isinstance(records, list) or not records:
        raise ValueError(
            f"{table_label}: expected a non-empty list of records."
        )

    seen_values = {field: set() for field in unique_fields}

    for position, row in enumerate(records, start=1):
        if not isinstance(row, dict):
            raise ValueError(
                f"{table_label} record {position}: expected a dictionary."
            )

        for field, max_length in field_limits.items():
            value = row.get(field)

            # Reject missing fields, NULL, non-text values and blank text.
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"{table_label} record {position}: "
                    f"{field} must be a non-empty string."
                )

            if len(value) > max_length:
                raise ValueError(
                    f"{table_label} record {position}: "
                    f"{field} exceeds {max_length} characters."
                )

            if field in seen_values:
                # Compare the actual values, as generated.
                if value in seen_values[field]:
                    raise ValueError(
                        f"{table_label} record {position}: "
                        f"duplicate {field}."
                    )

                seen_values[field].add(value)


# Validate customer records before loading them.
def validate_customers(records):
    validate_text_fields(
        records,
        table_label="Customers",
        field_limits={
            'first_name': 100,
            'last_name': 100,
            'email': 255,
            'phone_number': 20
        },
        unique_fields={'email', 'phone_number'}
    )

    # Check the project's minimum customer volume.
    if len(records) < 6000:
        raise ValueError(
            "Customer validation failed: expected at least 6,000 records."
        )

    now = datetime.now()

    for position, row in enumerate(records, start=1):
        created_at = row.get('created_at')

        # Our generated dataset requires a registration timestamp.
        if not isinstance(created_at, datetime):
            raise ValueError(
                f"Customer {position}: created_at must be a datetime."
            )

        # Match the naive timestamps used by our generation functions.
        if created_at.tzinfo is not None:
            raise ValueError(
                f"Customer {position}: expected a timezone-naive timestamp."
            )

        if created_at > now:
            raise ValueError(
                f"Customer {position}: created_at cannot be in the future."
            )

    print(f"Customer validation passed for {len(records)} records.")


# Validate store records before loading them.
def validate_stores(records):
    validate_text_fields(
        records,
        table_label="Stores",
        field_limits={
            'address': 255,
            'city': 100,
            'phone_number': 20
        },
        unique_fields={'phone_number'}
    )

    # Check the project's store-volume target.
    if not 3 <= len(records) <= 5:
        raise ValueError(
            "Store validation failed: expected between 3 and 5 records."
        )

    now = datetime.now()

    for position, row in enumerate(records, start=1):
        opened_at = row.get('opened_at')

        if not isinstance(opened_at, datetime):
            raise ValueError(
                f"Store {position}: opened_at must be a datetime."
            )

        if opened_at.tzinfo is not None:
            raise ValueError(
                f"Store {position}: expected a timezone-naive timestamp."
            )

        if opened_at > now:
            raise ValueError(
                f"Store {position}: opened_at cannot be in the future."
            )

    print(f"Store validation passed for {len(records)} records.")


# Validate the menu catalogue before inserting it into PostgreSQL
def validate_menu_items(records):
    # Ensure the JSON contains a list of menu items.
    if not isinstance(records, list):
        raise ValueError(
            "Menu validation failed: expected a list of menu items."
        )

    #Check the project's target volume.
    if not 20 <= len(records) <= 30:
        raise ValueError(
            "Menu validation failed: expected between 20 and 30 items."
        )

    required_keys = {'name', 'category', 'size'}
    allowed_categories = {'Pizza', 'Drink', 'Side', 'Dessert'}
    seen_items = set()

    for position, row in enumerate(records, start=1):
        # Each menu item must be a dictionary.
        if not isinstance(row, dict):
            raise ValueError(
                f"Menu item {position}: expected a dictionary."
            )

        # Check that all expected fields are present.
        missing_keys = required_keys - row.keys()

        if missing_keys:
            raise ValueError(
                f"Menu item {position}: missing fields "
                f"{', '.join(sorted(missing_keys))}."
            )

        # Name and category must contain meaningful text.
        for field, max_length in [('name', 150), ('category', 50)]:
            value = row[field]

            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"Menu item {position}: {field} must be "
                    "a non-empty string."
                )

            if len(value) > max_length:
                raise ValueError(
                    f"Menu item {position}: {field} exceeds "
                    f"{max_length} characters."
                )

        # The database allows size to be NULL.
        # When provided, it must be text within VARCHAR(20).
        size = row['size']

        if size is not None:
            if not isinstance(size, str) or not size.strip():
                raise ValueError(
                    f"Menu item {position}: size must be "
                    "a non-empty string or None."
                )

            if len(size) > 20:
                raise ValueError(
                    f"Menu item {position}: size exceeds 20 characters."
                )

        # Enforce the catalogue's agreed category names.
        if row['category'] not in allowed_categories:
            raise ValueError(
                f"Menu item {position}: invalid category "
                f"'{row['category']}'. Expected Pizza, Drink, "
                "Side or Dessert."
            )

        # Ignore case and surrounding spaces when detecting duplicates.
        item_key = (
            row['name'].strip().casefold(),
            size.strip().casefold() if size is not None else None
        )

        if item_key in seen_items:
            raise ValueError(
                f"Menu item {position}: duplicate name-and-size "
                f"combination for '{row['name']}'."
            )

        seen_items.add(item_key)

    print(f"Menu validation passed for {len(records)} items.")


# Validate ingredient records before inserting them into PostgreSQL.
def validate_ingredients(records):
    if not isinstance(records, list):
        raise ValueError(
            "Ingredient validation failed: expected a list."
        )

    # Check the project's target volume.
    if not 40 <= len(records) <= 50:
        raise ValueError(
            "Ingredient validation failed: expected 40–50 ingredients."
        )

    required_keys = {'name', 'stock_quantity', 'unit'}
    allowed_units = {'kg', 'liters', 'units'}
    seen_names = set()

    for position, row in enumerate(records, start=1):
        if not isinstance(row, dict):
            raise ValueError(
                f"Ingredient {position}: expected a dictionary."
            )

        # All three columns are required.
        missing_keys = required_keys - row.keys()

        if missing_keys:
            raise ValueError(
                f"Ingredient {position}: missing fields "
                f"{', '.join(sorted(missing_keys))}."
            )

        # Reject NULL, blank text and values exceeding column lengths.
        for field, max_length in [('name', 100), ('unit', 20)]:
            value = row[field]

            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"Ingredient {position}: {field} must be "
                    "a non-empty string."
                )

            if len(value) > max_length:
                raise ValueError(
                    f"Ingredient {position}: {field} exceeds "
                    f"{max_length} characters."
                )

        # Detect duplicate names, ignoring case and surrounding spaces.
        name_key = row['name'].strip().casefold()

        if name_key in seen_names:
            raise ValueError(
                f"Ingredient {position}: duplicate name '{row['name']}'."
            )

        seen_names.add(name_key)

        # Enforce the catalogue's agreed measurement units.
        if row['unit'] not in allowed_units:
            raise ValueError(
                f"Ingredient {position}: unit must be "
                "'kg', 'liters' or 'units'."
            )

        quantity = row['stock_quantity']

        # Accept the types produced by our generation function.
        # Explicitly reject booleans, which Python treats as integers.
        if isinstance(quantity, bool) or not isinstance(
            quantity, (int, Decimal)
        ):
            raise ValueError(
                f"Ingredient {position}: stock_quantity must be "
                "an integer or Decimal."
            )

        quantity = Decimal(quantity)

        # Reject special Decimal values such as NaN and Infinity.
        if not quantity.is_finite():
            raise ValueError(
                f"Ingredient {position}: stock_quantity must be finite."
            )

        # NUMERIC(10, 2) allows eight digits before the decimal point.
        # Our business rule also prevents negative stock.
        if not Decimal('0') <= quantity <= Decimal('99999999.99'):
            raise ValueError(
                f"Ingredient {position}: stock_quantity must be "
                "between 0 and 99999999.99."
            )

        # Reject values that would require rounding to two decimal places.
        if quantity != quantity.quantize(Decimal('0.01')):
            raise ValueError(
                f"Ingredient {position}: stock_quantity must have "
                "no more than two decimal places."
            )

        # Countable supplies must have whole-number quantities.
        if row['unit'] == 'units' and quantity != quantity.to_integral_value():
            raise ValueError(
                f"Ingredient {position}: stock measured in 'units' "
                "must be a whole number."
            )

    print(f"Ingredient validation passed for {len(records)} records.")


# Check relationships, dates and totals before loading orders.
def validate_orders(records, customers, stores, expected_count):
    if len(records) != expected_count:
        raise ValueError(
            f"Order validation failed: expected {expected_count} records."
        )

    # Lookups let us check IDs and dates efficiently.
    customer_dates = {
        row['customer_id']: row['created_at']
        for row in customers
    }
    store_dates = {
        row['store_id']: row['opened_at']
        for row in stores
    }

    required_keys = {
        'customer_id', 'store_id', 'order_timestamp', 'total_amount'
    }
    now = datetime.now()

    for position, row in enumerate(records, start=1):
        if not isinstance(row, dict) or required_keys - row.keys():
            raise ValueError(
                f"Order {position}: missing required fields."
            )

        customer_id = row['customer_id']
        store_id = row['store_id']

        if customer_id not in customer_dates:
            raise ValueError(f"Order {position}: unknown customer ID.")

        if store_id not in store_dates:
            raise ValueError(f"Order {position}: unknown store ID.")

        timestamp = row['order_timestamp']

        if not isinstance(timestamp, datetime):
            raise ValueError(f"Order {position}: invalid timestamp.")

        earliest_date = max(
            customer_dates[customer_id],
            store_dates[store_id]
        )

        if not earliest_date <= timestamp <= now:
            raise ValueError(
                f"Order {position}: timestamp is outside the valid range."
            )

        amount = row['total_amount']

        if not isinstance(amount, Decimal) or not amount.is_finite():
            raise ValueError(
                f"Order {position}: total must be a finite Decimal."
            )

        if not Decimal('0') <= amount <= Decimal('99999999.99'):
            raise ValueError(
                f"Order {position}: total is outside NUMERIC(10,2) limits."
            )

        if amount != amount.quantize(Decimal('0.01')):
            raise ValueError(
                f"Order {position}: total exceeds two decimal places."
            )

    print(f"Order validation passed for {len(records)} records.")


# Validate foreign keys, quantities and composite-key uniqueness.
def validate_order_items(records, orders, menu_items):
    expected_count = len(orders) * 3

    if len(records) != expected_count:
        raise ValueError(
            f"Order-item validation failed: expected "
            f"{expected_count} records."
        )

    valid_order_ids = {row['order_id'] for row in orders}
    valid_item_ids = {row['item_id'] for row in menu_items}

    required_keys = {'order_id', 'item_id', 'quantity'}
    seen_pairs = set()
    lines_per_order = {
        order_id: 0 for order_id in valid_order_ids
    }

    for position, row in enumerate(records, start=1):
        if not isinstance(row, dict) or required_keys - row.keys():
            raise ValueError(
                f"Order item {position}: missing required fields."
            )

        order_id = row['order_id']
        item_id = row['item_id']
        quantity = row['quantity']

        # Check that both referenced records exist.
        if order_id not in valid_order_ids:
            raise ValueError(
                f"Order item {position}: unknown order ID."
            )

        if item_id not in valid_item_ids:
            raise ValueError(
                f"Order item {position}: unknown menu-item ID."
            )

        # Reject NULL, booleans, fractions and non-positive quantities.
        if type(quantity) is not int or not 1 <= quantity <= 2147483647:
            raise ValueError(
                f"Order item {position}: quantity must be a positive "
                "integer within PostgreSQL INTEGER limits."
            )

        # Match the table's composite primary key.
        pair = (order_id, item_id)

        if pair in seen_pairs:
            raise ValueError(
                f"Order item {position}: duplicate order/item pair {pair}."
            )

        seen_pairs.add(pair)
        lines_per_order[order_id] += 1

    # Enforce our generation rule, beyond the database constraints.
    if any(count != 3 for count in lines_per_order.values()):
        raise ValueError(
            "Order-item validation failed: each order needs three lines."
        )

    print(f"Order-item validation passed for {len(records)} records.")


# Insert customers in batches and return their database-generated IDs.
def load_customers(connection, records):
    if not records:
        raise ValueError("No customer records supplied for loading.")

    # Tuple values follow the same order as the INSERT columns below.
    values = [
        (
            row['first_name'],
            row['last_name'],
            row['email'],
            row['phone_number'],
            row['created_at']
        )
        for row in records
    ]

    query = """
        INSERT INTO customers (
            first_name,
            last_name,
            email,
            phone_number,
            created_at
        )
        VALUES %s
        RETURNING customer_id, first_name, last_name, email, phone_number, created_at;
    """

    with connection.cursor() as cursor:
        # fetch=True collects returned rows from every batch.
        returned_rows = execute_values(
            cursor,
            query,
            values,
            page_size=1000,
            fetch=True
        )

    # Each returned record carries its own identity and registration date.
    # We do not assume returned rows match the input order.
    return [
        {
            'customer_id': customer_id,
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'phone_number': phone_number,
            'created_at': created_at
        }
        for customer_id, first_name, last_name, email, phone_number, created_at in returned_rows
    ]


# Reuse a populated table or load it if empty.
# The SELECT statements passed here are fixed queries from our code.
def reuse_or_load(connection, records, table_label, select_query, loader):
    with connection.cursor() as cursor:
        cursor.execute(select_query)

        column_names = [
            description[0] for description in cursor.description
        ]

        existing_records = [
            dict(zip(column_names, row))
            for row in cursor.fetchall()
        ]

    if existing_records:
        # Stop if the existing data doesn't match the expected volume.
        if len(existing_records) != len(records):
            raise ValueError(
                f"{table_label}: found {len(existing_records)} existing "
                f"records, but expected {len(records)}. "
                "No additional records were inserted into this table."
            )

        print(
            f"{table_label}: reusing "
            f"{len(existing_records)} existing records."
        )
        return existing_records

    # The table is empty, so insert the prepared records.
    loaded_records = loader(connection, records)

    print(
        f"{table_label}: prepared "
        f"{len(loaded_records)} new records for commit."
    )
    return loaded_records


# Insert stores and return their IDs and opening dates for order generation.
def load_stores(connection, records):
    values = [
        (
            row['address'],
            row['city'],
            row['phone_number'],
            row['opened_at']
        )
        for row in records
    ]

    query = """
        INSERT INTO stores (
            address, city, phone_number, opened_at
        )
        VALUES %s
        RETURNING store_id, address, city, phone_number, opened_at;
    """

    with connection.cursor() as cursor:
        returned_rows = execute_values(
            cursor, query, values, page_size=1000, fetch=True
        )

    return [
        {
            'store_id': store_id,
            'address': address,
            'city': city,
            'phone_number': phone_number,
            'opened_at': opened_at
        }
        for store_id, address, city, phone_number, opened_at
        in returned_rows
    ]


# Insert the menu catalogue and return the generated item IDs.
def load_menu_items_to_db(connection, records):
    values = [
        (row['name'], row['category'], row['size'])
        for row in records
    ]

    query = """
        INSERT INTO menu_items (name, category, size)
        VALUES %s
        RETURNING item_id, name, category, size;
    """

    with connection.cursor() as cursor:
        returned_rows = execute_values(
            cursor, query, values, page_size=1000, fetch=True
        )

    return [
        {
            'item_id': item_id,
            'name': name,
            'category': category,
            'size': size
        }
        for item_id, name, category, size in returned_rows
    ]


# Insert ingredients and their generated opening stock quantities.
def load_ingredients(connection, records):
    values = [
        (row['name'], row['stock_quantity'], row['unit'])
        for row in records
    ]

    query = """
        INSERT INTO ingredients (name, stock_quantity, unit)
        VALUES %s
        RETURNING ingredient_id, name, stock_quantity, unit;
    """

    with connection.cursor() as cursor:
        returned_rows = execute_values(
            cursor, query, values, page_size=1000, fetch=True
        )

    return [
        {
            'ingredient_id': ingredient_id,
            'name': name,
            'stock_quantity': stock_quantity,
            'unit': unit
        }
        for ingredient_id, name, stock_quantity, unit in returned_rows
    ]


# Bulk insert orders and retrieve their actual database IDs.
def load_orders(connection, records):
    values = [
        (
            row['customer_id'],
            row['store_id'],
            row['order_timestamp'],
            row['total_amount']
        )
        for row in records
    ]

    query = """
        INSERT INTO orders (
            customer_id, store_id, order_timestamp, total_amount
        )
        VALUES %s
        RETURNING
            order_id, customer_id, store_id,
            order_timestamp, total_amount;
    """

    with connection.cursor() as cursor:
        returned_rows = execute_values(
            cursor, query, values, page_size=1000, fetch=True
        )

    return [
        {
            'order_id': order_id,
            'customer_id': customer_id,
            'store_id': store_id,
            'order_timestamp': order_timestamp,
            'total_amount': total_amount
        }
        for (
            order_id, customer_id, store_id,
            order_timestamp, total_amount
        ) in returned_rows
    ]


# Bulk insert order lines and return the inserted records.
def load_order_items(connection, records):
    values = [
        (row['order_id'], row['item_id'], row['quantity'])
        for row in records
    ]

    query = """
        INSERT INTO order_items (order_id, item_id, quantity)
        VALUES %s
        RETURNING order_id, item_id, quantity;
    """

    with connection.cursor() as cursor:
        returned_rows = execute_values(
            cursor,
            query,
            values,
            page_size=1000,
            fetch=True
        )

    return [
        {
            'order_id': order_id,
            'item_id': item_id,
            'quantity': quantity
        }
        for order_id, item_id, quantity in returned_rows
    ]


# Coordinate generation, validation and small preview
def main():
    # Generate records for each table.
    customers = generate_customers(6500)
    stores = generate_stores(5)
    menu_items = load_menu_items()
    ingredients = generate_ingredients()

    # Check records before attempting to insert them.
    validate_customers(customers)
    validate_stores(stores)
    validate_menu_items(menu_items)
    validate_ingredients(ingredients)

    # Confirm the generated record counts
    print(f"{len(customers)} customer records generated.")
    print(f"{len(stores)} store records generated.")
    print(f"{len(menu_items)} menu items loaded from JSON.")
    print(f"{len(ingredients)} ingredient records generated.")

    # Preview first 5 rows for customers
    print("Customer sample:")
    for row in customers[:5]:
        print(row)

    # Preview first 5 rows for stores
    print("Store sample:")
    for row in stores[:5]:
        print(row)

    # Preview first 5 rows for ingredients
    print("Ingredient sample:")
    for row in ingredients[:5]:
        print(row)


    # Connect after generating and validating the records.
    connection = create_connection()

    try:
        # All new inserts in this block commit together.
        # If any step fails, the new inserts are rolled back.
        with connection:
            loaded_customers = reuse_or_load(
                connection,
                customers,
                "Customers",
                """
                    SELECT customer_id, first_name, last_name, email, phone_number, created_at
                    FROM customers
                    ORDER BY customer_id;
                """,
                load_customers
            )
            validate_customers(loaded_customers)

            loaded_stores = reuse_or_load(
                connection,
                stores,
                "Stores",
                """
                    SELECT store_id, address, city, phone_number, opened_at
                    FROM stores
                    ORDER BY store_id;
                """,
                load_stores
            )
            validate_stores(loaded_stores)

            loaded_menu_items = reuse_or_load(
                connection,
                menu_items,
                "Menu items",
                """
                    SELECT item_id, name, category, size
                    FROM menu_items
                    ORDER BY item_id;
                """,
                load_menu_items_to_db
            )
            validate_menu_items(loaded_menu_items)

            loaded_ingredients = reuse_or_load(
                connection,
                ingredients,
                "Ingredients",
                """
                    SELECT ingredient_id, name, stock_quantity, unit
                    FROM ingredients
                    ORDER BY ingredient_id;
                """,
                load_ingredients
            )
            validate_ingredients(loaded_ingredients)

            # Prepare orders using the actual saved customer/store records.
            orders = generate_orders(
                30000, loaded_customers, loaded_stores
            )

            validate_orders(
                orders,
                loaded_customers,
                loaded_stores,
                expected_count=30000
            )

            # Load an empty orders table or reuse its existing records.
            loaded_orders = reuse_or_load(
                connection,
                orders,
                "Orders",
                """
                    SELECT
                        order_id, customer_id, store_id,
                        order_timestamp, total_amount
                    FROM orders
                    ORDER BY order_id;
                """,
                load_orders
            )
            validate_orders(
                loaded_orders,
                loaded_customers,
                loaded_stores,
                expected_count=30000
            )

            # Generate order lines using actual database IDs.
            order_items = generate_order_items(
                loaded_orders, loaded_menu_items
            )

            validate_order_items(
                order_items, loaded_orders, loaded_menu_items
            )

            # Load once or reuse the existing order lines.
            loaded_order_items = reuse_or_load(
                connection,
                order_items,
                "Order items",
                """
                    SELECT order_id, item_id, quantity
                    FROM order_items
                    ORDER BY order_id, item_id;
                """,
                load_order_items
            )

            # Also validate saved records when the table was reused.
            validate_order_items(
                loaded_order_items, loaded_orders, loaded_menu_items
            )

        # Report success only after the transaction commits.
        print("Database preparation completed successfully.")
        print(f"Customers available: {len(loaded_customers)}")
        print(f"Stores available: {len(loaded_stores)}")
        print(f"Menu items available: {len(loaded_menu_items)}")
        print(f"Ingredients available: {len(loaded_ingredients)}")
        print(f"Orders available: {len(loaded_orders)}")
        print(f"Order items available: {len(loaded_order_items)}")

    finally:
        connection.close()


# Run the workflow when this script is executed directly.
if __name__ == "__main__":
    main()
    