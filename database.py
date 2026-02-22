import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL não configurada")

engine = create_engine(DATABASE_URL)

def salvar_lance(quadra, data, hora, drive_id):
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO lances (quadra, data, hora, drive_id)
                VALUES (:quadra, :data, :hora, :drive_id)
            """),
            {
                "quadra": quadra,
                "data": data,
                "hora": hora,
                "drive_id": drive_id
            }
        )