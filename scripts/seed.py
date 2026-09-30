import calendar
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "store.db"

SEED = 42
ANCHOR_DATE = date(2026, 9, 30)  # "today" for this dataset; keep in sync with the system prompt

CITIES = [
    ("Mumbai", 0.20),
    ("Delhi", 0.18),
    ("Bangalore", 0.15),
    ("Hyderabad", 0.10),
    ("Chennai", 0.10),
    ("Pune", 0.12),
    ("Kolkata", 0.08),
    ("Ahmedabad", 0.07),
]

PRODUCTS = [
    ("Wireless Earbuds Pro", "Audio", 2499),
    ("Bluetooth Speaker Mini", "Audio", 1799),
    ("Smart Watch X2", "Wearables", 3499),
    ("Fitness Band Lite", "Wearables", 1299),
    ("USB-C Fast Charger 65W", "Electronics", 999),
    ("Power Bank 20000mAh", "Electronics", 1499),
    ("Wireless Mouse", "Accessories", 599),
    ("Mechanical Keyboard Compact", "Accessories", 2999),
    ("Laptop Stand Aluminium", "Accessories", 899),
    ("Phone Case Clear", "Accessories", 299),
    ("Tempered Glass Screen Protector", "Accessories", 199),
    ("LED Desk Lamp", "Home", 1299),
    ("Smart Plug", "Home", 799),
    ("Portable Blender", "Home", 1599),
    ("Electric Kettle", "Home", 1199),
    ("Air Purifier Mini", "Home", 3999),
    ("Noise Cancelling Headphones", "Audio", 4999),
    ("Neckband Earphones", "Audio", 899),
    ("Smart Ring", "Wearables", 4499),
    ("Action Camera", "Electronics", 3999),
    ("Ring Light 10 inch", "Electronics", 1099),
    ("Tripod Stand", "Accessories", 699),
    ("Car Phone Mount", "Accessories", 399),
    ("Wireless Charger Pad", "Electronics", 899),
    ("Bluetooth Adapter", "Electronics", 499),
    ("Yoga Mat Premium", "Home", 999),
    ("Resistance Bands Set", "Home", 599),
    ("Water Bottle Insulated", "Home", 499),
    ("Backpack Urban", "Accessories", 1999),
    ("Travel Organizer Set", "Accessories", 799),
]

RETURN_REASONS = ["defective", "wrong item", "no longer needed", "changed mind", "damaged in transit"]

PLANTED_PRODUCT = "Wireless Earbuds Pro"
PLANTED_CITY = "Mumbai"
PLANTED_DROP_MONTH = (2026, 8)          # sales volume drop for the planted product
PLANTED_SPIKE_START = date(2026, 9, 1)  # return spike window (planted product + city)
PLANTED_SPIKE_END = date(2026, 9, 29)   # kept in the normal-volume month so it has a real sample size

BASE_ORDERS_PER_MONTH = 1500
FESTIVE_MONTHS = {(2025, 10), (2025, 11)}
FESTIVE_MULTIPLIER = 1.8

BASELINE_RETURN_RATE = 0.05
PLANTED_RETURN_RATE = 0.40


def month_range(start_year, start_month, count):
    months = []
    y, m = start_year, start_month
    for _ in range(count):
        months.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


MONTHS = month_range(2025, 10, 12)  # Oct 2025 .. Sep 2026


def random_date_in_month(rng, year, month):
    days = calendar.monthrange(year, month)[1]
    day = rng.randint(1, days)
    return date(year, month, day)


def build_schema(conn):
    conn.executescript(
        """
        DROP TABLE IF EXISTS returns;
        DROP TABLE IF EXISTS order_items;
        DROP TABLE IF EXISTS orders;
        DROP TABLE IF EXISTS products;
        DROP TABLE IF EXISTS customers;

        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            city TEXT NOT NULL,
            signup_date TEXT NOT NULL
        );

        CREATE TABLE products (
            product_id INTEGER PRIMARY KEY,
            sku TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL
        );

        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
            order_date TEXT NOT NULL,
            city TEXT NOT NULL
        );

        CREATE TABLE order_items (
            order_item_id INTEGER PRIMARY KEY,
            order_id INTEGER NOT NULL REFERENCES orders(order_id),
            product_id INTEGER NOT NULL REFERENCES products(product_id),
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL
        );

        CREATE TABLE returns (
            return_id INTEGER PRIMARY KEY,
            order_item_id INTEGER NOT NULL REFERENCES order_items(order_item_id),
            return_date TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            reason TEXT NOT NULL
        );

        CREATE INDEX idx_orders_date ON orders(order_date);
        CREATE INDEX idx_order_items_order ON order_items(order_id);
        CREATE INDEX idx_order_items_product ON order_items(product_id);
        CREATE INDEX idx_returns_item ON returns(order_item_id);
        """
    )


