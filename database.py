import sqlite3


def salvar_lance(quadra, data, hora, drive_id):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO lances (quadra, data, hora, drive_id)
        VALUES (?, ?, ?, ?)
    """, (quadra, data, hora, drive_id))

    conn.commit()
    conn.close()
