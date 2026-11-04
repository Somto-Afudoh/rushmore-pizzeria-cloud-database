# Imports and Faker setup
import yaml
import json
import psycopg2
from pathlib import Path
from faker import Faker
from decimal import Decimal
from psycopg2.extras import execute_values

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

    
# Validate customer records before loading them
def validate_customers(records):
    long_phones = [
        row for row in records
        if len(row['phone_number']) > 20
    ]

    if long_phones:
        raise ValueError(
            f"Data quality check failed: "
            f"{len(long_phones)} phone numbers exceed 20 characters."
        )

    print(f"Customer phone-length check passed for {len(records)} records.")


# Validate store records before loading them
def validate_stores(records):
    long_phones = [
        row for row in records
        if len(row['phone_number']) > 20
    ]

    if long_phones:
        raise ValueError(
            f"Data quality check failed: "
            f"{len(long_phones)} phone numbers exceed 20 characters."
        )

    print(f"Stores phone-length check passed for {len(records)} records.")


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
        RETURNING customer_id, email, created_at;
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
            'email': email,
            'created_at': created_at
        }
        for customer_id, email, created_at in returned_rows
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
                    SELECT customer_id, email, created_at
                    FROM customers
                    ORDER BY customer_id;
                """,
                load_customers
            )

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

        # Report success only after the transaction commits.
        print("Database preparation completed successfully.")
        print(f"Customers available: {len(loaded_customers)}")
        print(f"Stores available: {len(loaded_stores)}")
        print(f"Menu items available: {len(loaded_menu_items)}")
        print(f"Ingredients available: {len(loaded_ingredients)}")

    finally:
        connection.close()


# Run the workflow when this script is executed directly.
if __name__ == "__main__":
    main()
    