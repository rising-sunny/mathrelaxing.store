import os
import sqlite3

# 1. Update Database
db = "/var/www/mathrelaxing.store/mathrelaxing.db"
conn = sqlite3.connect(db)
cursor = conn.cursor()
cursor.execute("UPDATE products SET price_usd = 14.99 WHERE slug LIKE '%coloring-book%';")
conn.commit()
conn.close()
print("Database prices updated to 14.99")

# 2. Update HTML Templates
TEMPLATES_DIR = "/var/www/mathrelaxing.store/templates"
files = [f for f in os.listdir(TEMPLATES_DIR) if f.startswith("book")]

for f in files:
    path = os.path.join(TEMPLATES_DIR, f)
    with open(path, "r", encoding="utf-8") as file:
        content = file.read()
    
    if "24.99" in content:
        content = content.replace("24.99", "14.99")
        with open(path, "w", encoding="utf-8") as file:
            file.write(content)
        print(f"Updated {f}")
