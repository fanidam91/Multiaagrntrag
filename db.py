import sqlite3
import json
import random
import csv
from datetime import datetime, timedelta
from faker import Faker

fake = Faker()

DB_FILE = "orders.db"
CSV_FILE = "orders.csv"

# Product lists by category
CATEGORIES = {
    "Electronics": [
        {"name": "Wireless Headphones", "price": 89.99},
        {"name": "Mechanical Keyboard", "price": 129.99},
        {"name": "Smart Watch", "price": 199.99},
        {"name": "Bluetooth Speaker", "price": 49.99},
        {"name": "USB-C Hub Multiport", "price": 34.99},
        {"name": "Ergonomic Wireless Mouse", "price": 59.99},
    ],
    "Apparel": [
        {"name": "Organic Cotton Hoodie", "price": 65.00},
        {"name": "Running Shoes", "price": 110.00},
        {"name": "Denim Jacket", "price": 85.00},
        {"name": "Athletic Sweatpants", "price": 45.00},
        {"name": "Pack of 3 Cotton Tees", "price": 29.99},
    ],
    "Home & Kitchen": [
        {"name": "Digital Air Fryer", "price": 99.99},
        {"name": "Stainless Steel Water Bottle", "price": 24.99},
        {"name": "Smart Coffee Maker", "price": 149.99},
        {"name": "Memory Foam Pillow", "price": 39.99},
        {"name": "Handheld Milk Frother", "price": 15.99},
        {"name": "Chef Knife 8-inch", "price": 49.99},
    ],
    "Books": [
        {"name": "Data Engineering Handbook", "price": 45.99},
        {"name": "Sci-Fi Novel: Horizon's Edge", "price": 14.99},
        {"name": "The Art of Productivity", "price": 19.99},
        {"name": "Healthy Cooking Made Easy", "price": 22.50},
        {"name": "Mystery Thriller: Dark Waters", "price": 16.99},
    ],
    "Fitness": [
        {"name": "Non-Slip Yoga Mat", "price": 29.99},
        {"name": "Adjustable Dumbbells Set", "price": 249.99},
        {"name": "Resistance Bands Pack", "price": 19.99},
        {"name": "Foam Roller", "price": 22.99},
        {"name": "Sports Gym Duffle Bag", "price": 35.00},
    ]
}

STATUSES = ["Pending", "Processing", "Shipped", "Delivered", "Cancelled", "Refunded"]
CARRIERS = ["FedEx", "UPS", "DHL", "USPS"]

