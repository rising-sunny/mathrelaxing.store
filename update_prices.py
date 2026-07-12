import sqlite3

db = "/var/www/mathrelaxing.store/mathrelaxing.db"
conn = sqlite3.connect(db)
cursor = conn.cursor()

cursor.execute("UPDATE products SET price_usd = 24.99 WHERE slug LIKE '%coloring-book%';")
conn.commit()

cursor.execute("SELECT slug, price_usd FROM products WHERE slug LIKE '%coloring-book%';")
for row in cursor.fetchall():
    print(row)
conn.close()
