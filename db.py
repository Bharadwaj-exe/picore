import mysql.connector

def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",  
        database="picore"
    )

def save_query(expression, results):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO queries (expression) VALUES (%s)",
        (expression,)
    )
    query_id = cur.lastrowid

    for title, content in results:
        cur.execute(
            "INSERT INTO results (query_id, title, content) VALUES (%s, %s, %s)",
            (query_id, title, content)
        )

    conn.commit()
    cur.close()
    conn.close()

def fetch_history(limit=50):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT q.id, q.expression, q.created_at, r.title, r.content
        FROM queries q
        JOIN results r ON q.id = r.query_id
        ORDER BY q.created_at DESC
        LIMIT %s
    """, (limit,))

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows
def clear_history():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM results")
    cur.execute("DELETE FROM queries")

    cur.execute("ALTER TABLE results AUTO_INCREMENT = 1")
    cur.execute("ALTER TABLE queries AUTO_INCREMENT = 1")

    conn.commit()
    cur.close()
    conn.close()

    return rows
