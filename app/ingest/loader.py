import csv

from sqlalchemy import Column, Float, Integer, MetaData, String, Table, insert

METADATA = MetaData()

TABLES = {
    "customers": Table(
        "customers", METADATA,
        Column("customer_id", Integer, primary_key=True),
        Column("workspace_id", String, nullable=False),
        Column("name", String, nullable=False),
        Column("city", String, nullable=False),
        Column("signup_date", String, nullable=False),
    ),
    "products": Table(
        "products", METADATA,
        Column("product_id", Integer, primary_key=True),
        Column("workspace_id", String, nullable=False),
        Column("sku", String, nullable=False),
        Column("name", String, nullable=False),
        Column("category", String, nullable=False),
        Column("price", Float, nullable=False),
    ),
    "orders": Table(
        "orders", METADATA,
        Column("order_id", Integer, primary_key=True),
        Column("workspace_id", String, nullable=False),
        Column("customer_id", Integer, nullable=False),
        Column("order_date", String, nullable=False),
        Column("city", String, nullable=False),
    ),
    "order_items": Table(
        "order_items", METADATA,
        Column("order_item_id", Integer, primary_key=True),
        Column("workspace_id", String, nullable=False),
        Column("order_id", Integer, nullable=False),
        Column("product_id", Integer, nullable=False),
        Column("quantity", Integer, nullable=False),
        Column("unit_price", Float, nullable=False),
    ),
    "returns": Table(
        "returns", METADATA,
        Column("return_id", Integer, primary_key=True),
        Column("workspace_id", String, nullable=False),
        Column("order_item_id", Integer, nullable=False),
        Column("return_date", String, nullable=False),
        Column("quantity", Integer, nullable=False),
        Column("reason", String, nullable=False),
    ),
}

# column -> python type used to cast values read back out of the CSV
COLUMN_TYPES = {
    "customers": {"customer_id": int, "name": str, "city": str, "signup_date": str},
    "products": {"product_id": int, "sku": str, "name": str, "category": str, "price": float},
    "orders": {"order_id": int, "customer_id": int, "order_date": str, "city": str},
    "order_items": {
        "order_item_id": int, "order_id": int, "product_id": int,
        "quantity": int, "unit_price": float,
    },
    "returns": {
        "return_id": int, "order_item_id": int, "return_date": str,
        "quantity": int, "reason": str,
    },
}

LOAD_ORDER = ["customers", "products", "orders", "order_items", "returns"]


def create_schema(engine):
    METADATA.drop_all(engine)
    METADATA.create_all(engine)


def load_csv(engine, table_name: str, csv_path, workspace_id: str = "demo") -> int:
    table = TABLES[table_name]
    types = COLUMN_TYPES[table_name]

    rows = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for raw_row in reader:
            row = {"workspace_id": workspace_id}
            for col, caster in types.items():
                if col not in raw_row:
                    raise ValueError(f"{table_name}: missing column '{col}' in {csv_path}")
                row[col] = caster(raw_row[col])
            rows.append(row)

    if rows:
        with engine.begin() as conn:
            conn.execute(insert(table), rows)

    return len(rows)
