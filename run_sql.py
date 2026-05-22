import os
import psycopg2

database_url = os.environ.get("DATABASE_URL")
if not database_url:
    print("Error: DATABASE_URL not set")
    exit(1)

with open("seed_batch1_complete.sql", "r") as f:
    sql = f.read()

conn = psycopg2.connect(database_url)
conn.autocommit = True
cur = conn.cursor()

try:
    cur.execute(sql)
    print("SQL executed successfully.")
except Exception as e:
    print(f"Error executing SQL: {e}")
finally:
    cur.close()
    conn.close()
