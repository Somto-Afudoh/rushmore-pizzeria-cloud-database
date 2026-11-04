# Imports and Faker setup
import yaml
import json
from pathlib import Path
from faker import Faker

fake = Faker()


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
#This loads records into Python, not into PostgreSQL.
def load_menu_items():
    file_path = (
        Path(__file__).resolve().parent / "data" / "menu_items.json"
    )

    with file_path.open("r", encoding="utf-8") as file:
        return json.load(file)

    
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


#Validate the menu catalogue before inserting it into PostgreSQL
def validate_menu_items(records):
    #Ensure the JSON contains a list of menu items.
    if not isinstance(records,list):
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


# Coordinate generation, validation and small preview
def main():
    # Generate records for each table.
    customers = generate_customers(6500)
    stores = generate_stores(5)
    menu_items = load_menu_items()

    # Check records before attempting to insert them.
    validate_customers(customers)
    validate_stores(stores)
    validate_menu_items(menu_items)

    # Confirm the generated record counts
    print(f"{len(customers)} customer records generated.")
    print(f"{len(stores)} store records generated.")
    print(f"{len(menu_items)} menu items loaded from JSON.")

    # Preview first 5 rows for customers
    print("Customer sample:")
    for row in customers[:5]:
        print(row)

    # Preview first 5 rows for stores
    print("Store sample:")
    for row in stores[:5]:
        print(row)


# Run the workflow when this script is executed directly.
if __name__ == "__main__":
    main()