def generate_data():
    orders_data = []
    base_date = datetime.now() - timedelta(days=45)
    
    print("Generating 500 mock orders...")
    for i in range(1, 501):
        order_id = f"ORD-{1000 + i}"
        customer_name = fake.name()
        email = f"{customer_name.lower().replace(' ', '.')}@{fake.free_email_domain()}"
        phone = fake.phone_number()
        
        # Order date: random spreading over last 45 days
        days_offset = random.random() * 45
        order_time = base_date + timedelta(days=days_offset)
        order_date_str = order_time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Status logic weighted towards delivered
        status = random.choices(
            STATUSES, 
            weights=[8, 15, 20, 47, 6, 4], 
            k=1
        )[0]
        
        # Items logic
        num_items = random.randint(1, 3)
        items_list = []
        total_amount = 0.0
        
        for _ in range(num_items):
            cat = random.choice(list(CATEGORIES.keys()))
            prod = random.choice(CATEGORIES[cat])
            
            existing = next((x for x in items_list if x["name"] == prod["name"]), None)
            qty = random.randint(1, 2)
            if existing:
                existing["quantity"] += qty
            else:
                items_list.append({
                    "category": cat,
                    "name": prod["name"],
                    "price": prod["price"],
                    "quantity": qty
                })
            total_amount += prod["price"] * qty

        total_amount = round(total_amount, 2)
        
        # Address
        shipping_address = fake.street_address()
        city = fake.city()
        zip_code = fake.zipcode()
        country = "United States"
        
        # Logistics
        carrier = ""
        tracking_number = ""
        estimated_delivery = ""
        
        if status in ["Shipped", "Delivered", "Refunded"]:
            carrier = random.choice(CARRIERS)
            tracking_number = f"1Z{random.randint(100000000000, 999999999999)}"
            
            ship_days = random.randint(1, 3)
            ship_time = order_time + timedelta(days=ship_days)
            est_del_time = ship_time + timedelta(days=random.randint(2, 5))
            estimated_delivery = est_del_time.strftime("%Y-%m-%d")
            
        elif status == "Processing":
            est_del_time = order_time + timedelta(days=random.randint(4, 7))
            estimated_delivery = est_del_time.strftime("%Y-%m-%d")
            
        elif status == "Pending":
            est_del_time = order_time + timedelta(days=random.randint(5, 8))
            estimated_delivery = est_del_time.strftime("%Y-%m-%d")

        # History notes
        notes = []
        notes.append(f"[{order_time.strftime('%Y-%m-%d %H:%M:%S')}] Order created. Total: ${total_amount}")
        
        if status != "Pending" and status != "Cancelled":
            processing_time = order_time + timedelta(hours=random.randint(2, 24))
            notes.append(f"[{processing_time.strftime('%Y-%m-%d %H:%M:%S')}] Payment verified. Order moved to Processing.")
            
            if status in ["Shipped", "Delivered", "Refunded"]:
                ship_time = processing_time + timedelta(days=random.randint(1, 2))
                notes.append(f"[{ship_time.strftime('%Y-%m-%d %H:%M:%S')}] Dispatched via {carrier}. Tracking: {tracking_number}")
                
                if status in ["Delivered", "Refunded"]:
                    delivery_time = ship_time + timedelta(days=random.randint(2, 4))
                    notes.append(f"[{delivery_time.strftime('%Y-%m-%d %H:%M:%S')}] Delivered to front door/mailbox.")
                    
                    if status == "Refunded":
                        refund_time = delivery_time + timedelta(days=random.randint(1, 5))
                        notes.append(f"[{refund_time.strftime('%Y-%m-%d %H:%M:%S')}] Refund processed: Customer reported defective item.")
                        
        elif status == "Cancelled":
            cancel_time = order_time + timedelta(hours=random.randint(1, 12))
            notes.append(f"[{cancel_time.strftime('%Y-%m-%d %H:%M:%S')}] Order cancelled by customer before dispatch.")

        if random.random() < 0.15:
            support_time = order_time + timedelta(days=random.randint(1, 10))
            support_time_str = support_time.strftime('%Y-%m-%d %H:%M:%S')
            issues = [
                f"[{support_time_str}] Support Chat: Customer inquired about delivery date. Representative updated customer.",
                f"[{support_time_str}] Support Chat: Customer requested change of shipping address. Request rejected as order already processing.",
                f"[{support_time_str}] Support Chat: Customer complained about product instructions. Emailed manual pdf.",
                f"[{support_time_str}] Support Chat: Customer asked if they can add another item. Explained they must place a new order."
            ]
            notes.append(random.choice(issues))

        support_notes_str = "\n".join(notes)
        
        orders_data.append({
            "order_id": order_id,
            "customer_name": customer_name,
            "email": email,
            "phone": phone,
            "order_date": order_date_str,
            "status": status,
            "total_amount": total_amount,
            "shipping_address": shipping_address,
            "city": city,
            "zip_code": zip_code,
            "country": country,
            "carrier": carrier if carrier else "",
            "tracking_number": tracking_number if tracking_number else "",
            "estimated_delivery": estimated_delivery if estimated_delivery else "",
            "items": json.dumps(items_list),
            "support_notes": support_notes_str
        })
        
    # Write to CSV
    print(f"Writing to {CSV_FILE}...")
    headers = [
        "order_id", "customer_name", "email", "phone", "order_date", "status", "total_amount",
        "shipping_address", "city", "zip_code", "country", "carrier", "tracking_number",
        "estimated_delivery", "items", "support_notes"
    ]
    with open(CSV_FILE, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in orders_data:
            writer.writerow(row)
            
    # Write to SQLite
    print(f"Syncing to {DB_FILE}...")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS orders")
    cursor.execute("""
    CREATE TABLE orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT UNIQUE NOT NULL,
        customer_name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT NOT NULL,
        order_date TEXT NOT NULL,
        status TEXT NOT NULL,
        total_amount REAL NOT NULL,
        shipping_address TEXT NOT NULL,
        city TEXT NOT NULL,
        zip_code TEXT NOT NULL,
        country TEXT NOT NULL,
        carrier TEXT,
        tracking_number TEXT,
        estimated_delivery TEXT,
        items TEXT NOT NULL,
        support_notes TEXT
    )
    """)
    cursor.execute("CREATE INDEX idx_order_id ON orders(order_id)")
    cursor.execute("CREATE INDEX idx_customer_name ON orders(customer_name)")
    cursor.execute("CREATE INDEX idx_status ON orders(status)")
    cursor.execute("CREATE INDEX idx_order_date ON orders(order_date)")
    
    insert_data = [
        (
            r["order_id"], r["customer_name"], r["email"], r["phone"], r["order_date"], r["status"],
            r["total_amount"], r["shipping_address"], r["city"], r["zip_code"], r["country"],
            r["carrier"], r["tracking_number"], r["estimated_delivery"], r["items"], r["support_notes"]
        ) for r in orders_data
    ]
    
    cursor.executemany("""
    INSERT INTO orders (
        order_id, customer_name, email, phone, order_date, status, total_amount,
        shipping_address, city, zip_code, country, carrier, tracking_number,
        estimated_delivery, items, support_notes
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, insert_data)
    
    conn.commit()
    
    cursor.execute("SELECT COUNT(*) FROM orders")
    count = cursor.fetchone()[0]
    conn.close()
    
    print(f"Generated {count} orders. CSV and SQLite database updated successfully.")

if __name__ == "__main__":
    generate_data()
