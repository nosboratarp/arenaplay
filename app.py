import os
from dotenv import load_dotenv

load_dotenv()  # carrega variáveis do .env
import mercadopago
from flask import Flask, render_template, request, redirect, session
from flask_bcrypt import Bcrypt
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
timestamp = datetime.now().strftime("%H-%M-%S")

# ================================
# CONFIGURAÇÃO APP
# ================================

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

# ================================
# CONFIGURAÇÃO BANCO
# ================================

database_url = os.environ.get("DATABASE_URL")

if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace(
            "postgres://", "postgresql+psycopg://", 1
        )
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace(
            "postgresql://", "postgresql+psycopg://", 1
        )

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    print("🟢 Usando PostgreSQL (produção)")
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
    print("🔵 Usando SQLite local")

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# ================================
# MERCADO PAGO (SEGURO)
# ================================

MP_TOKEN = os.environ.get("MP_ACCESS_TOKEN")

if MP_TOKEN:
    sdk = mercadopago.SDK(MP_TOKEN)
    print("🟢 Mercado Pago ativo")
else:
    sdk = None
    print("🟡 Mercado Pago não configurado neste ambiente")

# ================================
# MODELOS
# ================================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)


class Lance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quadra = db.Column(db.String(100))
    data = db.Column(db.String(20))
    hora = db.Column(db.String(20))
    drive_id = db.Column(db.String(200))


class Pagamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    drive_id = db.Column(db.String(200))
    valor = db.Column(db.Float)
    status = db.Column(db.String(20))
    criado_em = db.Column(db.DateTime, server_default=db.func.now())


with app.app_context():
    db.create_all()

# ================================
# LOGIN
# ================================

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()

        if user and bcrypt.check_password_hash(user.password, password):
            session["user"] = user.email
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
# QUADRA
# ================================

@app.route("/quadra/<nome>")
def quadra(nome):
    if "user" not in session:
        return redirect("/")

    datas = (
        db.session.query(Lance.data)
        .filter_by(quadra=nome)
        .distinct()
        .order_by(Lance.data.desc())
        .all()
    )

    return render_template("quadra.html", quadra=nome, datas=datas)


# ================================
# LISTAR LANCES
# ================================

@app.route("/data/<quadra>/<data>")
def data_view(quadra, data):
    if "user" not in session:
        return redirect("/")

    lances = (
        db.session.query(
            Lance.hora,
            Lance.drive_id,
            db.func.coalesce(
                db.session.query(Pagamento.status)
                .filter(Pagamento.drive_id == Lance.drive_id)
                .order_by(Pagamento.criado_em.desc())
                .limit(1)
                .scalar_subquery(),
                "PENDENTE",
            ),
        )
        .filter(Lance.quadra == quadra, Lance.data == data)
        .order_by(Lance.hora.desc())
        .all()
    )

    return render_template(
        "lances.html",
        quadra=quadra,
        data=data,
        lances=lances,
    )


# ================================
# COMPRAR (PIX)
# ================================

@app.route("/comprar/<drive_id>", methods=["POST"])
def comprar(drive_id):

    if not sdk:
        return "Pagamento indisponível neste ambiente."

    payment_data = {
        "transaction_amount": 2.59,
        "description": "Replay ArenaPlay",
        "payment_method_id": "pix",
        "payer": {"email": session.get("user")},
        "external_reference": drive_id,
        "notification_url": "https://arenaplayfut.com.br/webhook",
    }

    payment_response = sdk.payment().create(payment_data)
    payment = payment_response["response"]

    novo_pagamento = Pagamento(
        drive_id=drive_id,
        valor=2.59,
        status="PENDENTE",
    )

    db.session.add(novo_pagamento)
    db.session.commit()

    qr_code = payment["point_of_interaction"]["transaction_data"]["qr_code"]
    qr_code_base64 = payment["point_of_interaction"]["transaction_data"]["qr_code_base64"]

    return render_template(
        "pagamento.html",
        qr_code=qr_code,
        qr_code_base64=qr_code_base64,
        drive_id=drive_id,
    )


# ================================
# WEBHOOK
# ================================

@app.route("/webhook", methods=["POST"])
def webhook():

    if not sdk:
        return "SDK não configurado", 400

    data = request.json

    if "data" in data and "id" in data["data"]:
        payment_id = data["data"]["id"]

        payment_info = sdk.payment().get(payment_id)["response"]

        drive_id = payment_info["external_reference"]
        status = payment_info["status"]

        if status == "approved":
            pagamento = (
                Pagamento.query
                .filter_by(drive_id=drive_id)
                .order_by(Pagamento.criado_em.desc())
                .first()
            )

            if pagamento:
                pagamento.status = "PAGO"
                db.session.commit()

    return "OK", 200


# ================================
# DOWNLOAD PROTEGIDO
# ================================

@app.route("/download/<drive_id>")
def download(drive_id):

    pagamento = (
        Pagamento.query
        .filter_by(drive_id=drive_id, status="PAGO")
        .order_by(Pagamento.criado_em.desc())
        .first()
    )

    if not pagamento:
        return "Pagamento não aprovado."

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

        if User.query.filter_by(email=email).first():
            return "Usuário já existe"

        novo_usuario = User(email=email, password=password)
        db.session.add(novo_usuario)
        db.session.commit()

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
    app.run()