def seed_customers(conn, rng, count=1600):
    cities = [c for c, _ in CITIES]
    weights = [w for _, w in CITIES]
    rows = []
    for i in range(1, count + 1):
        city = rng.choices(cities, weights=weights)[0]
        signup = ANCHOR_DATE - timedelta(days=rng.randint(30, 730))
        rows.append((i, f"Customer {i}", city, signup.isoformat()))
    conn.executemany(
        "INSERT INTO customers (customer_id, name, city, signup_date) VALUES (?, ?, ?, ?)",
        rows,
    )
    return [r[0] for r in rows], {r[0]: r[2] for r in rows}


def seed_products(conn, rng):
    rows = []
    for i, (name, category, price) in enumerate(PRODUCTS, start=1):
        sku = f"SKU-{i:04d}"
        rows.append((i, sku, name, category, float(price)))
    conn.executemany(
        "INSERT INTO products (product_id, sku, name, category, price) VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    base_weights = [rng.uniform(0.5, 2.0) for _ in PRODUCTS]
    return rows, base_weights


def seed_orders_and_items(conn, rng, customer_ids, customer_city, product_rows, base_weights):
    planted_idx = next(i for i, p in enumerate(product_rows) if p[2] == PLANTED_PRODUCT)

    order_id = 1
    item_id = 1
    return_id = 1
    order_rows = []
    item_rows = []
    return_rows = []

    for (year, month) in MONTHS:
        multiplier = FESTIVE_MULTIPLIER if (year, month) in FESTIVE_MONTHS else 1.0
        n_orders = int(BASE_ORDERS_PER_MONTH * multiplier) + rng.randint(-100, 100)

        weights = list(base_weights)
        if (year, month) == PLANTED_DROP_MONTH:
            weights[planted_idx] *= 0.2

        for _ in range(n_orders):
            customer_id = rng.choice(customer_ids)
            city = customer_city[customer_id]
            order_date = random_date_in_month(rng, year, month)

            order_rows.append((order_id, customer_id, order_date.isoformat(), city))

            n_items = rng.choices([1, 2, 3], weights=[60, 30, 10])[0]
            for _ in range(n_items):
                product_idx = rng.choices(range(len(product_rows)), weights=weights)[0]
                product = product_rows[product_idx]
                quantity = rng.choices([1, 2, 3], weights=[70, 20, 10])[0]
                unit_price = product[4]

                item_rows.append((item_id, order_id, product[0], quantity, unit_price))

                is_planted = (
                    product[2] == PLANTED_PRODUCT
                    and city == PLANTED_CITY
                    and PLANTED_SPIKE_START <= order_date <= PLANTED_SPIKE_END
                )
                return_prob = PLANTED_RETURN_RATE if is_planted else BASELINE_RETURN_RATE

                if rng.random() < return_prob:
                    delay = rng.randint(2, 10)
                    return_date = min(order_date + timedelta(days=delay), ANCHOR_DATE)
                    if is_planted:
                        reason = rng.choices(["defective", "wrong item"], weights=[70, 30])[0]
                    else:
                        reason = rng.choice(RETURN_REASONS)
                    return_rows.append((return_id, item_id, return_date.isoformat(), quantity, reason))
                    return_id += 1

                item_id += 1

            order_id += 1

    conn.executemany(
        "INSERT INTO orders (order_id, customer_id, order_date, city) VALUES (?, ?, ?, ?)",
        order_rows,
    )
    conn.executemany(
        "INSERT INTO order_items (order_item_id, order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?, ?)",
        item_rows,
    )
    conn.executemany(
        "INSERT INTO returns (return_id, order_item_id, return_date, quantity, reason) VALUES (?, ?, ?, ?, ?)",
        return_rows,
    )

    return len(order_rows), len(item_rows), len(return_rows)


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    rng = random.Random(SEED)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    build_schema(conn)

    customer_ids, customer_city = seed_customers(conn, rng)
    product_rows, base_weights = seed_products(conn, rng)
    n_orders, n_items, n_returns = seed_orders_and_items(
        conn, rng, customer_ids, customer_city, product_rows, base_weights
    )

    conn.commit()
    conn.close()

    print("seed complete:", DB_PATH)
    print("row counts:")
    print(f"  customers:   {len(customer_ids)}")
    print(f"  products:    {len(product_rows)}")
    print(f"  orders:      {n_orders}")
    print(f"  order_items: {n_items}")
    print(f"  returns:     {n_returns}")
    print()
    print("planted stories:")
    print(f"  return spike: '{PLANTED_PRODUCT}' in {PLANTED_CITY}, elevated returns")
    print(f"                for orders placed {PLANTED_SPIKE_START} to {PLANTED_SPIKE_END}")
    print(f"  sales drop:   '{PLANTED_PRODUCT}' order volume cut to ~20% of normal")
    print(f"                during {PLANTED_DROP_MONTH[0]}-{PLANTED_DROP_MONTH[1]:02d}")
    festive_list = ", ".join(f"{y}-{m:02d}" for y, m in sorted(FESTIVE_MONTHS))
    print(f"  festive bump: overall order volume up {int((FESTIVE_MULTIPLIER - 1) * 100)}% in {festive_list}")
    print(f"  anchor date (treat as 'today' for relative date terms): {ANCHOR_DATE}")


if __name__ == "__main__":
    main()
