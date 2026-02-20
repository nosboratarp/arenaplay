import mercadopago
import uuid

from flask import Flask, render_template, request, redirect, session
from flask_bcrypt import Bcrypt
import sqlite3

app = Flask(__name__)
app.secret_key = "arenaplay_secret_key"
ACCESS_TOKEN = "TEST-8249896473432277-021919-f12e8ceeb7a3f7def915aabadde590ee-277949068"
sdk = mercadopago.SDK(ACCESS_TOKEN)

bcrypt = Bcrypt(app)

# ================================
# CRIAR BANCO
# ================================
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            password TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quadra TEXT,
            data TEXT,
            hora TEXT,
            drive_id TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pagamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            drive_id TEXT,
            valor REAL,
            status TEXT,
            criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

init_db()

# ================================
# LOGIN
# ================================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email=?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and bcrypt.check_password_hash(user[2], password):
            session["user"] = user[1]
            return redirect("/dashboard")

        return "Login inválido"

    return render_template("login.html")

# ================================
# DASHBOARD
# ================================
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")
    return render_template("dashboard.html", user=session["user"])

# ================================
# QUADRA → LISTAR DATAS
# ================================
@app.route("/quadra/<nome>")
def quadra(nome):
    if "user" not in session:
        return redirect("/")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT data
        FROM lances
        WHERE quadra=?
        ORDER BY data DESC
    """, (nome,))

    datas = cursor.fetchall()
    conn.close()

    return render_template("quadra.html", quadra=nome, datas=datas)

# ================================
# DATA → LISTAR LANCES
# ================================
@app.route("/data/<quadra>/<data>")
def data_view(quadra, data):
    if "user" not in session:
        return redirect("/")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT l.hora, l.drive_id,
               COALESCE(
                   (SELECT status FROM pagamentos p
                    WHERE p.drive_id = l.drive_id
                    ORDER BY p.criado_em DESC
                    LIMIT 1),
                   'PENDENTE'
               ) as status_pagamento
        FROM lances l
        WHERE l.quadra=? AND l.data=?
        ORDER BY l.hora DESC
    """, (quadra, data))

    lances = cursor.fetchall()
    conn.close()

    return render_template(
        "lances.html",
        quadra=quadra,
        data=data,
        lances=lances
    )

# ================================
# COMPRAR REPLAY
# ================================
@app.route("/comprar/<drive_id>", methods=["POST"])
def comprar(drive_id):

    payment_data = {
        "transaction_amount": 2.59,
        "description": "Replay ArenaPlay",
        "payment_method_id": "pix",
        "payer": {
            "email": "teste@arenaplay.com"
        },
        "external_reference": drive_id
    }

    payment_response = sdk.payment().create(payment_data)
    payment = payment_response["response"]

    # Salvar como PENDENTE
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO pagamentos (drive_id, valor, status)
        VALUES (?, ?, ?)
    """, (drive_id, 2.59, "PENDENTE"))

    conn.commit()
    conn.close()

    qr_code = payment["point_of_interaction"]["transaction_data"]["qr_code"]
    qr_code_base64 = payment["point_of_interaction"]["transaction_data"]["qr_code_base64"]

    return render_template(
        "pagamento.html",
        qr_code=qr_code,
        qr_code_base64=qr_code_base64,
        drive_id=drive_id
    )
# ================================
# SIMULAR PAGAMENTO
# ================================
@app.route("/pago/<drive_id>")
def pago(drive_id):

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE pagamentos
        SET status = 'PAGO'
        WHERE drive_id = ?
    """, (drive_id,))

    conn.commit()
    conn.close()

    return redirect(f"/download/{drive_id}")

# ================================
# DOWNLOAD PROTEGIDO
# ================================
@app.route("/download/<drive_id>")
def download(drive_id):

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM pagamentos
        WHERE drive_id=? AND status='PAGO'
        ORDER BY criado_em DESC
        LIMIT 1
    """, (drive_id,))

    pagamento = cursor.fetchone()
    conn.close()

    if not pagamento:
        return "Pagamento não encontrado ou não aprovado."

    link = f"https://drive.google.com/uc?export=download&id={drive_id}"
    return redirect(link)

# ================================
# CADASTRO
# ================================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        password = bcrypt.generate_password_hash(
            request.form["password"]
        ).decode("utf-8")

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO users (email, password) VALUES (?, ?)",
                (email, password)
            )
            conn.commit()
        except:
            return "Usuário já existe"

        conn.close()
        return redirect("/")

    return render_template("register.html")

# ================================
# LOGOUT
# ================================
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)