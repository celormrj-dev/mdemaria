"""
╔══════════════════════════════════════════════════╗
║           M DE MARIA — by Claude             ║
║  M de Maria — Sua loja online        ║
║  + Pagamento · Filtro de Preço · Admin · Frete   ║
╚══════════════════════════════════════════════════╝

INSTALAÇÃO (1 vez):
  pip install flask werkzeug

RODAR:
  python mercado_app.py

Acesse: http://localhost:5000

USUÁRIO ADMIN:  admin@mercado.com / admin123
"""

from flask import (Flask, render_template_string, request, redirect,
                   url_for, session, flash, jsonify)
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, random, string
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = "mdemaria-secret-v2-2024"
DB = "mercado.db"

# ══════════════════════════════════════════
#  DATABASE
# ══════════════════════════════════════════
def get_db():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            is_seller INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0,
            cpf TEXT,
            phone TEXT,
            address TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            original_price REAL,
            stock INTEGER DEFAULT 1,
            category TEXT DEFAULT 'Geral',
            image_url TEXT,
            condition TEXT DEFAULT 'Novo',
            weight_kg REAL DEFAULT 0.5,
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (seller_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            buyer_id INTEGER NOT NULL,
            subtotal REAL NOT NULL,
            freight REAL DEFAULT 0,
            total REAL NOT NULL,
            status TEXT DEFAULT 'Aguardando pagamento',
            payment_method TEXT,
            payment_code TEXT,
            shipping_address TEXT,
            tracking_code TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (buyer_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            qty INTEGER NOT NULL,
            price REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        );
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    # Migrate: add missing columns if upgrading from v1
    for col, definition in [
        ("is_admin","INTEGER DEFAULT 0"), ("cpf","TEXT"), ("phone","TEXT"),
        ("address","TEXT"), ("weight_kg","REAL DEFAULT 0.5"),
        ("active","INTEGER DEFAULT 1"), ("subtotal","REAL DEFAULT 0"),
        ("freight","REAL DEFAULT 0"), ("payment_method","TEXT"),
        ("payment_code","TEXT"), ("shipping_address","TEXT"), ("tracking_code","TEXT"),
    ]:
        try:
            table = "orders" if col in ("subtotal","freight","payment_method","payment_code","shipping_address","tracking_code") else \
                    "products" if col in ("weight_kg","active") else "users"
            db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")
            db.commit()
        except: pass

    existing = db.execute("SELECT id FROM users WHERE email='admin@mercado.com'").fetchone()
    if not existing:
        db.execute("INSERT INTO users (name,email,password,is_seller,is_admin) VALUES (?,?,?,?,?)",
                   ("Admin","admin@mercado.com", generate_password_hash("admin123"), 1, 1))
        db.commit()
        uid = db.execute("SELECT id FROM users WHERE email='admin@mercado.com'").fetchone()["id"]
        products = [
            (uid,"iPhone 15 Pro Max 256GB","Smartphone Apple com câmera de 48MP, chip A17 Pro e titânio.",
             7999.00,9499.00,5,"Eletrônicos","https://images.unsplash.com/photo-1592899677977-9c10ca588bbd?w=400","Novo",0.4),
            (uid,"Nike Air Max 270","Tênis esportivo com amortecimento Air Max. Confortável para o dia a dia.",
             499.90,699.90,12,"Calçados","https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=400","Novo",0.8),
            (uid,'Smart TV Samsung 55" 4K QLED',"Imagem cristalina com tecnologia QLED, HDR10+ e Tizen OS.",
             2799.00,3499.00,3,"Eletrônicos","https://images.unsplash.com/photo-1593784991095-a205069470b6?w=400","Novo",12.0),
            (uid,"Notebook Dell Inspiron 15","Intel i7 12ª geração, 16GB RAM, SSD 512GB, tela Full HD.",
             4199.00,4999.00,8,"Informática","https://images.unsplash.com/photo-1496181133206-80ce9b88a853?w=400","Novo",2.1),
            (uid,"Fone Sony WH-1000XM5","Cancelamento de ruído líder da indústria, 30h de bateria.",
             1499.00,1999.00,15,"Eletrônicos","https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=400","Novo",0.25),
            (uid,"Mochila Samsonite 20L","Resistente à água, compartimento para notebook 15.6'.",
             289.90,399.90,20,"Bolsas","https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=400","Novo",0.9),
            (uid,"Câmera Canon EOS R50","Mirrorless 24.2MP, vídeo 4K, ideal para criadores de conteúdo.",
             5499.00,6299.00,4,"Fotografia","https://images.unsplash.com/photo-1502920917128-1aa500764cbd?w=400","Novo",0.45),
            (uid,"Kindle Paperwhite 16GB","Luz ajustável, resistente à água, bateria de semanas.",
             499.00,699.00,25,"Livros & E-readers","https://images.unsplash.com/photo-1481627834876-b7833e8f5570?w=400","Novo",0.21),
        ]
        db.executemany("""INSERT INTO products
            (seller_id,title,description,price,original_price,stock,category,image_url,condition,weight_kg)
            VALUES (?,?,?,?,?,?,?,?,?,?)""", products)
        db.commit()
    db.close()

# ══════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════
def login_required(f):
    @wraps(f)
    def d(*a,**k):
        if "user_id" not in session:
            flash("Faça login para continuar.", "warning")
            return redirect(url_for("login"))
        return f(*a,**k)
    return d

def seller_required(f):
    @wraps(f)
    def d(*a,**k):
        if "user_id" not in session: return redirect(url_for("login"))
        db = get_db()
        u = db.execute("SELECT is_seller FROM users WHERE id=?", (session["user_id"],)).fetchone()
        db.close()
        if not u or not u["is_seller"]:
            flash("Acesso restrito a vendedores.", "danger")
            return redirect(url_for("index"))
        return f(*a,**k)
    return d

def admin_required(f):
    @wraps(f)
    def d(*a,**k):
        if "user_id" not in session: return redirect(url_for("login"))
        db = get_db()
        u = db.execute("SELECT is_admin FROM users WHERE id=?", (session["user_id"],)).fetchone()
        db.close()
        if not u or not u["is_admin"]:
            flash("Acesso restrito a administradores.", "danger")
            return redirect(url_for("index"))
        return f(*a,**k)
    return d

def current_user():
    if "user_id" in session:
        db = get_db()
        u = db.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
        db.close()
        return dict(u) if u else None
    return None

def cart_count():
    return sum(session.get("cart", {}).values())

def fmt_brl(v):
    if v is None: return "R$ 0,00"
    return f"R$ {float(v):,.2f}".replace(",","X").replace(".",",").replace("X",".")

def gen_code(prefix="", length=8):
    return prefix + ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# Frete simulado por CEP (tabela baseada em regiões do Brasil)
FREIGHT_TABLE = {
    "SP": {"PAC": 15.90, "SEDEX": 29.90, "days_pac": 3, "days_sedex": 1},
    "RJ": {"PAC": 18.90, "SEDEX": 34.90, "days_pac": 4, "days_sedex": 2},
    "MG": {"PAC": 17.90, "SEDEX": 32.90, "days_pac": 4, "days_sedex": 2},
    "RS": {"PAC": 22.90, "SEDEX": 42.90, "days_pac": 7, "days_sedex": 3},
    "SC": {"PAC": 21.90, "SEDEX": 39.90, "days_pac": 6, "days_sedex": 3},
    "PR": {"PAC": 20.90, "SEDEX": 37.90, "days_pac": 5, "days_sedex": 2},
    "BA": {"PAC": 24.90, "SEDEX": 44.90, "days_pac": 8, "days_sedex": 4},
    "PE": {"PAC": 25.90, "SEDEX": 46.90, "days_pac": 9, "days_sedex": 4},
    "CE": {"PAC": 26.90, "SEDEX": 48.90, "days_pac": 10, "days_sedex": 5},
    "GO": {"PAC": 21.90, "SEDEX": 39.90, "days_pac": 6, "days_sedex": 3},
    "DF": {"PAC": 20.90, "SEDEX": 38.90, "days_pac": 5, "days_sedex": 3},
    "AM": {"PAC": 35.90, "SEDEX": 65.90, "days_pac": 14, "days_sedex": 7},
    "PA": {"PAC": 32.90, "SEDEX": 58.90, "days_pac": 12, "days_sedex": 6},
    "MT": {"PAC": 28.90, "SEDEX": 52.90, "days_pac": 10, "days_sedex": 5},
    "MS": {"PAC": 23.90, "SEDEX": 43.90, "days_pac": 7, "days_sedex": 4},
    "DEFAULT": {"PAC": 27.90, "SEDEX": 49.90, "days_pac": 10, "days_sedex": 5},
}

CEP_UF = {
    "01":"SP","02":"SP","03":"SP","04":"SP","05":"SP","06":"SP","07":"SP","08":"SP","09":"SP",
    "10":"SP","11":"SP","12":"SP","13":"SP","14":"SP","15":"SP","16":"SP","17":"SP","18":"SP","19":"SP",
    "20":"RJ","21":"RJ","22":"RJ","23":"RJ","24":"RJ","25":"RJ","26":"RJ","27":"RJ","28":"RJ",
    "29":"ES","30":"MG","31":"MG","32":"MG","33":"MG","34":"MG","35":"MG","36":"MG","37":"MG",
    "38":"MG","39":"MG","40":"BA","41":"BA","42":"BA","43":"BA","44":"BA","45":"BA","46":"BA",
    "47":"BA","48":"BA","49":"SE","50":"PE","51":"PE","52":"PE","53":"PE","54":"PE","55":"PE",
    "56":"PE","57":"AL","58":"PB","59":"RN","60":"CE","61":"CE","62":"CE","63":"CE",
    "64":"PI","65":"MA","66":"PA","67":"PA","68":"PA","69":"AM","70":"DF","71":"DF","72":"GO",
    "73":"GO","74":"GO","75":"GO","76":"GO","77":"TO","78":"MT","79":"MS","80":"PR","81":"PR",
    "82":"PR","83":"PR","84":"PR","85":"PR","86":"PR","87":"PR",
    "88":"SC","89":"SC","90":"RS","91":"RS","92":"RS","93":"RS","94":"RS","95":"RS","96":"RS",
    "97":"RS","98":"RS","99":"RS",
}

def calcular_frete(cep: str, peso_kg: float = 0.5, subtotal: float = 0):
    cep_clean = cep.replace("-","").replace(" ","").strip()
    if len(cep_clean) != 8 or not cep_clean.isdigit():
        return None
    prefix = cep_clean[:2]
    uf = CEP_UF.get(prefix, "DEFAULT")
    tabela = FREIGHT_TABLE.get(uf, FREIGHT_TABLE["DEFAULT"])
    # Ajuste por peso
    extra = max(0, (peso_kg - 0.5)) * 3.5
    pac = round(tabela["PAC"] + extra, 2)
    sedex = round(tabela["SEDEX"] + extra * 1.5, 2)
    # Frete grátis acima de R$299
    free = subtotal >= 299
    return {
        "uf": uf, "cep": f"{cep_clean[:5]}-{cep_clean[5:]}",
        "PAC": {"price": 0.0 if free else pac, "days": tabela["days_pac"], "free": free},
        "SEDEX": {"price": sedex, "days": tabela["days_sedex"], "free": False},
        "free_threshold": subtotal >= 299,
    }

app.jinja_env.globals.update(current_user=current_user, cart_count=cart_count, fmt_brl=fmt_brl)
CATEGORIES = ["Todos","Eletrônicos","Informática","Calçados","Bolsas","Fotografia","Livros & E-readers","Moda","Casa & Jardim","Esportes"]

# ══════════════════════════════════════════
#  BASE TEMPLATE
# ══════════════════════════════════════════
BASE = r"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ page_title if page_title else "M de Maria" }}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter',sans-serif;background:#f5f5f5;color:#333;min-height:100vh}
a{text-decoration:none;color:inherit}

.navbar{background:#fce4ec;padding:0 2rem;display:flex;align-items:center;gap:1rem;height:64px;box-shadow:0 2px 8px rgba(0,0,0,.08);position:sticky;top:0;z-index:100}
.nav-logo{font-size:1.4rem;font-weight:700;color:#333;white-space:nowrap}
.nav-logo span{color:#e91e8c}
.search-wrap{flex:1;max-width:640px;display:flex}
.search-wrap input{flex:1;padding:.6rem 1rem;border:2px solid #3483fa;border-right:none;border-radius:4px 0 0 4px;font-size:.9rem;outline:none}
.search-wrap button{background:#3483fa;color:#fff;border:none;padding:.6rem 1.2rem;border-radius:0 4px 4px 0;cursor:pointer;font-weight:600}
.search-wrap button:hover{background:#2968c8}
.nav-links{display:flex;align-items:center;gap:.5rem;margin-left:auto;flex-wrap:wrap}
.nav-btn{padding:.45rem .85rem;border-radius:6px;font-size:.8rem;font-weight:500;cursor:pointer;border:none;transition:.2s}
.btn-ghost{background:transparent;color:#333}.btn-ghost:hover{background:rgba(0,0,0,.07)}
.btn-primary{background:#3483fa;color:#fff}.btn-primary:hover{background:#2968c8}
.btn-yellow{background:#ffe600;color:#333}.btn-yellow:hover{background:#f0d800}
.btn-red{background:#e63946;color:#fff;border:none;cursor:pointer;padding:.4rem .8rem;border-radius:6px;font-size:.8rem}
.cart-btn{position:relative;background:#fff;border:1px solid #ddd;padding:.4rem .8rem;border-radius:6px;font-size:.82rem;cursor:pointer;display:flex;align-items:center;gap:.4rem}
.cart-btn:hover{border-color:#3483fa}
.cart-badge{background:#3483fa;color:#fff;font-size:.6rem;font-weight:700;width:18px;height:18px;border-radius:50%;display:flex;align-items:center;justify-content:center;position:absolute;top:-6px;right:-6px}
.admin-bar{background:#1a1a2e;color:#eee;font-size:.75rem;padding:.4rem 2rem;display:flex;gap:1.5rem;align-items:center}
.admin-bar a{color:#7fffb2;font-weight:500}

.flash-wrap{padding:.5rem 2rem}
.alert{padding:.75rem 1rem;border-radius:6px;margin-bottom:.5rem;font-size:.88rem}
.alert-success{background:#d4edda;color:#155724;border:1px solid #c3e6cb}
.alert-danger{background:#f8d7da;color:#721c24;border:1px solid #f5c6cb}
.alert-warning{background:#fff3cd;color:#856404;border:1px solid #ffeeba}
.alert-info{background:#d1ecf1;color:#0c5460;border:1px solid #bee5eb}

.container{max-width:1200px;margin:0 auto;padding:1.5rem 1rem}
.page-title{font-size:1.4rem;font-weight:700;margin-bottom:1.2rem}

/* GRID + CARDS */
.shop-layout{display:grid;grid-template-columns:220px 1fr;gap:1.5rem;align-items:start}
.filter-panel{background:#fff;border-radius:10px;padding:1.2rem;box-shadow:0 1px 4px rgba(0,0,0,.08);position:sticky;top:80px}
.filter-panel h3{font-size:.85rem;font-weight:700;margin-bottom:.8rem;text-transform:uppercase;letter-spacing:.05em;color:#555}
.filter-section{margin-bottom:1.2rem;padding-bottom:1.2rem;border-bottom:1px solid #f0f0f0}
.filter-section:last-child{border:none;margin:0;padding:0}
.price-inputs{display:flex;gap:.5rem;align-items:center;margin-top:.6rem}
.price-inputs input{flex:1;padding:.45rem .6rem;border:1px solid #ddd;border-radius:6px;font-size:.8rem;width:0}
.price-inputs span{font-size:.8rem;color:#999;flex-shrink:0}
.filter-radio{display:block;font-size:.82rem;padding:.3rem 0;cursor:pointer;color:#555}
.filter-radio:hover{color:#3483fa}
.filter-radio input{margin-right:.4rem}
.apply-btn{width:100%;padding:.55rem;background:#3483fa;color:#fff;border:none;border-radius:6px;font-size:.82rem;font-weight:600;cursor:pointer;margin-top:.6rem}
.apply-btn:hover{background:#2968c8}
.clear-btn{width:100%;padding:.45rem;background:#f5f5f5;color:#555;border:1px solid #ddd;border-radius:6px;font-size:.78rem;cursor:pointer;margin-top:.4rem}

.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:1rem}
.card{background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.08);transition:.2s;cursor:pointer}
.card:hover{box-shadow:0 4px 16px rgba(0,0,0,.14);transform:translateY(-2px)}
.card img{width:100%;height:170px;object-fit:contain;padding:.8rem;background:#f9f9f9}
.card-body{padding:.9rem}
.card-title{font-size:.85rem;font-weight:500;margin-bottom:.4rem;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.card-price{font-size:1.15rem;font-weight:700}
.card-original{font-size:.75rem;color:#999;text-decoration:line-through}
.card-discount{font-size:.75rem;color:#00a650;font-weight:600;margin-left:.3rem}
.card-free{font-size:.72rem;color:#00a650;margin-top:.2rem}
.card-condition{font-size:.7rem;color:#aaa;margin-top:.3rem}

/* PRODUCT PAGE */
.product-layout{display:grid;grid-template-columns:1fr 340px;gap:2rem;align-items:start}
.product-img-box{background:#fff;border-radius:10px;padding:2rem;text-align:center;box-shadow:0 1px 4px rgba(0,0,0,.08)}
.product-img-box img{max-width:100%;max-height:320px;object-fit:contain}
.product-info{background:#fff;border-radius:10px;padding:1.5rem;box-shadow:0 1px 4px rgba(0,0,0,.08)}
.product-condition{font-size:.75rem;color:#999;margin-bottom:.3rem}
.product-title{font-size:1.25rem;font-weight:600;margin-bottom:.8rem;line-height:1.4}
.product-price-box{margin:.8rem 0}
.product-original{font-size:.85rem;color:#999;text-decoration:line-through}
.product-price{font-size:1.9rem;font-weight:700}
.product-discount{font-size:.82rem;color:#00a650;font-weight:600}
.product-installment{font-size:.8rem;color:#555;margin-top:.15rem}
.qty-wrap{display:flex;align-items:center;gap:.8rem;margin:.8rem 0}
.qty-wrap button{width:30px;height:30px;border:1px solid #ddd;border-radius:4px;font-size:.9rem;cursor:pointer;background:#fff}
.qty-wrap button:hover{border-color:#3483fa}
.qty-wrap span{font-weight:600;min-width:20px;text-align:center}
.btn-full{width:100%;padding:.7rem;border-radius:6px;font-size:.9rem;font-weight:600;cursor:pointer;border:none;margin-bottom:.4rem}
.btn-buy{background:#3483fa;color:#fff}.btn-buy:hover{background:#2968c8}
.btn-cart{background:#fff;color:#3483fa;border:1.5px solid #3483fa}.btn-cart:hover{background:#e8f0fe}

/* FREIGHT CALC */
.freight-box{background:#f8f9fa;border:1px solid #e9ecef;border-radius:8px;padding:1rem;margin:1rem 0}
.freight-box h4{font-size:.82rem;font-weight:600;margin-bottom:.6rem}
.freight-input-row{display:flex;gap:.4rem}
.freight-input-row input{flex:1;padding:.5rem .7rem;border:1px solid #ddd;border-radius:6px;font-size:.82rem;letter-spacing:.05em}
.freight-input-row button{padding:.5rem .9rem;background:#3483fa;color:#fff;border:none;border-radius:6px;font-size:.8rem;cursor:pointer;white-space:nowrap}
.freight-result{margin-top:.8rem}
.freight-option{display:flex;justify-content:space-between;align-items:center;padding:.5rem .7rem;border:1px solid #ddd;border-radius:6px;margin-bottom:.4rem;background:#fff;cursor:pointer;transition:.15s}
.freight-option:hover,.freight-option.selected{border-color:#3483fa;background:#e8f0fe}
.freight-option-left{font-size:.8rem;font-weight:500}
.freight-option-days{font-size:.72rem;color:#777}
.freight-option-price{font-size:.85rem;font-weight:700;color:#333}
.freight-free{color:#00a650;font-weight:700}

/* REVIEWS */
.stars{color:#f5a623;font-size:.95rem}
.reviews-section{background:#fff;border-radius:10px;padding:1.5rem;margin-top:1.5rem;box-shadow:0 1px 4px rgba(0,0,0,.08)}
.review-card{border-bottom:1px solid #eee;padding:.9rem 0}
.review-card:last-child{border:none}
.review-author{font-weight:600;font-size:.83rem;margin-bottom:.3rem}
.review-text{font-size:.82rem;color:#555;line-height:1.5}
.review-form select,.review-form textarea{width:100%;padding:.55rem .8rem;border:1px solid #ddd;border-radius:6px;font-size:.83rem;margin-bottom:.5rem;font-family:inherit}
.review-form textarea{resize:vertical;min-height:75px}

/* CART */
.cart-layout{display:grid;grid-template-columns:1fr 300px;gap:1.5rem;align-items:start}
.cart-item{background:#fff;border-radius:8px;padding:1rem;display:flex;gap:1rem;margin-bottom:.7rem;box-shadow:0 1px 3px rgba(0,0,0,.07)}
.cart-item img{width:75px;height:75px;object-fit:contain;flex-shrink:0}
.cart-item-title{font-size:.85rem;font-weight:500;margin-bottom:.3rem}
.cart-item-price{font-size:1rem;font-weight:700}
.cart-item-remove{font-size:.75rem;color:#e63946;cursor:pointer;background:none;border:none;margin-top:.3rem;padding:0}
.cart-summary{background:#fff;border-radius:8px;padding:1.2rem;box-shadow:0 1px 4px rgba(0,0,0,.08)}
.summary-row{display:flex;justify-content:space-between;font-size:.85rem;margin-bottom:.5rem;color:#555}
.summary-total{display:flex;justify-content:space-between;font-size:1.05rem;font-weight:700;padding-top:.8rem;border-top:1px solid #eee;margin-top:.4rem}

/* CHECKOUT / PAYMENT */
.checkout-layout{display:grid;grid-template-columns:1fr 320px;gap:1.5rem;align-items:start}
.checkout-section{background:#fff;border-radius:10px;padding:1.5rem;box-shadow:0 1px 4px rgba(0,0,0,.08);margin-bottom:1rem}
.checkout-section h3{font-size:1rem;font-weight:700;margin-bottom:1rem;padding-bottom:.6rem;border-bottom:1px solid #eee}
.payment-methods{display:grid;grid-template-columns:repeat(3,1fr);gap:.7rem;margin-bottom:1rem}
.pay-btn{border:2px solid #ddd;border-radius:8px;padding:.8rem .5rem;text-align:center;cursor:pointer;transition:.2s;background:#fff;font-size:.78rem;font-weight:500}
.pay-btn:hover,.pay-btn.active{border-color:#3483fa;background:#e8f0fe;color:#3483fa}
.pay-btn .icon{font-size:1.5rem;display:block;margin-bottom:.3rem}
.pix-code-box{background:#f8f9fa;border:1px dashed #ccc;border-radius:8px;padding:1rem;text-align:center;margin:.8rem 0}
.pix-code{font-family:monospace;font-size:.75rem;word-break:break-all;color:#555;margin:.5rem 0}
.pix-copy-btn{background:#00a650;color:#fff;border:none;padding:.4rem 1rem;border-radius:6px;font-size:.78rem;cursor:pointer}
.card-form input{width:100%;padding:.6rem .8rem;border:1px solid #ddd;border-radius:6px;font-size:.85rem;margin-bottom:.6rem;font-family:inherit}
.card-form-row{display:grid;grid-template-columns:2fr 1fr 1fr;gap:.6rem}
.boleto-info{background:#fff3cd;border:1px solid #ffc107;border-radius:8px;padding:1rem;font-size:.83rem;color:#856404}
.order-confirm{text-align:center;padding:2rem;background:#fff;border-radius:10px;box-shadow:0 1px 4px rgba(0,0,0,.08)}
.order-confirm .check{font-size:4rem;margin-bottom:.8rem}
.order-confirm h2{font-size:1.4rem;margin-bottom:.5rem}

/* PANELS */
.panel-grid{display:grid;grid-template-columns:200px 1fr;gap:1.5rem;align-items:start}
.panel-menu{background:#fff;border-radius:8px;padding:.7rem;box-shadow:0 1px 3px rgba(0,0,0,.07)}
.panel-menu a{display:block;padding:.6rem .8rem;border-radius:6px;font-size:.85rem;color:#555;transition:.15s}
.panel-menu a:hover,.panel-menu a.active{background:#e8f0fe;color:#3483fa;font-weight:500}
.panel-menu .menu-section{font-size:.65rem;text-transform:uppercase;letter-spacing:.1em;color:#aaa;padding:.5rem .8rem .2rem;margin-top:.4rem}
.panel-content{background:#fff;border-radius:8px;padding:1.5rem;box-shadow:0 1px 3px rgba(0,0,0,.07)}
.form-group{margin-bottom:.9rem}
.form-group label{display:block;font-size:.8rem;font-weight:500;margin-bottom:.3rem;color:#555}
.form-group input,.form-group textarea,.form-group select{width:100%;padding:.55rem .8rem;border:1px solid #ddd;border-radius:6px;font-size:.83rem;font-family:inherit}
.form-group textarea{resize:vertical;min-height:85px}
.form-row{display:grid;grid-template-columns:1fr 1fr;gap:.8rem}
.table{width:100%;border-collapse:collapse;font-size:.83rem}
.table th{background:#f5f5f5;padding:.65rem .8rem;text-align:left;font-weight:600;border-bottom:2px solid #eee}
.table td{padding:.6rem .8rem;border-bottom:1px solid #f0f0f0;vertical-align:middle}
.table tr:hover td{background:#fafafa}
.badge{padding:.18rem .5rem;border-radius:99px;font-size:.7rem;font-weight:600;white-space:nowrap}
.badge-green{background:#d4edda;color:#155724}
.badge-yellow{background:#fff3cd;color:#856404}
.badge-red{background:#f8d7da;color:#721c24}
.badge-blue{background:#d1ecf1;color:#0c5460}
.badge-gray{background:#e9ecef;color:#495057}

/* STATS */
.stats-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin-bottom:1.5rem}
.stat-card{background:#fff;border-radius:8px;padding:1rem 1.2rem;box-shadow:0 1px 3px rgba(0,0,0,.07)}
.stat-num{font-size:1.6rem;font-weight:700;color:#3483fa}
.stat-label{font-size:.72rem;color:#999;margin-top:.15rem}
.stat-trend{font-size:.72rem;color:#00a650;margin-top:.15rem}

/* AUTH */
.auth-box{max-width:440px;margin:3rem auto;background:#fff;border-radius:10px;padding:2rem;box-shadow:0 2px 12px rgba(0,0,0,.1)}
.auth-box h2{text-align:center;margin-bottom:1.4rem;font-size:1.3rem}
.auth-footer{text-align:center;margin-top:1rem;font-size:.83rem;color:#666}
.auth-footer a{color:#3483fa;font-weight:500}

/* HERO */
.hero{background:linear-gradient(135deg,#3483fa,#1e5fa8);color:#fff;border-radius:10px;padding:2rem;margin-bottom:1.5rem;position:relative;overflow:hidden}
.hero h2{font-size:1.7rem;font-weight:700;margin-bottom:.4rem}
.hero p{opacity:.85;margin-bottom:1rem;font-size:.95rem}
.hero::after{content:'🛍️';position:absolute;right:2rem;top:50%;transform:translateY(-50%);font-size:5rem;opacity:.2}

/* FRETE PAGE */
.frete-layout{max-width:700px;margin:0 auto}
.frete-card{background:#fff;border-radius:12px;padding:2rem;box-shadow:0 2px 12px rgba(0,0,0,.08);margin-bottom:1.5rem}
.frete-result-table{width:100%;border-collapse:collapse;margin-top:1rem}
.frete-result-table th{background:#f5f5f5;padding:.7rem 1rem;text-align:left;font-size:.82rem;color:#555;border-bottom:2px solid #eee}
.frete-result-table td{padding:.7rem 1rem;border-bottom:1px solid #f0f0f0;font-size:.85rem}
.frete-result-table tr:hover td{background:#f8f9fa}
.uf-flag{display:inline-block;background:#3483fa;color:#fff;font-size:.65rem;font-weight:700;padding:.15rem .45rem;border-radius:4px;margin-right:.4rem}

.cat-bar{background:#fff;border-bottom:1px solid #eee;padding:.5rem 2rem;display:flex;gap:.4rem;overflow-x:auto}
.cat-btn{white-space:nowrap;padding:.3rem .75rem;border-radius:99px;font-size:.76rem;cursor:pointer;border:1px solid #ddd;background:#fff;transition:.15s}
.cat-btn:hover,.cat-btn.active{background:#3483fa;color:#fff;border-color:#3483fa}

.orders-page .order-card{background:#fff;border-radius:8px;padding:1.1rem;margin-bottom:.7rem;box-shadow:0 1px 3px rgba(0,0,0,.07)}
.order-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:.6rem}

@media(max-width:900px){
  .shop-layout{grid-template-columns:1fr}
  .filter-panel{position:static}
  .product-layout,.cart-layout,.checkout-layout,.panel-grid{grid-template-columns:1fr}
  .stats-grid{grid-template-columns:repeat(2,1fr)}
  .payment-methods{grid-template-columns:repeat(3,1fr)}
  .form-row,.card-form-row{grid-template-columns:1fr}
  .navbar{flex-wrap:wrap;height:auto;padding:.7rem 1rem;gap:.4rem}
  .search-wrap{order:3;width:100%}
}
</style>
</head>
<body>
{% set u = current_user() %}
{% if u and u.is_admin %}
<div class="admin-bar">
  🔧 Modo Admin |
  <a href="/admin">Dashboard</a>
  <a href="/admin/usuarios">Usuários</a>
  <a href="/admin/produtos">Produtos</a>
  <a href="/admin/pedidos">Pedidos</a>
  <a href="/">← Ver site</a>
</div>
{% endif %}
<nav class="navbar">
  <a href="/" class="nav-logo">M de <span>Maria</span></a>
  <div class="search-wrap">
    <form action="/busca" method="get" style="display:contents">
      <input name="q" placeholder="Buscar produtos, marcas e muito mais..." value="{{ request.args.get('q','') }}">
      <button type="submit">🔍</button>
    </form>
  </div>
  <div class="nav-links">
    {% if u %}
      <span style="font-size:.78rem;color:#555">Olá, <strong>{{ u.name.split()[0] }}</strong></span>
      {% if u.is_seller %}<a href="/painel" class="nav-btn btn-ghost">📦 Painel</a>{% endif %}
      {% if u.is_admin %}<a href="/admin" class="nav-btn btn-ghost" style="color:#e63946">⚙️ Admin</a>{% endif %}
      <a href="/pedidos" class="nav-btn btn-ghost">Pedidos</a>
      <a href="/frete" class="nav-btn btn-ghost">🚚 Frete</a>
      <a href="/logout" class="nav-btn btn-ghost">Sair</a>
    {% else %}
      <a href="/login" class="nav-btn btn-ghost">Entrar</a>
      <a href="/cadastro" class="nav-btn btn-yellow">Cadastre-se</a>
      <a href="/frete" class="nav-btn btn-ghost">🚚 Frete</a>
    {% endif %}
    <a href="/carrinho" class="cart-btn">
      🛒 Carrinho
      {% if cart_count() > 0 %}<span class="cart-badge">{{ cart_count() }}</span>{% endif %}
    </a>
  </div>
</nav>
{% with msgs = get_flashed_messages(with_categories=true) %}
  {% if msgs %}<div class="flash-wrap">{% for c,m in msgs %}<div class="alert alert-{{ c }}">{{ m }}</div>{% endfor %}</div>{% endif %}
{% endwith %}

</body>
</html>
"""

# ══════════════════════════════════════════
#  ROUTES — LOJA
# ══════════════════════════════════════════
@app.route("/")
def index():
    db = get_db()
    cat = request.args.get("cat","")
    pmin = request.args.get("pmin","")
    pmax = request.args.get("pmax","")
    sort = request.args.get("sort","recentes")
    cond = request.args.get("cond","")

    query = "SELECT p.*,u.name as seller_name FROM products p JOIN users u ON p.seller_id=u.id WHERE p.stock>0 AND p.active=1"
    params = []
    if cat and cat != "Todos":
        query += " AND p.category=?"; params.append(cat)
    if pmin:
        try: query += " AND p.price>=?"; params.append(float(pmin))
        except: pass
    if pmax:
        try: query += " AND p.price<=?"; params.append(float(pmax))
        except: pass
    if cond:
        query += " AND p.condition=?"; params.append(cond)
    sort_map = {"recentes":"p.id DESC","menor":"p.price ASC","maior":"p.price DESC","desc":"((p.original_price-p.price)/p.original_price) DESC"}
    query += f" ORDER BY {sort_map.get(sort,'p.id DESC')}"

    products = db.execute(query, params).fetchall()
    db.close()

    tmpl = BASE + r"""
<div class="cat-bar">
  {% for c in cats %}
  <a href="/?cat={{ c }}{% if request.args.get('sort') %}&sort={{ request.args.get('sort') }}{% endif %}">
    <button class="cat-btn {{ 'active' if (request.args.get('cat','')==c or (c=='Todos' and not request.args.get('cat'))) else '' }}">{{ c }}</button>
  </a>
  {% endfor %}
</div>
<div class="container">
  {% if not request.args.get('cat') and not request.args.get('pmin') %}
  <div class="hero">
    <h2>As melhores compras estão aqui</h2>
    <p>Frete grátis acima de R$ 299 · Parcele em até 12x sem juros</p>
    <a href="/?cat=Eletrônicos"><button style="background:#fff;color:#3483fa;border:none;padding:.55rem 1.2rem;border-radius:6px;font-weight:700;cursor:pointer">Ver ofertas 🔥</button></a>
  </div>
  {% endif %}
  <div class="shop-layout">
    <!-- FILTROS -->
    <div class="filter-panel">
      <form method="get" action="/">
        {% if request.args.get('cat') %}<input type="hidden" name="cat" value="{{ request.args.get('cat') }}">{% endif %}
        <h3>Filtros</h3>
        <div class="filter-section">
          <h3>Ordenar por</h3>
          {% for v,l in [('recentes','Mais recentes'),('menor','Menor preço'),('maior','Maior preço'),('desc','Maior desconto')] %}
          <label class="filter-radio"><input type="radio" name="sort" value="{{ v }}" {{ 'checked' if request.args.get('sort','')==v else '' }}>{{ l }}</label>
          {% endfor %}
        </div>
        <div class="filter-section">
          <h3>Faixa de Preço</h3>
          <div class="price-inputs">
            <input name="pmin" placeholder="R$ Mín" value="{{ request.args.get('pmin','') }}" type="number" min="0">
            <span>—</span>
            <input name="pmax" placeholder="R$ Máx" value="{{ request.args.get('pmax','') }}" type="number" min="0">
          </div>
          <div style="margin-top:.6rem">
            {% for mn,mx,lbl in [(0,500,'Até R$ 500'),(500,1500,'R$ 500–1.500'),(1500,5000,'R$ 1.500–5.000'),(5000,99999,'Acima de R$ 5.000')] %}
            <label class="filter-radio">
              <input type="radio" name="pmin" value="{{ mn }}" onchange="this.form.pmax.value='{{ mx }}'"> {{ lbl }}
            </label>
            {% endfor %}
          </div>
        </div>
        <div class="filter-section">
          <h3>Condição</h3>
          {% for c in ['Novo','Usado','Recondicionado'] %}
          <label class="filter-radio"><input type="radio" name="cond" value="{{ c }}" {{ 'checked' if request.args.get('cond')==c else '' }}>{{ c }}</label>
          {% endfor %}
        </div>
        <button type="submit" class="apply-btn">Aplicar filtros</button>
        <a href="/"><button type="button" class="clear-btn">✕ Limpar filtros</button></a>
      </form>
    </div>
    <!-- PRODUTOS -->
    <div>
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">
        <div class="page-title" style="margin:0">
          {{ products|length }} produto{{ 's' if products|length!=1 else '' }}
          {% if request.args.get('cat') %} em <em>{{ request.args.get('cat') }}</em>{% endif %}
          {% if request.args.get('pmin') or request.args.get('pmax') %}
            — R$ {{ request.args.get('pmin',0) }} a R$ {{ request.args.get('pmax','∞') }}
          {% endif %}
        </div>
      </div>
      <div class="grid">
        {% for p in products %}
        <a href="/produto/{{ p.id }}">
        <div class="card">
          <img src="{{ p.image_url or 'https://via.placeholder.com/300' }}" alt="{{ p.title }}" loading="lazy">
          <div class="card-body">
            <div class="card-title">{{ p.title }}</div>
            {% if p.original_price and p.original_price > p.price %}
            <div class="card-original">{{ fmt_brl(p.original_price) }}<span class="card-discount">{{ ((1-p.price/p.original_price)*100)|int }}% OFF</span></div>
            {% endif %}
            <div class="card-price">{{ fmt_brl(p.price) }}</div>
            <div class="card-free">{% if p.price >= 299 %}✅ Frete grátis{% else %}🚚 Calcular frete{% endif %}</div>
            <div class="card-condition">{{ p.condition }}</div>
          </div>
        </div></a>
        {% else %}
        <div style="grid-column:1/-1;text-align:center;padding:3rem;color:#999">
          <div style="font-size:2.5rem;margin-bottom:.5rem">😕</div>
          Nenhum produto encontrado para esses filtros.
          <br><a href="/" style="color:#3483fa;font-size:.85rem">Limpar filtros</a>
        </div>
        {% endfor %}
      </div>
    </div>
  </div>
</div>

"""
    return render_template_string(tmpl, products=products, cats=CATEGORIES)


@app.route("/busca")
def busca():
    q = request.args.get("q","").strip()
    db = get_db()
    products = db.execute("""SELECT p.*,u.name as seller_name FROM products p
        JOIN users u ON p.seller_id=u.id
        WHERE p.stock>0 AND p.active=1 AND (p.title LIKE ? OR p.description LIKE ? OR p.category LIKE ?)
        ORDER BY p.id DESC""", (f"%{q}%",f"%{q}%",f"%{q}%")).fetchall()
    db.close()
    tmpl = BASE + r"""
<div class="container">
  <div class="page-title">Resultados para "<em>{{ q }}</em>" ({{ products|length }})</div>
  <div class="grid">
    {% for p in products %}
    <a href="/produto/{{ p.id }}"><div class="card">
      <img src="{{ p.image_url or 'https://via.placeholder.com/300' }}" alt="{{ p.title }}" loading="lazy">
      <div class="card-body">
        <div class="card-title">{{ p.title }}</div>
        {% if p.original_price and p.original_price > p.price %}
        <div class="card-original">{{ fmt_brl(p.original_price) }}<span class="card-discount">{{ ((1-p.price/p.original_price)*100)|int }}% OFF</span></div>
        {% endif %}
        <div class="card-price">{{ fmt_brl(p.price) }}</div>
        <div class="card-free">{% if p.price >= 299 %}✅ Frete grátis{% else %}🚚 Calcular frete{% endif %}</div>
      </div>
    </div></a>
    {% else %}
    <div style="grid-column:1/-1;text-align:center;padding:3rem;color:#999">
      <div style="font-size:2.5rem">😕</div>
      Nenhum resultado para "<strong>{{ q }}</strong>".
      <br><a href="/" style="color:#3483fa;font-size:.85rem">← Voltar</a>
    </div>
    {% endfor %}
  </div>
</div>

"""
    return render_template_string(tmpl, products=products, q=q)


@app.route("/produto/<int:pid>")
def produto(pid):
    db = get_db()
    p = db.execute("""SELECT p.*,u.name as seller_name FROM products p
        JOIN users u ON p.seller_id=u.id WHERE p.id=?""", (pid,)).fetchone()
    if not p:
        db.close(); flash("Produto não encontrado.", "danger"); return redirect(url_for("index"))
    reviews = db.execute("""SELECT r.*,u.name as author FROM reviews r
        JOIN users u ON r.user_id=u.id WHERE r.product_id=? ORDER BY r.id DESC""", (pid,)).fetchall()
    avg = db.execute("SELECT AVG(rating) as a FROM reviews WHERE product_id=?", (pid,)).fetchone()["a"]
    avg = round(avg or 0, 1)
    db.close()
    discount = int((1-p["price"]/p["original_price"])*100) if p["original_price"] and p["original_price"]>p["price"] else 0

    tmpl = BASE + r"""
<div class="container">
  <div style="font-size:.78rem;color:#999;margin-bottom:1rem">
    <a href="/">Início</a> › <a href="/?cat={{ p.category }}">{{ p.category }}</a> › {{ p.title[:45] }}
  </div>
  <div class="product-layout">
    <div>
      <div class="product-img-box">
        <img src="{{ p.image_url or 'https://via.placeholder.com/400' }}" alt="{{ p.title }}">
      </div>
    </div>
    <div>
      <div class="product-info">
        <div class="product-condition">{{ p.condition }} | {{ p.category }}</div>
        <div class="product-title">{{ p.title }}</div>
        <div><span class="stars">{{ '★'*avg_int }}{{ '☆'*(5-avg_int) }}</span>
          <span style="font-size:.75rem;color:#999"> ({{ reviews|length }} avaliações)</span></div>
        <div class="product-price-box">
          {% if p.original_price and p.original_price > p.price %}
          <div class="product-original">{{ fmt_brl(p.original_price) }}</div>
          <div class="product-price">{{ fmt_brl(p.price) }} <span class="product-discount">{{ discount }}% OFF</span></div>
          {% else %}
          <div class="product-price">{{ fmt_brl(p.price) }}</div>
          {% endif %}
          <div class="product-installment">em até 12x de {{ fmt_brl(p.price/12) }} sem juros</div>
        </div>
        <div style="font-size:.8rem;color:#555;margin-bottom:.6rem">
          📦 <strong>{{ p.stock }}</strong> unidades disponíveis
        </div>
        <div style="font-size:.8rem;color:#00a650;margin-bottom:.8rem">
          {% if p.price >= 299 %}✅ <strong>Frete grátis</strong> para todo o Brasil{% else %}🚚 Calcule o frete abaixo{% endif %}
        </div>

        <!-- CALCULADORA DE FRETE INLINE -->
        <div class="freight-box">
          <h4>🚚 Calcular frete e prazo</h4>
          <div class="freight-input-row">
            <input type="text" id="cep-input" placeholder="00000-000" maxlength="9"
              oninput="this.value=this.value.replace(/\D/g,'').replace(/(\d{5})(\d)/,'$1-$2')">
            <button onclick="calcFrete({{ p.weight_kg }}, {{ p.price }})">Calcular</button>
          </div>
          <div class="freight-result" id="frete-result"></div>
        </div>

        <div class="qty-wrap">
          <span style="font-size:.8rem;color:#555">Qtd:</span>
          <button onclick="changeQty(-1)">−</button>
          <span id="qty">1</span>
          <button onclick="changeQty(1)">+</button>
        </div>
        <form action="/carrinho/add/{{ p.id }}" method="post" id="cartForm">
          <input type="hidden" name="qty" id="qtyInput" value="1">
          <input type="hidden" name="selected_freight" id="selectedFreight" value="">
          <button type="button" class="btn-full btn-buy" onclick="buyNow()">⚡ Comprar agora</button>
          <button type="submit" class="btn-full btn-cart">🛒 Adicionar ao carrinho</button>
        </form>
        <hr style="margin:.9rem 0;border:none;border-top:1px solid #eee">
        <div style="font-size:.79rem;color:#555">
          👤 Vendedor: <strong>{{ p.seller_name }}</strong><br>
          📅 {{ p.created_at[:10] }}
        </div>
      </div>
    </div>
  </div>

  {% if p.description %}
  <div class="reviews-section" style="margin-top:1.5rem">
    <h3 style="margin-bottom:.7rem">Descrição do produto</h3>
    <p style="font-size:.87rem;line-height:1.7;color:#444">{{ p.description }}</p>
  </div>
  {% endif %}

  <div class="reviews-section">
    <h3 style="margin-bottom:.9rem">Avaliações ({{ reviews|length }})</h3>
    {% set cu = current_user() %}
    {% if cu %}
    <div style="background:#f9f9f9;padding:1rem;border-radius:8px;margin-bottom:1rem">
      <h4 style="font-size:.85rem;margin-bottom:.7rem">Deixe sua avaliação</h4>
      <form action="/produto/{{ p.id }}/review" method="post" class="review-form">
        <select name="rating" required>
          <option value="">⭐ Escolha uma nota</option>
          <option value="5">⭐⭐⭐⭐⭐ Excelente</option>
          <option value="4">⭐⭐⭐⭐ Muito bom</option>
          <option value="3">⭐⭐⭐ Bom</option>
          <option value="2">⭐⭐ Regular</option>
          <option value="1">⭐ Ruim</option>
        </select>
        <textarea name="comment" placeholder="Conta sua experiência..."></textarea>
        <button type="submit" class="btn-full btn-buy" style="font-size:.82rem;padding:.55rem">Enviar avaliação</button>
      </form>
    </div>
    {% else %}
    <p style="font-size:.8rem;color:#999;margin-bottom:.8rem"><a href="/login" style="color:#3483fa">Faça login</a> para avaliar.</p>
    {% endif %}
    {% for r in reviews %}
    <div class="review-card">
      <div class="review-author">{{ r.author }} <span class="stars" style="font-size:.75rem">{{ '★'*r.rating }}{{ '☆'*(5-r.rating) }}</span></div>
      <div class="review-text">{{ r.comment or '' }}</div>
      <div style="font-size:.7rem;color:#aaa;margin-top:.2rem">{{ r.created_at[:10] }}</div>
    </div>
    {% else %}<p style="font-size:.8rem;color:#aaa">Sem avaliações ainda. Seja o primeiro!</p>{% endfor %}
  </div>
</div>
<script>
let qty=1,stock={{ p.stock }};
function changeQty(d){qty=Math.min(Math.max(1,qty+d),stock);document.getElementById('qty').textContent=qty;document.getElementById('qtyInput').value=qty;}
function buyNow(){document.getElementById('cartForm').action='/carrinho/add/{{ p.id }}?next=checkout';document.getElementById('cartForm').submit();}
function calcFrete(peso, preco){
  const cep=document.getElementById('cep-input').value.replace(/\D/g,'');
  if(cep.length!==8){alert('CEP inválido! Digite 8 dígitos.');return;}
  fetch('/api/frete?cep='+cep+'&peso='+peso+'&subtotal='+preco)
    .then(r=>r.json()).then(d=>{
      if(d.error){document.getElementById('frete-result').innerHTML='<p style="color:#e63946;font-size:.8rem">'+d.error+'</p>';return;}
      let html=`<div style="font-size:.75rem;color:#777;margin-bottom:.4rem">📍 ${d.cep} — Estado: <strong>${d.uf}</strong></div>`;
      for(const [tipo,info] of Object.entries({PAC:d.PAC,SEDEX:d.SEDEX})){
        html+=`<div class="freight-option" onclick="selectFreight('${tipo}',${info.price},this)">
          <div><div class="freight-option-left">${tipo==='PAC'?'📦 PAC (Correios)':'⚡ SEDEX (Expresso)'}</div>
          <div class="freight-option-days">Prazo: até ${info.days} dia(s) úteis</div></div>
          <div class="freight-option-price ${info.price===0?'freight-free':''}">${info.price===0?'GRÁTIS':'R$ '+info.price.toFixed(2).replace('.',',')}</div>
        </div>`;
      }
      document.getElementById('frete-result').innerHTML=html;
    }).catch(()=>document.getElementById('frete-result').innerHTML='<p style="color:#e63946;font-size:.8rem">Erro ao calcular frete.</p>');
}
function selectFreight(tipo,preco,el){
  document.querySelectorAll('.freight-option').forEach(e=>e.classList.remove('selected'));
  el.classList.add('selected');
  document.getElementById('selectedFreight').value=tipo+'|'+preco;
}
</script>

"""
    return render_template_string(tmpl, p=dict(p), reviews=reviews, avg=avg, avg_int=int(avg), discount=discount)


@app.route("/api/frete")
def api_frete():
    cep = request.args.get("cep","")
    peso = float(request.args.get("peso", 0.5))
    subtotal = float(request.args.get("subtotal", 0))
    result = calcular_frete(cep, peso, subtotal)
    if not result:
        return jsonify({"error": "CEP inválido. Digite 8 dígitos numéricos."})
    return jsonify(result)


@app.route("/produto/<int:pid>/review", methods=["POST"])
@login_required
def add_review(pid):
    db = get_db()
    if not db.execute("SELECT id FROM reviews WHERE product_id=? AND user_id=?", (pid,session["user_id"])).fetchone():
        db.execute("INSERT INTO reviews (product_id,user_id,rating,comment) VALUES (?,?,?,?)",
                   (pid,session["user_id"],int(request.form.get("rating",3)),request.form.get("comment","").strip()))
        db.commit()
        flash("Avaliação enviada! 🙏", "success")
    else:
        flash("Você já avaliou este produto.", "warning")
    db.close()
    return redirect(url_for("produto", pid=pid))


# ══════════════════════════════════════════
#  CALCULADORA DE FRETE (PÁGINA DEDICADA)
# ══════════════════════════════════════════
@app.route("/frete")
def frete_page():
    tmpl = BASE + r"""
<div class="container frete-layout">
  <div class="page-title">🚚 Calculadora de Frete</div>

  <div class="frete-card">
    <h3 style="margin-bottom:1rem;font-size:1.05rem">Calcule o valor do frete por CEP</h3>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:.8rem;margin-bottom:1rem">
      <div class="form-group" style="margin:0">
        <label>CEP de destino *</label>
        <input type="text" id="fc-cep" placeholder="00000-000" maxlength="9"
          oninput="this.value=this.value.replace(/\D/g,'').replace(/(\d{5})(\d)/,'$1-$2')">
      </div>
      <div class="form-group" style="margin:0">
        <label>Peso do pacote (kg)</label>
        <input type="number" id="fc-peso" value="0.5" step="0.1" min="0.1" max="30">
      </div>
      <div class="form-group" style="margin:0">
        <label>Valor da compra (R$)</label>
        <input type="number" id="fc-valor" value="0" step="0.01" min="0" placeholder="0,00">
      </div>
    </div>
    <button onclick="calcularFreteCompleto()" style="background:#3483fa;color:#fff;border:none;padding:.65rem 2rem;border-radius:8px;font-size:.9rem;font-weight:600;cursor:pointer">
      📦 Calcular frete
    </button>
    <div id="fc-result" style="margin-top:1.2rem"></div>
  </div>

  <div class="frete-card">
    <h3 style="margin-bottom:.8rem;font-size:1rem">📋 Tabela de prazos por estado</h3>
    <p style="font-size:.82rem;color:#777;margin-bottom:1rem">Valores de referência para 0,5kg · Frete grátis acima de R$ 299 no PAC</p>
    <table class="frete-result-table">
      <thead><tr><th>Estado</th><th>PAC (dias úteis)</th><th>PAC (R$)</th><th>SEDEX (dias úteis)</th><th>SEDEX (R$)</th></tr></thead>
      <tbody>
        {% for uf, dados in tabela.items() %}
        {% if uf != 'DEFAULT' %}
        <tr>
          <td><span class="uf-flag">{{ uf }}</span></td>
          <td>Até {{ dados.days_pac }} dias</td>
          <td>R$ {{ "%.2f"|format(dados.PAC) }}</td>
          <td>Até {{ dados.days_sedex }} dias</td>
          <td>R$ {{ "%.2f"|format(dados.SEDEX) }}</td>
        </tr>
        {% endif %}
        {% endfor %}
      </tbody>
    </table>
  </div>

  <div class="frete-card" style="background:#e8f4fd;border:1px solid #b8daff">
    <h3 style="font-size:.95rem;margin-bottom:.6rem;color:#0c5460">ℹ️ Como funciona o frete?</h3>
    <ul style="font-size:.83rem;color:#555;line-height:1.9;padding-left:1.2rem">
      <li><strong>PAC Grátis:</strong> Compras acima de R$ 299 têm frete PAC gratuito.</li>
      <li><strong>PAC:</strong> Entrega econômica pelos Correios. Prazo de 3 a 14 dias úteis conforme a região.</li>
      <li><strong>SEDEX:</strong> Entrega expresso, mais rápida. Disponível para todo o Brasil.</li>
      <li><strong>Peso:</strong> O frete é calculado com base no peso do produto. Pedidos com múltiplos produtos somam o peso.</li>
      <li><strong>Rastreio:</strong> Código de rastreio enviado por e-mail após confirmação do pagamento.</li>
    </ul>
  </div>
</div>
<script>
function calcularFreteCompleto(){
  const cep=document.getElementById('fc-cep').value.replace(/\D/g,'');
  const peso=parseFloat(document.getElementById('fc-peso').value)||0.5;
  const valor=parseFloat(document.getElementById('fc-valor').value)||0;
  if(cep.length!==8){alert('CEP inválido!');return;}
  fetch('/api/frete?cep='+cep+'&peso='+peso+'&subtotal='+valor)
    .then(r=>r.json()).then(d=>{
      if(d.error){document.getElementById('fc-result').innerHTML='<p style="color:#e63946">'+d.error+'</p>';return;}
      const fmt=v=>v===0?'<strong style="color:#00a650">GRÁTIS</strong>':'<strong>R$ '+v.toFixed(2).replace('.',',')+'</strong>';
      document.getElementById('fc-result').innerHTML=`
        <div style="background:#f8f9fa;border-radius:8px;padding:1.2rem;border:1px solid #dee2e6">
          <div style="font-size:.85rem;margin-bottom:1rem">
            📍 CEP <strong>${d.cep}</strong> — Estado: <strong>${d.uf}</strong>
            ${valor>=299?'<span style="background:#d4edda;color:#155724;padding:.15rem .5rem;border-radius:99px;font-size:.72rem;margin-left:.5rem">✅ PAC Grátis!</span>':''}
          </div>
          <table style="width:100%;border-collapse:collapse;font-size:.85rem">
            <tr style="border-bottom:1px solid #eee">
              <th style="text-align:left;padding:.5rem;color:#555">Modalidade</th>
              <th style="padding:.5rem;color:#555">Prazo</th>
              <th style="text-align:right;padding:.5rem;color:#555">Valor</th>
            </tr>
            <tr style="border-bottom:1px solid #f0f0f0">
              <td style="padding:.6rem">📦 PAC (Correios)</td>
              <td style="text-align:center;padding:.6rem;color:#777">Até ${d.PAC.days} dias úteis</td>
              <td style="text-align:right;padding:.6rem">${fmt(d.PAC.price)}</td>
            </tr>
            <tr>
              <td style="padding:.6rem">⚡ SEDEX (Expresso)</td>
              <td style="text-align:center;padding:.6rem;color:#777">Até ${d.SEDEX.days} dias úteis</td>
              <td style="text-align:right;padding:.6rem">${fmt(d.SEDEX.price)}</td>
            </tr>
          </table>
          ${valor>0&&valor<299?`<p style="font-size:.75rem;color:#777;margin-top:.6rem">💡 Adicione mais R$ ${(299-valor).toFixed(2).replace('.',',')} e ganhe frete PAC grátis!</p>`:''}
        </div>`;
    });
}
document.getElementById('fc-cep').addEventListener('keydown',e=>{if(e.key==='Enter')calcularFreteCompleto();});
</script>

"""
    return render_template_string(tmpl, tabela=FREIGHT_TABLE)


# ══════════════════════════════════════════
#  CART
# ══════════════════════════════════════════
@app.route("/carrinho/add/<int:pid>", methods=["POST"])
def cart_add(pid):
    qty = int(request.form.get("qty",1))
    cart = session.get("cart",{})
    cart[str(pid)] = cart.get(str(pid),0) + qty
    session["cart"] = cart
    flash("Produto adicionado ao carrinho! 🛒", "success")
    next_page = request.args.get("next","")
    if next_page == "checkout":
        return redirect(url_for("checkout_page"))
    return redirect(request.referrer or url_for("index"))

@app.route("/carrinho/remove/<int:pid>", methods=["POST"])
def cart_remove(pid):
    cart = session.get("cart",{})
    cart.pop(str(pid),None)
    session["cart"] = cart
    return redirect(url_for("carrinho"))

@app.route("/carrinho")
def carrinho():
    cart = session.get("cart",{})
    items, total, peso_total = [], 0, 0
    if cart:
        db = get_db()
        for pid,qty in cart.items():
            p = db.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
            if p:
                sub = p["price"]*qty
                total += sub
                peso_total += (p["weight_kg"] or 0.5)*qty
                items.append({"product":dict(p),"qty":qty,"subtotal":sub})
        db.close()
    tmpl = BASE + r"""
<div class="container">
  <div class="page-title">🛒 Meu Carrinho ({{ items|length }} iten{{ 's' if items|length!=1 else '' }})</div>
  {% if items %}
  <div class="cart-layout">
    <div>
      {% for item in items %}
      <div class="cart-item">
        <img src="{{ item.product.image_url or 'https://via.placeholder.com/80' }}" alt="">
        <div style="flex:1">
          <div class="cart-item-title">{{ item.product.title }}</div>
          <div style="font-size:.76rem;color:#aaa">Qtd: {{ item.qty }} · {{ item.product.condition }}</div>
          <div class="cart-item-price">{{ fmt_brl(item.subtotal) }}</div>
          <div style="font-size:.74rem;color:#aaa">({{ fmt_brl(item.product.price) }} cada)</div>
          <form action="/carrinho/remove/{{ item.product.id }}" method="post">
            <button class="cart-item-remove">🗑️ Remover</button>
          </form>
        </div>
      </div>
      {% endfor %}
    </div>
    <div class="cart-summary">
      <h3 style="margin-bottom:1rem;font-size:.95rem">Resumo</h3>
      {% for item in items %}
      <div class="summary-row"><span>{{ item.product.title[:28] }}...</span><span>{{ fmt_brl(item.subtotal) }}</span></div>
      {% endfor %}
      <div class="summary-row" style="color:#00a650"><span>🚚 Frete PAC</span><span>{{ 'Grátis' if total>=299 else 'Ver no checkout' }}</span></div>
      <div class="summary-total"><span>Total</span><span>{{ fmt_brl(total) }}</span></div>
      <div style="font-size:.73rem;color:#999;margin-top:.3rem;margin-bottom:.8rem">em até 12x de {{ fmt_brl(total/12) }}</div>
      <a href="/checkout"><button class="btn-full btn-buy">Continuar para pagamento →</button></a>
      <a href="/"><button class="btn-full btn-cart" style="margin-top:.4rem">← Continuar comprando</button></a>
    </div>
  </div>
  {% else %}
  <div style="text-align:center;padding:4rem;color:#999">
    <div style="font-size:3.5rem;margin-bottom:1rem">🛒</div>
    <p style="margin-bottom:1rem">Seu carrinho está vazio.</p>
    <a href="/"><button class="btn-full btn-buy" style="max-width:200px;margin:0 auto">Ver produtos</button></a>
  </div>
  {% endif %}
</div>

"""
    return render_template_string(tmpl, items=items, total=total, peso_total=peso_total)


# ══════════════════════════════════════════
#  CHECKOUT & PAGAMENTO
# ══════════════════════════════════════════
@app.route("/checkout")
@login_required
def checkout_page():
    cart = session.get("cart",{})
    if not cart:
        flash("Carrinho vazio.", "warning"); return redirect(url_for("carrinho"))
    db = get_db()
    items, subtotal, peso_total = [], 0, 0
    for pid,qty in cart.items():
        p = db.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
        if p:
            sub = p["price"]*qty
            subtotal += sub
            peso_total += (p["weight_kg"] or 0.5)*qty
            items.append({"product":dict(p),"qty":qty,"subtotal":sub})
    user = db.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    db.close()

    pix_code = gen_code("PIX.",16)
    boleto_code = f"{random.randint(1000,9999)}.{random.randint(10000,99999)} {random.randint(10000,99999)}.{random.randint(100000,999999)} {random.randint(10000,99999)}.{random.randint(100000,999999)} {random.randint(1,9)} {random.randint(10000000000,99999999999)}"

    tmpl = BASE + r"""
<div class="container">
  <div class="page-title">💳 Finalizar Compra</div>
  <div class="checkout-layout">
    <div>
      <!-- ENDEREÇO -->
      <div class="checkout-section">
        <h3>📍 Endereço de entrega</h3>
        <form id="checkoutForm" action="/checkout/finalizar" method="post">
        <input type="hidden" name="pix_code" value="{{ pix_code }}">
        <input type="hidden" name="subtotal" value="{{ subtotal }}">
        <div class="form-row">
          <div class="form-group">
            <label>CEP *</label>
            <input name="cep" type="text" maxlength="9" placeholder="00000-000" required
              oninput="this.value=this.value.replace(/\D/g,'').replace(/(\d{5})(\d)/,'$1-$2')"
              value="{{ user.address.split('|')[0] if user.address else '' }}">
          </div>
          <div class="form-group"><label>Nome completo *</label>
            <input name="recipient" value="{{ user.name }}" required></div>
        </div>
        <div class="form-row">
          <div class="form-group"><label>Rua / Av. *</label><input name="street" placeholder="Rua das Flores, 123" required></div>
          <div class="form-group"><label>Complemento</label><input name="complement" placeholder="Apto, Bloco..."></div>
        </div>
        <div class="form-row">
          <div class="form-group"><label>Cidade *</label><input name="city" required></div>
          <div class="form-group"><label>Estado *</label>
            <select name="state" required>
              {% for uf in ['AC','AL','AM','AP','BA','CE','DF','ES','GO','MA','MG','MS','MT','PA','PB','PE','PI','PR','RJ','RN','RO','RR','RS','SC','SE','SP','TO'] %}
              <option>{{ uf }}</option>{% endfor %}
            </select></div>
        </div>
      </div>

      <!-- FRETE NO CHECKOUT -->
      <div class="checkout-section">
        <h3>🚚 Opções de entrega</h3>
        <div class="freight-input-row" style="margin-bottom:.8rem">
          <input type="text" id="ck-cep" placeholder="00000-000" maxlength="9"
            oninput="this.value=this.value.replace(/\D/g,'').replace(/(\d{5})(\d)/,'$1-$2')">
          <button type="button" onclick="calcCheckoutFrete({{ peso_total }}, {{ subtotal }})">Calcular</button>
        </div>
        <div id="ck-frete-result"></div>
        <input type="hidden" name="freight_type" id="freight_type" value="PAC">
        <input type="hidden" name="freight_value" id="freight_value" value="{{ '0' if subtotal>=299 else '15.90' }}">
      </div>

      <!-- PAGAMENTO -->
      <div class="checkout-section">
        <h3>💳 Forma de pagamento</h3>
        <div class="payment-methods">
          <div class="pay-btn active" id="pay-pix" onclick="selectPay('pix')">
            <span class="icon">⚡</span>PIX
          </div>
          <div class="pay-btn" id="pay-boleto" onclick="selectPay('boleto')">
            <span class="icon">🧾</span>Boleto
          </div>
          <div class="pay-btn" id="pay-card" onclick="selectPay('card')">
            <span class="icon">💳</span>Cartão
          </div>
        </div>
        <input type="hidden" name="payment_method" id="payment_method" value="PIX">

        <!-- PIX -->
        <div id="panel-pix">
          <div class="pix-code-box">
            <div style="font-size:2.5rem;margin-bottom:.4rem">⚡</div>
            <div style="font-size:.82rem;color:#555;margin-bottom:.5rem">Copie o código PIX abaixo ou escaneie o QR code:</div>
            <div class="pix-code">{{ pix_code }}</div>
            <button type="button" class="pix-copy-btn" onclick="navigator.clipboard.writeText('{{ pix_code }}').then(()=>this.textContent='✓ Copiado!')">📋 Copiar código PIX</button>
          </div>
          <div style="font-size:.78rem;color:#777;text-align:center">⏱ Código válido por 30 minutos · Aprovação instantânea</div>
        </div>

        <!-- BOLETO -->
        <div id="panel-boleto" style="display:none">
          <div class="boleto-info">
            <strong>📄 Boleto Bancário</strong><br>
            Vencimento: {{ (3)|string }} dias úteis após emissão.<br>
            Aprovação em até 3 dias úteis após o pagamento.<br><br>
            <strong>Código:</strong><br>
            <span style="font-family:monospace;font-size:.8rem">{{ boleto_code }}</span>
          </div>
        </div>

        <!-- CARTÃO -->
        <div id="panel-card" style="display:none" class="card-form">
          <input name="card_number" placeholder="Número do cartão (0000 0000 0000 0000)"
            maxlength="19" oninput="formatCard(this)">
          <input name="card_name" placeholder="Nome igual no cartão">
          <div class="card-form-row">
            <input name="card_expiry" placeholder="MM/AA" maxlength="5">
            <input name="card_cvv" placeholder="CVV" maxlength="4">
            <select name="card_parcelas">
              {% for i in range(1,13) %}
              <option value="{{ i }}">{{ i }}x de {{ fmt_brl(subtotal/i) }}</option>
              {% endfor %}
            </select>
          </div>
        </div>
      </div>

      <button type="submit" form="checkoutForm" class="btn-full btn-buy" style="font-size:1rem;padding:.8rem">
        ✅ Confirmar pedido
      </button>
      </form>
    </div>

    <!-- RESUMO -->
    <div>
      <div class="cart-summary">
        <h3 style="margin-bottom:1rem;font-size:.95rem">📦 Resumo do pedido</h3>
        {% for item in items %}
        <div class="summary-row">
          <span>{{ item.product.title[:25] }}... (x{{ item.qty }})</span>
          <span>{{ fmt_brl(item.subtotal) }}</span>
        </div>
        {% endfor %}
        <div class="summary-row" style="color:#00a650" id="frete-summary-row">
          <span>🚚 Frete</span><span id="frete-summary-val">{{ 'Grátis' if subtotal>=299 else 'A calcular' }}</span>
        </div>
        <div class="summary-total">
          <span>Total</span><span id="total-summary">{{ fmt_brl(subtotal) }}</span>
        </div>
        <div style="font-size:.72rem;color:#999;margin-top:.3rem">
          {{ subtotal|round(2) >= 299 and '✅ PAC Grátis aplicado!' or '' }}
        </div>
      </div>
    </div>
  </div>
</div>
<script>
let sub={{ subtotal }};
function selectPay(m){
  ['pix','boleto','card'].forEach(p=>{
    document.getElementById('pay-'+p).classList.toggle('active',p===m);
    document.getElementById('panel-'+p).style.display=p===m?'block':'none';
  });
  document.getElementById('payment_method').value=m.toUpperCase();
}
function formatCard(i){i.value=i.value.replace(/\D/g,'').replace(/(.{4})/g,'$1 ').trim().slice(0,19);}
function calcCheckoutFrete(peso,subtotal){
  const cep=document.getElementById('ck-cep').value.replace(/\D/g,'');
  if(cep.length!==8){alert('CEP inválido!');return;}
  fetch('/api/frete?cep='+cep+'&peso='+peso+'&subtotal='+subtotal)
    .then(r=>r.json()).then(d=>{
      if(d.error){document.getElementById('ck-frete-result').innerHTML='<p style="color:#e63946;font-size:.8rem">'+d.error+'</p>';return;}
      let html='';
      for(const [tipo,info] of Object.entries({PAC:d.PAC,SEDEX:d.SEDEX})){
        html+=`<div class="freight-option" onclick="pickFrete('${tipo}',${info.price},this)">
          <div><div class="freight-option-left">${tipo==='PAC'?'📦 PAC':'⚡ SEDEX'}</div>
          <div class="freight-option-days">Até ${info.days} dias úteis</div></div>
          <div class="freight-option-price ${info.price===0?'freight-free':''}">${info.price===0?'GRÁTIS':'R$ '+info.price.toFixed(2).replace('.',',')}</div>
        </div>`;
      }
      document.getElementById('ck-frete-result').innerHTML=html;
      // auto-select PAC
      pickFrete('PAC',d.PAC.price,document.querySelector('.freight-option'));
      document.querySelector('.freight-option').classList.add('selected');
    });
}
function pickFrete(tipo,preco,el){
  document.querySelectorAll('#ck-frete-result .freight-option').forEach(e=>e.classList.remove('selected'));
  if(el)el.classList.add('selected');
  document.getElementById('freight_type').value=tipo;
  document.getElementById('freight_value').value=preco;
  const tot=sub+preco;
  document.getElementById('frete-summary-val').textContent=preco===0?'Grátis':'R$ '+preco.toFixed(2).replace('.',',');
  document.getElementById('total-summary').textContent='R$ '+tot.toFixed(2).replace('.',',');
}
</script>

"""
    return render_template_string(tmpl, items=items, subtotal=subtotal, peso_total=peso_total,
                                  user=dict(user), pix_code=pix_code, boleto_code=boleto_code)


@app.route("/checkout/finalizar", methods=["POST"])
@login_required
def checkout_finalizar():
    cart = session.get("cart",{})
    if not cart: return redirect(url_for("carrinho"))

    db = get_db()
    subtotal = float(request.form.get("subtotal",0))
    freight = float(request.form.get("freight_value",0))
    total = subtotal + freight
    payment_method = request.form.get("payment_method","PIX")
    pix_code = request.form.get("pix_code","")
    freight_type = request.form.get("freight_type","PAC")
    shipping_parts = [request.form.get("street",""), request.form.get("complement",""),
                      request.form.get("city",""), request.form.get("state",""),
                      request.form.get("cep",""), request.form.get("recipient","")]
    shipping_address = " | ".join(p for p in shipping_parts if p)
    tracking = gen_code("BR",9) + "BR"
    payment_code = pix_code if payment_method=="PIX" else gen_code("BOL.",10)
    status = "Pago" if payment_method=="PIX" else "Aguardando pagamento"

    order_items = []
    for pid,qty in cart.items():
        p = db.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
        if p and p["stock"]>=qty:
            order_items.append((pid,qty,p["price"]))

    if not order_items:
        flash("Produtos indisponíveis.", "danger"); db.close(); return redirect(url_for("carrinho"))

    cur = db.execute("""INSERT INTO orders
        (buyer_id,subtotal,freight,total,status,payment_method,payment_code,shipping_address,tracking_code)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (session["user_id"],subtotal,freight,total,status,payment_method,payment_code,shipping_address,tracking))
    oid = cur.lastrowid
    for pid,qty,price in order_items:
        db.execute("INSERT INTO order_items (order_id,product_id,qty,price) VALUES (?,?,?,?)", (oid,pid,qty,price))
        db.execute("UPDATE products SET stock=stock-? WHERE id=?", (qty,pid))
    db.commit(); db.close()
    session["cart"] = {}
    session["last_order"] = oid
    return redirect(url_for("order_confirm", oid=oid))


@app.route("/pedido/confirmado/<int:oid>")
@login_required
def order_confirm(oid):
    db = get_db()
    order = db.execute("SELECT * FROM orders WHERE id=? AND buyer_id=?", (oid,session["user_id"])).fetchone()
    db.close()
    if not order: return redirect(url_for("pedidos"))
    tmpl = BASE + r"""
<div class="container" style="max-width:600px">
  <div class="order-confirm">
    <div class="check">🎉</div>
    <h2>Pedido #{{ o.id }} confirmado!</h2>
    <p style="color:#555;margin-bottom:1.5rem;font-size:.9rem">
      {% if o.payment_method=='PIX' %}Pagamento aprovado instantaneamente via PIX.
      {% elif o.payment_method=='BOLETO' %}Aguardando pagamento do boleto (até 3 dias úteis).
      {% else %}Pagamento via cartão em processamento.{% endif %}
    </p>
    <div style="background:#f8f9fa;border-radius:10px;padding:1.2rem;text-align:left;margin-bottom:1.5rem;font-size:.85rem">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:.6rem">
        <div><strong>Total pago</strong><br>{{ fmt_brl(o.total) }}</div>
        <div><strong>Frete</strong><br>{{ 'Grátis' if o.freight==0 else fmt_brl(o.freight) }}</div>
        <div><strong>Pagamento</strong><br>{{ o.payment_method }}</div>
        <div><strong>Status</strong><br><span class="badge badge-{{ 'green' if o.status=='Pago' else 'yellow' }}">{{ o.status }}</span></div>
      </div>
      {% if o.tracking_code %}
      <div style="margin-top:.8rem;padding-top:.8rem;border-top:1px solid #eee">
        📦 Rastreio: <strong>{{ o.tracking_code }}</strong>
      </div>
      {% endif %}
      {% if o.shipping_address %}
      <div style="margin-top:.5rem">📍 {{ o.shipping_address }}</div>
      {% endif %}
    </div>
    <a href="/pedidos"><button class="btn-full btn-buy" style="max-width:280px;margin:0 auto .6rem">Ver meus pedidos</button></a>
    <a href="/"><button class="btn-full btn-cart" style="max-width:280px;margin:0 auto">Continuar comprando</button></a>
  </div>
</div>

"""
    return render_template_string(tmpl, o=dict(order))


@app.route("/pedidos")
@login_required
def pedidos():
    db = get_db()
    orders = db.execute("""SELECT o.*,GROUP_CONCAT(p.title,' | ') as titles
        FROM orders o LEFT JOIN order_items oi ON o.id=oi.order_id
        LEFT JOIN products p ON oi.product_id=p.id
        WHERE o.buyer_id=? GROUP BY o.id ORDER BY o.id DESC""", (session["user_id"],)).fetchall()
    db.close()
    tmpl = BASE + r"""
<div class="container orders-page">
  <div class="page-title">📦 Meus Pedidos</div>
  {% if orders %}
  {% for o in orders %}
  <div class="order-card">
    <div class="order-header">
      <span style="font-weight:700">Pedido #{{ o.id }}</span>
      <span class="badge badge-{{ 'green' if o.status=='Pago' else ('blue' if o.status=='Enviado' else 'yellow') }}">{{ o.status }}</span>
    </div>
    <div style="font-size:.82rem;color:#777;margin-bottom:.5rem">{{ o.titles or '—' }}</div>
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.4rem">
      <div style="font-size:.75rem;color:#aaa">
        📅 {{ o.created_at[:16] }} · {{ o.payment_method or '—' }}
        {% if o.tracking_code %} · 📦 {{ o.tracking_code }}{% endif %}
      </div>
      <span style="font-weight:700">{{ fmt_brl(o.total) }}</span>
    </div>
  </div>
  {% endfor %}
  {% else %}
  <div style="text-align:center;padding:4rem;color:#999">
    <div style="font-size:3rem;margin-bottom:1rem">📭</div>
    <p>Nenhum pedido ainda.</p>
    <a href="/" style="color:#3483fa;font-size:.85rem">Explorar produtos</a>
  </div>
  {% endif %}
</div>

"""
    return render_template_string(tmpl, orders=orders)


# ══════════════════════════════════════════
#  AUTH
# ══════════════════════════════════════════
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        email=request.form["email"].strip().lower()
        db=get_db()
        user=db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        db.close()
        if user and check_password_hash(user["password"],request.form["password"]):
            session["user_id"]=user["id"]
            flash(f"Bem-vindo, {user['name'].split()[0]}! 👋","success")
            return redirect(url_for("index"))
        flash("E-mail ou senha incorretos.","danger")
    tmpl = BASE + r"""
<div class="auth-box">
  <h2>Entrar na sua conta</h2>
  <form method="post">
    <div class="form-group"><label>E-mail</label><input type="email" name="email" required placeholder="seu@email.com"></div>
    <div class="form-group"><label>Senha</label><input type="password" name="password" required placeholder="••••••••"></div>
    <button type="submit" class="btn-full btn-buy">Entrar</button>
  </form>
  <div class="auth-footer">Não tem conta? <a href="/cadastro">Cadastre-se grátis</a></div>
</div>

"""
    return render_template_string(tmpl)

@app.route("/cadastro", methods=["GET","POST"])
def cadastro():
    if request.method=="POST":
        name=request.form["name"].strip()
        email=request.form["email"].strip().lower()
        password=request.form["password"]
        is_seller=1 if request.form.get("is_seller") else 0
        if len(password)<6:
            flash("Senha deve ter pelo menos 6 caracteres.","danger")
            return redirect(url_for("cadastro"))
        db=get_db()
        try:
            db.execute("INSERT INTO users (name,email,password,is_seller) VALUES (?,?,?,?)",
                       (name,email,generate_password_hash(password),is_seller))
            db.commit()
            user=db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
            session["user_id"]=user["id"]
            flash("Conta criada! Bem-vindo! 🎉","success")
            return redirect(url_for("index"))
        except: flash("Este e-mail já está cadastrado.","danger")
        finally: db.close()
    tmpl = BASE + r"""
<div class="auth-box">
  <h2>Criar conta grátis</h2>
  <form method="post">
    <div class="form-group"><label>Nome completo</label><input name="name" required placeholder="Seu nome"></div>
    <div class="form-group"><label>E-mail</label><input type="email" name="email" required placeholder="seu@email.com"></div>
    <div class="form-group"><label>Senha</label><input type="password" name="password" required placeholder="Mínimo 6 caracteres"></div>
    <div class="form-group" style="display:flex;align-items:center;gap:.5rem">
      <input type="checkbox" name="is_seller" id="s" style="width:auto">
      <label for="s" style="margin:0;cursor:pointer;font-size:.85rem">Quero também vender produtos</label>
    </div>
    <button type="submit" class="btn-full btn-yellow">Criar conta</button>
  </form>
  <div class="auth-footer">Já tem conta? <a href="/login">Entrar</a></div>
</div>

"""
    return render_template_string(tmpl)

@app.route("/logout")
def logout():
    session.clear(); flash("Até logo! 👋","info"); return redirect(url_for("index"))


# ══════════════════════════════════════════
#  PAINEL DO VENDEDOR
# ══════════════════════════════════════════
@app.route("/painel")
@seller_required
def painel():
    db=get_db(); uid=session["user_id"]
    products=db.execute("SELECT * FROM products WHERE seller_id=? ORDER BY id DESC", (uid,)).fetchall()
    revenue=db.execute("""SELECT COALESCE(SUM(oi.price*oi.qty),0) as r FROM order_items oi
        JOIN products p ON oi.product_id=p.id WHERE p.seller_id=?""", (uid,)).fetchone()["r"]
    n_orders=db.execute("""SELECT COUNT(DISTINCT oi.order_id) as n FROM order_items oi
        JOIN products p ON oi.product_id=p.id WHERE p.seller_id=?""", (uid,)).fetchone()["n"]
    db.close()
    tmpl = BASE + r"""
<div class="container">
  <div class="page-title">📦 Painel do Vendedor</div>
  <div class="stats-grid">
    <div class="stat-card"><div class="stat-num">{{ products|length }}</div><div class="stat-label">Produtos</div></div>
    <div class="stat-card"><div class="stat-num">{{ n_orders }}</div><div class="stat-label">Pedidos recebidos</div></div>
    <div class="stat-card"><div class="stat-num">{{ fmt_brl(revenue) }}</div><div class="stat-label">Receita total</div></div>
    <div class="stat-card"><div class="stat-num">{{ products|sum(attribute='stock') }}</div><div class="stat-label">Em estoque</div></div>
  </div>
  <div class="panel-grid">
    <div class="panel-menu">
      <a href="/painel" class="active">📋 Meus Produtos</a>
      <a href="/painel/novo">➕ Novo Anúncio</a>
      <a href="/pedidos">📦 Pedidos</a>
      <a href="/frete">🚚 Calcular frete</a>
      <a href="/">🏪 Ver loja</a>
    </div>
    <div class="panel-content">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">
        <h3>Meus Anúncios</h3>
        <a href="/painel/novo"><button class="nav-btn btn-primary">+ Novo</button></a>
      </div>
      <table class="table">
        <thead><tr><th>Produto</th><th>Preço</th><th>Estoque</th><th>Categoria</th><th>Status</th><th>Ações</th></tr></thead>
        <tbody>
          {% for p in products %}
          <tr>
            <td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ p.title }}</td>
            <td>{{ fmt_brl(p.price) }}</td>
            <td><span class="badge {{ 'badge-green' if p.stock>5 else ('badge-yellow' if p.stock>0 else 'badge-red') }}">{{ p.stock }}</span></td>
            <td>{{ p.category }}</td>
            <td><span class="badge {{ 'badge-green' if p.active else 'badge-gray' }}">{{ 'Ativo' if p.active else 'Inativo' }}</span></td>
            <td style="white-space:nowrap">
              <a href="/painel/editar/{{ p.id }}"><button class="nav-btn btn-ghost" style="font-size:.72rem;padding:.25rem .5rem">✏️</button></a>
              <form action="/painel/deletar/{{ p.id }}" method="post" style="display:inline" onsubmit="return confirm('Excluir?')">
                <button class="nav-btn" style="font-size:.72rem;padding:.25rem .5rem;color:#e63946;background:none;border:none;cursor:pointer">🗑️</button>
              </form>
            </td>
          </tr>
          {% else %}
          <tr><td colspan="6" style="text-align:center;color:#999;padding:2rem">Nenhum produto ainda.</td></tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
</div>

"""
    return render_template_string(tmpl, products=products, revenue=revenue, n_orders=n_orders)


def product_form_html(title, p, action):
    cats = ['Geral','Eletrônicos','Informática','Calçados','Bolsas','Fotografia','Livros & E-readers','Moda','Casa & Jardim','Esportes']
    return f"""
<div class="container" style="max-width:680px">
  <div class="page-title">{title}</div>
  <div class="panel-content">
    <form method="post" action="{action}">
      <div class="form-group"><label>Título *</label><input name="title" required value="{p.get('title','')}"></div>
      <div class="form-group"><label>Descrição</label><textarea name="description">{p.get('description','')}</textarea></div>
      <div class="form-row">
        <div class="form-group"><label>Preço (R$) *</label><input name="price" type="number" step="0.01" min="0" required value="{p.get('price','')}"></div>
        <div class="form-group"><label>Preço original (riscado)</label><input name="original_price" type="number" step="0.01" min="0" value="{p.get('original_price','')}"></div>
      </div>
      <div class="form-row">
        <div class="form-group"><label>Estoque *</label><input name="stock" type="number" min="0" required value="{p.get('stock',1)}"></div>
        <div class="form-group"><label>Peso (kg)</label><input name="weight_kg" type="number" step="0.01" min="0.01" value="{p.get('weight_kg',0.5)}"></div>
      </div>
      <div class="form-row">
        <div class="form-group"><label>Condição</label><select name="condition">
          {"".join(f"<option {'selected' if p.get('condition')==c else ''}>{c}</option>" for c in ['Novo','Usado','Recondicionado'])}
        </select></div>
        <div class="form-group"><label>Categoria</label><select name="category">
          {"".join(f"<option {'selected' if p.get('category')==c else ''}>{c}</option>" for c in cats)}
        </select></div>
      </div>
      <div class="form-group"><label>URL da imagem</label><input name="image_url" placeholder="https://..." value="{p.get('image_url','')}"></div>
      <div class="form-group" style="display:flex;align-items:center;gap:.5rem">
        <input type="checkbox" name="active" id="active" value="1" style="width:auto" {"checked" if p.get('active',1) else ""}>
        <label for="active" style="margin:0;cursor:pointer;font-size:.85rem">Produto ativo (visível na loja)</label>
      </div>
      <div style="display:flex;gap:.8rem;margin-top:.5rem">
        <button type="submit" class="btn-full btn-buy">{title}</button>
        <a href="/painel"><button type="button" class="btn-full btn-cart">Cancelar</button></a>
      </div>
    </form>
  </div>
</div>
"""

@app.route("/painel/novo", methods=["GET","POST"])
@seller_required
def painel_novo():
    if request.method=="POST":
        db=get_db()
        db.execute("""INSERT INTO products (seller_id,title,description,price,original_price,stock,category,image_url,condition,weight_kg,active)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (
            session["user_id"],request.form["title"],request.form.get("description",""),
            float(request.form["price"]),
            float(request.form["original_price"]) if request.form.get("original_price") else None,
            int(request.form.get("stock",1)),request.form.get("category","Geral"),
            request.form.get("image_url",""),request.form.get("condition","Novo"),
            float(request.form.get("weight_kg",0.5)),1 if request.form.get("active") else 0,
        ))
        db.commit(); db.close()
        flash("Produto anunciado! 🎉","success")
        return redirect(url_for("painel"))
    return render_template_string(BASE + product_form_html("Novo Anúncio", {}, "/painel/novo"))

@app.route("/painel/editar/<int:pid>", methods=["GET","POST"])
@seller_required
def painel_editar(pid):
    db=get_db()
    p=db.execute("SELECT * FROM products WHERE id=? AND seller_id=?", (pid,session["user_id"])).fetchone()
    if not p: db.close(); flash("Produto não encontrado.","danger"); return redirect(url_for("painel"))
    if request.method=="POST":
        db.execute("""UPDATE products SET title=?,description=?,price=?,original_price=?,stock=?,
            category=?,image_url=?,condition=?,weight_kg=?,active=? WHERE id=?""", (
            request.form["title"],request.form.get("description",""),
            float(request.form["price"]),
            float(request.form["original_price"]) if request.form.get("original_price") else None,
            int(request.form.get("stock",1)),request.form.get("category","Geral"),
            request.form.get("image_url",""),request.form.get("condition","Novo"),
            float(request.form.get("weight_kg",0.5)),1 if request.form.get("active") else 0,pid,
        ))
        db.commit(); db.close()
        flash("Produto atualizado! ✅","success")
        return redirect(url_for("painel"))
    pd=dict(p); db.close()
    return render_template_string(BASE + product_form_html("Editar Produto", pd, f"/painel/editar/{pid}"))

@app.route("/painel/deletar/<int:pid>", methods=["POST"])
@seller_required
def painel_deletar(pid):
    db=get_db()
    db.execute("DELETE FROM products WHERE id=? AND seller_id=?", (pid,session["user_id"]))
    db.commit(); db.close()
    flash("Produto removido.","info")
    return redirect(url_for("painel"))


# ══════════════════════════════════════════
#  PAINEL ADMIN
# ══════════════════════════════════════════
def admin_menu(active=""):
    links = [
        ("📊 Dashboard","/admin","dashboard"),
        ("👥 Usuários","/admin/usuarios","usuarios"),
        ("📦 Produtos","/admin/produtos","produtos"),
        ("🛒 Pedidos","/admin/pedidos","pedidos"),
    ]
    html = '<div class="panel-menu"><div class="menu-section">Administração</div>'
    for label,href,key in links:
        html += f'<a href="{href}" class="{"active" if active==key else ""}">{label}</a>'
    html += '<div class="menu-section" style="margin-top:1rem">Rápido</div>'
    html += '<a href="/frete">🚚 Calculadora Frete</a><a href="/">🏪 Ver loja</a></div>'
    return html

@app.route("/admin")
@admin_required
def admin_dashboard():
    db=get_db()
    n_users=db.execute("SELECT COUNT(*) as n FROM users").fetchone()["n"]
    n_products=db.execute("SELECT COUNT(*) as n FROM products WHERE active=1").fetchone()["n"]
    n_orders=db.execute("SELECT COUNT(*) as n FROM orders").fetchone()["n"]
    revenue=db.execute("SELECT COALESCE(SUM(total),0) as r FROM orders WHERE status='Pago'").fetchone()["r"]
    recent_orders=db.execute("""SELECT o.*,u.name as buyer_name FROM orders o
        JOIN users u ON o.buyer_id=u.id ORDER BY o.id DESC LIMIT 8""").fetchall()
    top_products=db.execute("""SELECT p.title,SUM(oi.qty) as sold,SUM(oi.price*oi.qty) as revenue
        FROM order_items oi JOIN products p ON oi.product_id=p.id
        GROUP BY p.id ORDER BY sold DESC LIMIT 5""").fetchall()
    db.close()
    tmpl = BASE + r"""
<div class="container">
  <div class="page-title">⚙️ Painel Administrativo</div>
  <div class="stats-grid">
    <div class="stat-card"><div class="stat-num">{{ n_users }}</div><div class="stat-label">Usuários cadastrados</div></div>
    <div class="stat-card"><div class="stat-num">{{ n_products }}</div><div class="stat-label">Produtos ativos</div></div>
    <div class="stat-card"><div class="stat-num">{{ n_orders }}</div><div class="stat-label">Total de pedidos</div></div>
    <div class="stat-card"><div class="stat-num">{{ fmt_brl(revenue) }}</div><div class="stat-label">Receita confirmada</div></div>
  </div>
  <div class="panel-grid">
    {{ menu|safe }}
    <div>
      <div class="panel-content" style="margin-bottom:1rem">
        <h3 style="margin-bottom:1rem">📈 Produtos mais vendidos</h3>
        <table class="table">
          <thead><tr><th>Produto</th><th>Vendidos</th><th>Receita</th></tr></thead>
          <tbody>
            {% for p in top_products %}
            <tr><td>{{ p.title[:45] }}</td><td>{{ p.sold }}</td><td>{{ fmt_brl(p.revenue) }}</td></tr>
            {% else %}
            <tr><td colspan="3" style="text-align:center;color:#999;padding:1rem">Nenhuma venda ainda.</td></tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
      <div class="panel-content">
        <h3 style="margin-bottom:1rem">🛒 Pedidos recentes</h3>
        <table class="table">
          <thead><tr><th>#</th><th>Comprador</th><th>Total</th><th>Pagamento</th><th>Status</th><th>Data</th></tr></thead>
          <tbody>
            {% for o in recent_orders %}
            <tr>
              <td>{{ o.id }}</td>
              <td>{{ o.buyer_name }}</td>
              <td>{{ fmt_brl(o.total) }}</td>
              <td><span style="font-size:.75rem">{{ o.payment_method or '—' }}</span></td>
              <td><span class="badge badge-{{ 'green' if o.status=='Pago' else ('blue' if o.status=='Enviado' else 'yellow') }}">{{ o.status }}</span></td>
              <td style="font-size:.75rem;color:#aaa">{{ o.created_at[:16] }}</td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </div>
</div>

"""
    return render_template_string(tmpl, n_users=n_users, n_products=n_products,
                                  n_orders=n_orders, revenue=revenue,
                                  recent_orders=recent_orders, top_products=top_products,
                                  menu=admin_menu("dashboard"))


@app.route("/admin/usuarios")
@admin_required
def admin_usuarios():
    db=get_db()
    users=db.execute("SELECT * FROM users ORDER BY id DESC").fetchall()
    db.close()
    tmpl = BASE + r"""
<div class="container">
  <div class="page-title">👥 Gerenciar Usuários</div>
  <div class="panel-grid">
    {{ menu|safe }}
    <div class="panel-content">
      <table class="table">
        <thead><tr><th>#</th><th>Nome</th><th>E-mail</th><th>Tipo</th><th>Desde</th><th>Ações</th></tr></thead>
        <tbody>
          {% for u in users %}
          <tr>
            <td>{{ u.id }}</td>
            <td>{{ u.name }}</td>
            <td style="font-size:.8rem">{{ u.email }}</td>
            <td>
              {% if u.is_admin %}<span class="badge badge-red">Admin</span>{% endif %}
              {% if u.is_seller %}<span class="badge badge-blue">Vendedor</span>{% endif %}
              {% if not u.is_admin and not u.is_seller %}<span class="badge badge-gray">Comprador</span>{% endif %}
            </td>
            <td style="font-size:.75rem;color:#aaa">{{ u.created_at[:10] }}</td>
            <td style="white-space:nowrap">
              <form action="/admin/usuarios/{{ u.id }}/toggle-seller" method="post" style="display:inline">
                <button class="nav-btn btn-ghost" style="font-size:.72rem;padding:.25rem .5rem" title="{{ 'Remover vendedor' if u.is_seller else 'Tornar vendedor' }}">
                  {{ '🔴 Vendedor' if u.is_seller else '🟢 Seller' }}
                </button>
              </form>
              {% if not u.is_admin %}
              <form action="/admin/usuarios/{{ u.id }}/toggle-admin" method="post" style="display:inline">
                <button class="nav-btn btn-ghost" style="font-size:.72rem;padding:.25rem .5rem">⚙️ Admin</button>
              </form>
              {% endif %}
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
</div>

"""
    return render_template_string(tmpl, users=users, menu=admin_menu("usuarios"))


@app.route("/admin/usuarios/<int:uid>/toggle-seller", methods=["POST"])
@admin_required
def admin_toggle_seller(uid):
    db=get_db()
    u=db.execute("SELECT is_seller FROM users WHERE id=?", (uid,)).fetchone()
    if u:
        db.execute("UPDATE users SET is_seller=? WHERE id=?", (0 if u["is_seller"] else 1, uid))
        db.commit()
    db.close()
    flash("Permissão atualizada.","success")
    return redirect(url_for("admin_usuarios"))

@app.route("/admin/usuarios/<int:uid>/toggle-admin", methods=["POST"])
@admin_required
def admin_toggle_admin(uid):
    db=get_db()
    u=db.execute("SELECT is_admin FROM users WHERE id=?", (uid,)).fetchone()
    if u:
        db.execute("UPDATE users SET is_admin=? WHERE id=?", (0 if u["is_admin"] else 1, uid))
        db.commit()
    db.close()
    flash("Permissão de admin atualizada.","success")
    return redirect(url_for("admin_usuarios"))


@app.route("/admin/produtos")
@admin_required
def admin_produtos():
    db=get_db()
    products=db.execute("""SELECT p.*,u.name as seller_name FROM products p
        JOIN users u ON p.seller_id=u.id ORDER BY p.id DESC""").fetchall()
    db.close()
    tmpl = BASE + r"""
<div class="container">
  <div class="page-title">📦 Gerenciar Produtos</div>
  <div class="panel-grid">
    {{ menu|safe }}
    <div class="panel-content">
      <table class="table">
        <thead><tr><th>#</th><th>Produto</th><th>Vendedor</th><th>Preço</th><th>Estoque</th><th>Status</th><th>Ações</th></tr></thead>
        <tbody>
          {% for p in products %}
          <tr>
            <td>{{ p.id }}</td>
            <td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ p.title }}</td>
            <td style="font-size:.8rem">{{ p.seller_name }}</td>
            <td>{{ fmt_brl(p.price) }}</td>
            <td><span class="badge {{ 'badge-green' if p.stock>5 else ('badge-yellow' if p.stock>0 else 'badge-red') }}">{{ p.stock }}</span></td>
            <td><span class="badge {{ 'badge-green' if p.active else 'badge-gray' }}">{{ 'Ativo' if p.active else 'Inativo' }}</span></td>
            <td style="white-space:nowrap">
              <form action="/admin/produtos/{{ p.id }}/toggle" method="post" style="display:inline">
                <button class="nav-btn btn-ghost" style="font-size:.72rem;padding:.25rem .5rem">{{ '🔴 Desativar' if p.active else '🟢 Ativar' }}</button>
              </form>
              <form action="/admin/produtos/{{ p.id }}/deletar" method="post" style="display:inline" onsubmit="return confirm('Excluir produto?')">
                <button class="btn-red" style="font-size:.72rem;padding:.25rem .5rem">🗑️</button>
              </form>
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
</div>

"""
    return render_template_string(tmpl, products=products, menu=admin_menu("produtos"))

@app.route("/admin/produtos/<int:pid>/toggle", methods=["POST"])
@admin_required
def admin_toggle_produto(pid):
    db=get_db()
    p=db.execute("SELECT active FROM products WHERE id=?", (pid,)).fetchone()
    if p:
        db.execute("UPDATE products SET active=? WHERE id=?", (0 if p["active"] else 1, pid))
        db.commit()
    db.close()
    flash("Status do produto atualizado.","success")
    return redirect(url_for("admin_produtos"))

@app.route("/admin/produtos/<int:pid>/deletar", methods=["POST"])
@admin_required
def admin_deletar_produto(pid):
    db=get_db()
    db.execute("DELETE FROM products WHERE id=?", (pid,))
    db.commit(); db.close()
    flash("Produto removido.","info")
    return redirect(url_for("admin_produtos"))


@app.route("/admin/pedidos")
@admin_required
def admin_pedidos():
    db=get_db()
    orders=db.execute("""SELECT o.*,u.name as buyer_name FROM orders o
        JOIN users u ON o.buyer_id=u.id ORDER BY o.id DESC""").fetchall()
    db.close()
    status_options = ["Aguardando pagamento","Pago","Em separação","Enviado","Entregue","Cancelado"]
    tmpl = BASE + r"""
<div class="container">
  <div class="page-title">🛒 Gerenciar Pedidos</div>
  <div class="panel-grid">
    {{ menu|safe }}
    <div class="panel-content">
      <table class="table">
        <thead><tr><th>#</th><th>Comprador</th><th>Total</th><th>Frete</th><th>Pagamento</th><th>Status</th><th>Rastreio</th><th>Ações</th></tr></thead>
        <tbody>
          {% for o in orders %}
          <tr>
            <td>{{ o.id }}</td>
            <td style="font-size:.82rem">{{ o.buyer_name }}</td>
            <td>{{ fmt_brl(o.total) }}</td>
            <td style="font-size:.78rem">{{ 'Grátis' if o.freight==0 else fmt_brl(o.freight) }}</td>
            <td style="font-size:.75rem">{{ o.payment_method or '—' }}</td>
            <td>
              <form action="/admin/pedidos/{{ o.id }}/status" method="post" style="display:flex;gap:.3rem">
                <select name="status" style="padding:.2rem .4rem;font-size:.75rem;border:1px solid #ddd;border-radius:4px">
                  {% for s in status_opts %}
                  <option {{ 'selected' if o.status==s else '' }}>{{ s }}</option>
                  {% endfor %}
                </select>
                <button type="submit" style="padding:.2rem .5rem;background:#3483fa;color:#fff;border:none;border-radius:4px;font-size:.72rem;cursor:pointer">OK</button>
              </form>
            </td>
            <td style="font-size:.72rem;font-family:monospace">{{ o.tracking_code or '—' }}</td>
            <td style="font-size:.72rem;color:#aaa">{{ o.created_at[:10] }}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
</div>

"""
    return render_template_string(tmpl, orders=orders, menu=admin_menu("pedidos"), status_opts=status_options)

@app.route("/admin/pedidos/<int:oid>/status", methods=["POST"])
@admin_required
def admin_update_status(oid):
    new_status = request.form.get("status","Pago")
    db=get_db()
    db.execute("UPDATE orders SET status=? WHERE id=?", (new_status,oid))
    db.commit(); db.close()
    flash(f"Pedido #{oid} atualizado para '{new_status}'.","success")
    return redirect(url_for("admin_pedidos"))


# ══════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════
if __name__=="__main__":
    init_db()
    print("\n" + "="*56)
    print("  🛍️  M DE MARIA — rodando!")
    print("  👉  Acesse: http://localhost:5000")
    print()
    print("  👤 Admin:  admin@mercado.com / admin123")
    print()
    print("  🆕 Novidades nesta versão:")
    print("     ✅ Filtro de preço, ordem, condição")
    print("     ✅ Pagamento: PIX, Boleto, Cartão")
    print("     ✅ Calculadora de frete por CEP")
    print("     ✅ Painel Admin (usuários, produtos, pedidos)")
    print("     ✅ Página dedicada de frete com tabela por UF")
    print("="*56 + "\n")
    app.run(debug=True, port=5000)
