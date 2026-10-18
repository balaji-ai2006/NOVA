import sqlite3

conn = sqlite3.connect('data/databases/nova_memory.db')
cursor = conn.cursor()
cursor.execute("DELETE FROM memories WHERE content LIKE '%Again%'")
cursor.execute("INSERT OR REPLACE INTO memories (id, content, created_at, updated_at) VALUES (1, 'User name is Balaji.', datetime('now'), datetime('now'))")

conn.commit()
print("Total memories now:", cursor.execute("SELECT COUNT(*) FROM memories").fetchone()[0])
for row in cursor.execute("SELECT id, content FROM memories").fetchall():
    print(row)
conn.close()
