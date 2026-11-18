#!/usr/bin/env python3
"""Perihan Baktaş art gallery site (Python standard library only)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import mimetypes
import os
import re
import secrets
import sqlite3
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlencode, urlparse

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    SITE_TIMEZONE = ZoneInfo(os.environ.get("GALLERY_TIMEZONE", "Europe/Istanbul"))
except (ImportError, ZoneInfoNotFoundError):
    # Turkey has observed UTC+03:00 year-round since 2016. Keep scheduling
    # correct on Windows builds that do not have the IANA timezone database.
    SITE_TIMEZONE = timezone(timedelta(hours=3), "Europe/Istanbul")


def site_now():
    return datetime.now(SITE_TIMEZONE)


def site_now_string():
    return site_now().strftime("%Y-%m-%dT%H:%M")

ROOT = Path(__file__).resolve().parent
DATA_ROOT = Path(os.environ.get("GALLERY_DATA_DIR", str(ROOT))).expanduser()
DB_PATH = DATA_ROOT / "data" / "site.sqlite3"
UPLOADS = DATA_ROOT / "uploads"
MAX_FILE = 8 * 1024 * 1024
MAX_REQUEST = MAX_FILE + 256 * 1024
ALLOWED_EXT = {".jpg", ".jpeg", ".jfif", ".png", ".webp"}
LEGACY_SAMPLE_WORKS = [
    ("TBL-001", "Baharın Şarkısı", "50x70 cm", 3200, 2500, "Çiçekler", "Pembe çiçekler ve yumuşak bahar tonları."),
    ("TBL-002", "Ayçiçekleri", "60x80 cm", 4000, 3200, "Çiçekler", "Sıcak sarı tonlarda ayçiçeği kompozisyonu."),
    ("TBL-003", "Sakin Kıyı", "70x90 cm", 5000, 4000, "Manzaralar", "Mavi ve kum tonlarında dingin bir kıyı."),
    ("TBL-004", "Kiraz Çiçekleri", "50x70 cm", 4500, 3500, "Çiçekler", "Bahar dallarından ilham alan özgün eser."),
    ("TBL-005", "Pembe Huzur", "40x60 cm", 3600, 2800, "Yumuşak Tonlar", "Lavanta ve pembe tonların huzurlu buluşması."),
    ("TBL-006", "Lavanta Tarlası", "50x70 cm", 3600, 3000, "Manzaralar", "Lavanta renklerinde sakin bir kır manzarası."),
    ("TBL-007", "Güneşli Sabah", "60x80 cm", 4500, 3800, "Manzaralar", "Güne yeni başlayan bir bahar manzarası."),
    ("TBL-008", "Gül Bahçesi", "40x50 cm", 2900, 2400, "Çiçekler", "Yumuşak pembe ve yeşil tonlarda güller."),
    ("TBL-009", "Kır Çiçekleri", "50x70 cm", 3100, 2700, "Çiçekler", "Renkli kır çiçeklerinden oluşan özgün çalışma."),
    ("TBL-010", "Bahar Dalı", "60x80 cm", 4600, 3900, "Çiçekler", "Çiçek açan dalların hareketli yorumu."),
    ("TBL-011", "Papatya Tarlası", "40x50 cm", 2600, 2200, "Çiçekler", "Açık tonlarda sade papatya kompozisyonu."),
    ("TBL-012", "Sabah Sisi", "70x90 cm", 5200, 4500, "Manzaralar", "Sakin bir sabahın yumuşak renkleri."),
    ("TBL-013", "Menekşe Bahçesi", "50x70 cm", 3700, 3100, "Çiçekler", "Mor ve yeşil tonların dengeli yorumu."),
    ("TBL-014", "Altın Ufuk", "60x80 cm", 4200, 3600, "Manzaralar", "Ufukta altın ışıkları taşıyan manzara."),
    ("TBL-015", "Pembe Göl", "40x60 cm", 3400, 2900, "Yumuşak Tonlar", "Göl yansımalarından ilham alan yumuşak tonlar."),
    ("TBL-016", "Ağaçların Fısıltısı", "70x70 cm", 4900, 4200, "Manzaralar", "Ağaçların dinginliğini taşıyan özgün eser."),
    ("TBL-017", "Yasemin Esintisi", "50x50 cm", 3000, 2500, "Çiçekler", "Açık renklerde zarif yasemin dalları."),
    ("TBL-018", "Gelincik Kırı", "60x90 cm", 4400, 3700, "Manzaralar", "Kırmızı gelinciklerin canlı renkleri."),
    ("TBL-019", "Erguvan Akşam", "50x70 cm", 3200, 3200, "Yumuşak Tonlar", "Akşam ışığında erguvan ve pembe tonlar."),
    ("TBL-020", "Lavanta Rüyası", "40x60 cm", 2800, 2800, "Yumuşak Tonlar", "Lavanta tonlarında dingin bir düş."),
    ("TBL-021", "Sessiz Mavi", "60x80 cm", 3500, 3500, "Manzaralar", "Mavinin sessiz ve sakin tonları."),
    ("TBL-022", "Yasemin Rüzgârı", "50x70 cm", 3800, 3300, "Çiçekler", "Yasemin dallarından ilham alan çalışma."),
    ("TBL-023", "Çınar Gölgesi", "60x80 cm", 4700, 4100, "Manzaralar", "Gölge ve ışıkla şekillenen bir manzara."),
    ("TBL-024", "Mor Salkım", "40x60 cm", 3000, 2600, "Çiçekler", "Mor salkımların bahar renkleri."),
    ("TBL-025", "Kırlangıç Yolu", "70x90 cm", 5500, 4800, "Manzaralar", "Geniş ufuklu, bahardan esinlenen manzara."),
    ("TBL-026", "Güneş Tarlası", "50x70 cm", 3900, 3400, "Manzaralar", "Güneş ışığını taşıyan sıcak renkler."),
    ("TBL-027", "Sessiz Limon", "40x50 cm", 2700, 2300, "Yumuşak Tonlar", "Sarı ve yeşilin sade buluşması."),
]


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c


def init_db():
    with connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS admin (id INTEGER PRIMARY KEY CHECK(id=1), password_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS products (
          id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL, title TEXT NOT NULL,
          size TEXT NOT NULL DEFAULT '', price INTEGER NOT NULL DEFAULT 0, sale_price INTEGER,
          category TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '', image TEXT NOT NULL DEFAULT '',
          whatsapp_url TEXT NOT NULL DEFAULT '', featured INTEGER NOT NULL DEFAULT 0,
          sold INTEGER NOT NULL DEFAULT 0, archived INTEGER NOT NULL DEFAULT 0,
          show_new INTEGER NOT NULL DEFAULT 0, show_collections INTEGER NOT NULL DEFAULT 0,
          show_curated INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS product_likes (
          product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
          visitor_id TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY(product_id, visitor_id)
        );
        CREATE TABLE IF NOT EXISTS product_comments (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
          parent_id INTEGER REFERENCES product_comments(id) ON DELETE CASCADE,
          visitor_id TEXT NOT NULL DEFAULT '',
          first_name TEXT NOT NULL, last_name TEXT NOT NULL, body TEXT NOT NULL,
          avatar_path TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS site_visitors (
          visitor_id TEXT PRIMARY KEY,
          first_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          last_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS product_shares (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS product_comments_product_idx ON product_comments(product_id, id);
        CREATE INDEX IF NOT EXISTS product_shares_product_idx ON product_shares(product_id, id);
        """)
        product_columns = {row[1] for row in c.execute("PRAGMA table_info(products)")}
        if "inspect_title" not in product_columns:
            c.execute("ALTER TABLE products ADD COLUMN inspect_title TEXT NOT NULL DEFAULT ''")
        if "article" not in product_columns:
            c.execute("ALTER TABLE products ADD COLUMN article TEXT NOT NULL DEFAULT ''")
        if "publish_at" not in product_columns:
            c.execute("ALTER TABLE products ADD COLUMN publish_at TEXT NOT NULL DEFAULT ''")
        if "show_new" not in product_columns:
            c.execute("ALTER TABLE products ADD COLUMN show_new INTEGER NOT NULL DEFAULT 0")
            c.execute("ALTER TABLE products ADD COLUMN show_collections INTEGER NOT NULL DEFAULT 0")
            c.execute("ALTER TABLE products ADD COLUMN show_curated INTEGER NOT NULL DEFAULT 0")
            c.execute("UPDATE products SET show_curated=featured")
            latest = c.execute("SELECT id FROM products WHERE archived=0 AND sold=0 ORDER BY id DESC LIMIT 4").fetchall()
            c.executemany("UPDATE products SET show_new=1 WHERE id=?", [(row[0],) for row in latest])
        defaults = {
            "site_name": "Perihan Baktaş", "whatsapp_url": "", "instagram_url": "",
            "tiktok_url": "", "telegram_url": "", "question_message": "Merhaba, {code} kodlu tablonuz hakkında soru sormak istiyorum.", "categories": "Çiçekler, Manzaralar, Yumuşak Tonlar",
            "stat_visitors_offset": "0", "stat_sold_offset": "0", "stat_available_offset": "0",
            "about_heading": "Sanatla İç İçe Bir Yaşam",
            "about_text": "Sanat benim için yalnızca renkleri yan yana getirmek değil; duyguları, anıları ve doğadan aldığım ilhamı tuvale taşımak. Her eserimi atölyemde, renklerin ve mevsimlerin bende uyandırdığı hislerle, sabırla ve özenle hazırlıyorum.\n\nÇiçeklerden, bahar ışığından ve günlük hayatın küçük güzelliklerinden ilham alıyorum. Eserlerimin evlerinize huzur ve kendine ait bir hikâye taşımasını diliyorum.",
            "session_secret": secrets.token_hex(32),
        }
        for k, v in defaults.items():
            c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k, v))
        if not c.execute("SELECT 1 FROM settings WHERE key='legacy_sample_cleanup_v1'").fetchone():
            for item in LEGACY_SAMPLE_WORKS:
                code, title, size, price, sale, category, desc = item
                c.execute("DELETE FROM products WHERE code=? AND title=? AND size=? AND price=? AND sale_price IS ? AND category=? AND description=? AND COALESCE(image,'')=''",
                          (code, title, size, price, sale if sale < price else None, category, desc))
            c.execute("INSERT INTO settings(key,value) VALUES('legacy_sample_cleanup_v1','1')")
        if not c.execute("SELECT 1 FROM settings WHERE key='product_sections_v2'").fetchone():
            c.execute("UPDATE products SET show_curated=0")
            c.execute("UPDATE products SET show_curated=1 WHERE id IN (SELECT id FROM products WHERE featured=1 AND sold=0 AND archived=0 ORDER BY id DESC LIMIT 3)")
            c.execute("INSERT INTO settings(key,value) VALUES('product_sections_v2','1')")


def settings():
    with connect() as c:
        return {r["key"]: r["value"] for r in c.execute("SELECT key,value FROM settings")}


def actual_site_stats():
    now = site_now_string()
    with connect() as c:
        return {
            "visitors": c.execute("SELECT COUNT(*) FROM site_visitors").fetchone()[0],
            "sold": c.execute("SELECT COUNT(*) FROM products WHERE sold=1").fetchone()[0],
            "available": c.execute("SELECT COUNT(*) FROM products WHERE archived=0 AND sold=0 AND (publish_at='' OR publish_at<=?)", (now,)).fetchone()[0],
        }


def display_site_stats(cfg=None, actual=None):
    cfg = cfg if cfg is not None else settings()
    actual = actual if actual is not None else actual_site_stats()
    result = {}
    for name in ("visitors", "sold", "available"):
        try:
            offset = int(cfg.get("stat_" + name + "_offset", 0))
        except (TypeError, ValueError):
            offset = 0
        result[name] = max(0, int(actual.get(name, 0)) + offset)
    return result


def esc(s):
    return html.escape(str(s or ""), quote=True)


def money(n):
    return f"₺{int(n or 0):,}".replace(",", ".")


def product_sections(product):
    choices = (("show_new", "Yeni Gelenler"), ("show_curated", "Sanatçının Seçkisi"))
    return " · ".join(label for key, label in choices if product[key]) or "Seçilmedi"


def admin_product_row(product, csrf, likes, comments, shares=0, archived=False):
    code = product["code"]
    product_id = product["id"]
    code_cell = f"<code>{esc(code)}</code> <button type='button' class='copy-code' data-copy='{esc(code)}' title='Eser kodunu kopyala' aria-label='Eser kodunu kopyala'>Kopyala</button>"
    if archived:
        state = "Arşivde"
        actions = f"<a href='/atolye-yonetim-8f31/products/{product_id}'>Düzenle</a> · <form class='inline-form' method='post' action='/atolye-yonetim-8f31/products/{product_id}/unarchive'><input type='hidden' name='csrf' value='{csrf}'><button class='text-button'>Arşivden Çıkar</button></form>"
    else:
        state = "Taslak" if product["publish_at"] and product["publish_at"] > site_now_string() else ("Satıldı" if product["sold"] else "Yayında")
        sold_button = "Satışa Aç" if product["sold"] else "Satıldı Olarak İşaretle"
        actions = f"<a href='/atolye-yonetim-8f31/products/{product_id}'>Düzenle</a> · <form class='inline-form' method='post' action='/atolye-yonetim-8f31/products/{product_id}/sold'><input type='hidden' name='csrf' value='{csrf}'><button class='text-button'>{sold_button}</button></form> · <form class='inline-form' method='post' action='/atolye-yonetim-8f31/products/{product_id}/archive'><input type='hidden' name='csrf' value='{csrf}'><button class='text-button'>Arşivle</button></form>"
    actions += f" · <form class='inline-form' method='post' action='/atolye-yonetim-8f31/products/{product_id}/delete' onsubmit='return confirm(&quot;Eser kalıcı olarak silinecek; görseli, beğeni kayıtları ve yorumları da kaldırılacak. Bu işlem geri alınamaz.&quot;)'><input type='hidden' name='csrf' value='{csrf}'><button class='text-button delete-button'>Sil</button></form>"
    status = f"{state}{(' · '+esc(product['publish_at'])) if product['publish_at'] else ''}"
    return f"<tr><td>{code_cell}</td><td>{esc(product['title'])}</td><td>{esc(product['size'])}</td><td>{money(product['sale_price'] or product['price'])}</td><td>{likes} ♥</td><td>{comments} 💬</td><td>{shares} ↗</td><td>{esc(product_sections(product))}</td><td>{status}</td><td>{actions}</td></tr>"


def safe_url(value):
    v = (value or "").strip()
    return v if v.startswith(("https://", "http://")) else ""


def parse_whatsapp_accounts(value):
    try:
        raw_accounts = json.loads(value or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(raw_accounts, list):
        return []
    accounts = []
    for item in raw_accounts[:20]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()[:60]
        url = safe_url(str(item.get("url", "")).strip()[:500])
        if name and url:
            accounts.append({"name": name, "url": url})
    return accounts


def render(title, content, message=""):
    cfg = settings()
    nav = """<a href='/'>Ana Sayfa</a><a href='/#eserler'>Eserler</a><a href='/arsiv'>Arşiv</a>"""
    alert = f"<div class='notice'>{esc(message)}</div>" if message else ""
    socials = "".join(f"<a target='_blank' rel='noopener' href='{esc(safe_url(cfg.get(k)))}'>{label}</a>" for k, label in (("instagram_url", "Instagram"), ("tiktok_url", "TikTok"), ("telegram_url", "Telegram")) if safe_url(cfg.get(k)))
    return f"""<!doctype html><html lang='tr'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><meta name='description' content='Perihan Baktaş el yapımı sanat eserleri.'><title>{esc(title)} · {esc(cfg.get('site_name'))}</title><link rel='stylesheet' href='/static/style.css'></head><body>
    <header class='site-head'><a class='brand' href='/'><span class='brand-mark'>✿</span><span><b>Sanat Atölyesi</b><small>EL YAPIMI TABLOLAR · {esc(cfg.get('site_name'))}</small></span></a><nav>{nav}</nav></header>
    {alert}<main>{content}</main><footer><div><b>{esc(cfg.get('site_name'))}</b><p>Bahar sizinle eve gelsin.</p></div><div class='socials'>{socials}</div></footer><script src='/static/app.js' defer></script><script src='/static/comments.js' defer></script></body></html>"""


def artwork(product):
    image = f"<img src='/{esc(product['image'])}' alt='{esc(product['title'])}'>" if product["image"] else f"<div class='art-placeholder art-{int(product['id']) % 5}' aria-hidden='true'><i>✿</i><i>✿</i><i>✿</i><i>✿</i></div>"
    old = f"<del>{money(product['price'])}</del>" if product["sale_price"] and product["sale_price"] < product["price"] else ""
    price = product["sale_price"] if product["sale_price"] and product["sale_price"] < product["price"] else product["price"]
    badge = "<span class='badge sold-badge'>Sahibini buldu</span>" if product["sold"] else ("<span class='badge'>Öne Çıkan</span>" if product["featured"] else "")
    buy_url = safe_url(product["whatsapp_url"]) or safe_url(settings().get("whatsapp_url"))
    buy = (f"<a class='button small' href='{esc(buy_url)}' target='_blank' rel='noopener'>Bilgi Al</a>" if buy_url and not product["sold"] else ("<span class='button small sold-button' aria-disabled='true'>Satıldı</span>" if product["sold"] else ""))
    like = f"<div class='like-row'><button type='button' class='like-button' data-like-code='{esc(product['code'])}' data-liked='0' aria-pressed='false' aria-label='0 beğeni'><svg viewBox='0 0 24 24' aria-hidden='true'><path d='M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8l1.1 1.1L12 21l7.8-7.5 1.1-1.1a5.5 5.5 0 0 0-.1-7.8Z'/></svg><span class='like-count'>0</span></button><button type='button' class='comment-button' data-comment-code='{esc(product['code'])}' aria-label='0 yorum'><svg viewBox='0 0 24 24' aria-hidden='true'><path d='M20 11.5a8.4 8.4 0 0 1-12.7 7.2L3 20l1.4-4.1A8.4 8.4 0 1 1 20 11.5Z'/><path d='M8 11h8M8 14h5'/></svg><span class='comment-count'>0</span></button></div>"
    return f"<article class='product-card'>{badge}<div class='art-frame' data-work-code='{esc(product['code'])}'><span class='work-code-badge'>{esc(product['code'])}</span>{image}</div><div class='product-info'><span class='product-code'>{esc(product['code'])}</span><h3>{esc(product['title'])}</h3><p>{esc(product['size'])}</p><p class='product-price'>{old}<b>{money(price)}</b></p><p class='description'>{esc(product['description'])}</p><div class='actions'>{buy}</div>{like}</div></article>"


def product_cards(rows):
    return "".join(artwork(row) for row in rows) or "<p class='empty'>Bu bölümde henüz eser yok.</p>"


def product_code_from_digits(digits, existing_code=""):
    digits = str(digits or "").strip()
    if not re.fullmatch(r"[0-9]{1,12}", digits):
        raise ValueError("Eser kodu için yalnızca 1–12 rakam girin.")
    prefix = "PB-"
    match = re.fullmatch(r"([A-Z]+-)[0-9]+", str(existing_code or "").upper())
    if match:
        prefix = match.group(1)
    return prefix + digits


def render_legacy_home():
    """Keep the supplied homepage and continuously bind its artwork to the admin catalog."""
    return """<!doctype html><html lang='tr'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Perihan Baktaş | Sanat Atölyesi</title><style>
    *{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;overflow:hidden}iframe{display:block;width:100%;height:100%;border:0;background:#f8eff1;opacity:0;transform:translateY(10px) scale(.995);transition:opacity .85s ease,transform .85s cubic-bezier(.22,.68,0,1)}iframe.is-visible{opacity:1;transform:translateY(0) scale(1)}.page-loader{position:fixed;inset:0;z-index:100;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:7px;background:radial-gradient(ellipse at 20% 22%,#f9e7ec 0,transparent 29%),radial-gradient(ellipse at 82% 76%,#e7eee9 0,transparent 28%),#f8eff1;color:#344b43;transform:scale(1);transition:opacity .75s ease,visibility .75s ease,transform .75s ease}.page-loader.is-hidden{opacity:0;visibility:hidden;pointer-events:none;transform:scale(1.015)}.loader-bloom{position:relative;width:72px;height:72px;margin-bottom:10px;color:#70449c;font:64px/1 Georgia,serif;animation:loader-bloom-turn 5s ease-in-out infinite}.loader-bloom:before{content:'✿';position:absolute;inset:0;display:grid;place-items:center;text-shadow:0 7px 18px rgba(75,40,112,.42)}.loader-bloom:after{content:'';position:absolute;width:9px;height:9px;left:32px;top:32px;border-radius:50%;background:#f3c966}.page-loader strong{font:600 23px/1.2 Georgia,serif;color:#3f5a46}.page-loader p{margin:0;color:#827783;font:13px/1.5 Arial,sans-serif}.loader-brush-line{width:160px;height:3px;margin-top:14px;border-radius:9px;background:#eadfd6;overflow:hidden}.loader-brush-line i{display:block;width:45%;height:100%;border-radius:9px;background:linear-gradient(90deg,#e9a2b9,#79546f,#e9a2b9);transform-origin:left;animation:loader-brush-sweep 1.6s ease-in-out infinite alternate}@keyframes loader-bloom-turn{0%,100%{transform:rotate(-8deg) scale(.94)}50%{transform:rotate(9deg) scale(1.04)}}@keyframes loader-brush-sweep{from{transform:translateX(-8%)}to{transform:translateX(135%)}}@media(prefers-reduced-motion:reduce){.loader-bloom,.loader-brush-line i{animation-duration:.01ms!important;animation-iteration-count:1!important}}
    </style></head><body><iframe id='legacy-home' src='/legacy-home-content' title='Perihan Baktaş sanat galerisi' allow='web-share; clipboard-write'></iframe><div class='page-loader' id='page-loader' role='status' aria-live='polite'><div class='loader-bloom' aria-hidden='true'></div><strong>Atölye hazırlanıyor</strong><p>Sanat eserleri yükleniyor…</p><span class='loader-brush-line' aria-hidden='true'><i></i></span></div><script>
    (function(){var frame=document.getElementById('legacy-home'),loader=document.getElementById('page-loader'),busy=false,lastSignature='',loaderStartedAt=Date.now(),pageRevealed=false,revealTimer=0;function revealPage(){if(pageRevealed)return;var remaining=3000-(Date.now()-loaderStartedAt);if(remaining>0){if(!revealTimer)revealTimer=window.setTimeout(function(){revealTimer=0;revealPage()},remaining);return}pageRevealed=true;if(frame)frame.classList.add('is-visible');if(loader){loader.classList.add('is-hidden');loader.setAttribute('aria-hidden','true')}}window.setTimeout(revealPage,15000);
    var likeVisitor=(function(){var key='perihan-gallery-visitor';try{var id=localStorage.getItem(key);if(!id){id=(window.crypto&&crypto.randomUUID)?crypto.randomUUID():'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g,function(c){var r=Math.random()*16|0;return(c==='x'?r:(r&3|8)).toString(16)});localStorage.setItem(key,id)}return id}catch(e){return 'session-'+Math.random().toString(16).slice(2)+Date.now().toString(16)}})();
    function setLikeState(d,code,value){window.__publicLikes=window.__publicLikes||{};window.__publicLikes[code]=value;Array.from(d.querySelectorAll('.like-button')).forEach(function(b){if(b.dataset.likeCode!==code)return;b.dataset.liked=value.liked?'1':'0';b.setAttribute('aria-pressed',value.liked?'true':'false');b.setAttribute('aria-label','Beğen, '+value.count+' beğeni'+(value.liked?', beğeniyi geri al':''));var n=b.querySelector('.like-count');if(n)n.textContent=value.count})}
    function setCommentCount(d,code,count){window.__publicCommentCounts=window.__publicCommentCounts||{};window.__publicCommentCounts[code]=Number(count||0);Array.from(d.querySelectorAll('.comment-button')).forEach(function(b){if(b.dataset.commentCode!==code)return;var n=b.querySelector('.comment-count');if(n)n.textContent=String(count||0);b.setAttribute('aria-label','Yorumları aç, '+String(count||0)+' yorum')})}
    function setShareCount(d,code,count){window.__publicShareCounts=window.__publicShareCounts||{};window.__publicShareCounts[code]=Number(count||0);Array.from(d.querySelectorAll('.share-button')).forEach(function(b){if(b.dataset.shareCode!==code)return;var n=b.querySelector('.share-count');if(n)n.textContent=String(count||0);b.setAttribute('aria-label','Eseri paylaş, '+String(count||0)+' paylaşım')})}
    function showShareFeedback(d,message){var toast=d.getElementById('gallery-share-feedback');if(!toast){toast=detailNode(d,'div','gallery-share-feedback');toast.id='gallery-share-feedback';toast.setAttribute('role','status');toast.setAttribute('aria-live','polite');d.body.appendChild(toast)}toast.textContent=message;toast.classList.add('is-visible');clearTimeout(toast.__hideTimer);toast.__hideTimer=setTimeout(function(){toast.classList.remove('is-visible')},2200)}
    function questionHref(d,p,cfg){var contact=p.whatsapp_url||cfg.whatsapp_url||'https://wa.me/',template=String(cfg.question_message||'Merhaba, {code} kodlu tablonuz hakkında soru sormak istiyorum.'),hasCode=/[{]code[}]/i.test(template),message=template.replace(/[{]code[}]/gi,p.code||'').replace(/[{]title[}]/gi,p.title||'');if(!hasCode)message=(message.trim()?message.trim()+' ':'')+(p.code||'');try{var url=new URL(contact,d.location.href);if(url.protocol!=='https:'&&url.protocol!=='http:')throw Error('invalid whatsapp url');url.searchParams.set('text',message);return url.href}catch(e){return 'https://wa.me/?text='+encodeURIComponent(message)}}
    function ensureLikeRow(d,card,p,cfg){var ct=card.querySelector('.ct');if(!ct)return;var code=p.code||'',row=ct.querySelector('.like-row');if(!row){row=d.createElement('div');row.className='like-row';var actions=ct.querySelector('.card-actions');if(actions)actions.insertAdjacentElement('afterend',row);else ct.appendChild(row)}var ask=row.querySelector('.question-button');if(!ask){ask=d.createElement('a');ask.className='question-button';ask.textContent='Soru Sor';row.insertBefore(ask,row.firstChild)}ask.href=questionHref(d,p,cfg);ask.target='_blank';ask.rel='noopener noreferrer';ask.setAttribute('aria-label',code+' kodlu eser hakkında WhatsApp üzerinden soru sor');var b=row.querySelector('.like-button');if(!b){row.insertAdjacentHTML('afterbegin','<button type="button" class="like-button" data-like-code="" data-liked="0" aria-pressed="false" aria-label="0 beğeni"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8l1.1 1.1L12 21l7.8-7.5 1.1-1.1a5.5 5.5 0 0 0-.1-7.8Z"/></svg><span class="like-count">0</span></button>');b=row.querySelector('.like-button')}var comment=row.querySelector('.comment-button');if(!comment){comment=d.createElement('button');comment.type='button';comment.className='comment-button';comment.setAttribute('aria-label','0 yorum');comment.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 11.5a8.4 8.4 0 0 1-12.7 7.2L3 20l1.4-4.1A8.4 8.4 0 1 1 20 11.5Z"/><path d="M8 11h8M8 14h5"/></svg><span class="comment-count">0</span>';row.appendChild(comment)}var share=row.querySelector('.share-button');if(!share){share=d.createElement('button');share.type='button';share.className='share-button';share.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="m8.7 10.7 6.6-4.4M8.7 13.3l6.6 4.4"/></svg><span class="share-count">0</span>';row.appendChild(share)}var social=row.querySelector('.like-actions');if(!social){social=d.createElement('span');social.className='like-actions';row.appendChild(social)}if(b.parentElement!==social)social.appendChild(b);if(comment.parentElement!==social)social.appendChild(comment);if(share.parentElement!==social)social.appendChild(share);b.dataset.likeCode=code;comment.dataset.commentCode=code;share.dataset.shareCode=code;var state=(window.__publicLikes||{})[code]||{count:0,liked:false};setLikeState(d,code,state);setCommentCount(d,code,(window.__publicCommentCounts||{})[code]||0);setShareCount(d,code,(window.__publicShareCounts||{})[code]===undefined?(p.share_count||0):(window.__publicShareCounts||{})[code])}
    function detailNode(d,tag,className,text){var node=d.createElement(tag);if(className)node.className=className;if(text!==undefined&&text!==null)node.textContent=text;return node}
    function openArtworkDetail(d,p,card,cfg,focusComments){
      var old=d.getElementById('art-detail-overlay');if(old)old.remove();
      var overlay=detailNode(d,'div','art-detail-overlay');overlay.id='art-detail-overlay';overlay.setAttribute('role','dialog');overlay.setAttribute('aria-modal','true');overlay.setAttribute('aria-label',p.title+' eser ayrıntıları');
      var panel=detailNode(d,'section','art-detail-panel');overlay.appendChild(panel);
      var art=detailNode(d,'div','art-detail-art');panel.appendChild(art);
      var imagePath=p.image||'';var source=imagePath?(imagePath.charAt(0)==='/'?imagePath:'/'+imagePath):'';var existing=card&&card.querySelector('.art img');if(!source&&existing)source=existing.getAttribute('src')||existing.src||'';
      if(source){var image=detailNode(d,'img');image.src=source;image.alt=p.title;image.decoding='async';art.appendChild(image)}else if(card&&card.querySelector('.art')){var artwork=card.querySelector('.art').cloneNode(true);var chip=artwork.querySelector('.chip');if(chip)chip.remove();art.appendChild(artwork)}
      var info=detailNode(d,'div','art-detail-info');panel.appendChild(info);
      var close=detailNode(d,'button','art-detail-close','×');close.type='button';close.setAttribute('aria-label','Eser ayrıntılarını kapat');panel.appendChild(close);
      info.appendChild(detailNode(d,'span','art-detail-kicker','ATÖLYEDEN BİR ESER'));
      info.appendChild(detailNode(d,'h2','',p.inspect_title||p.title));
      if(p.inspect_title&&p.inspect_title!==p.title)info.appendChild(detailNode(d,'p','art-detail-product-name',p.title));
      info.appendChild(detailNode(d,'p','art-detail-code',(p.code||'')));
      var facts=detailNode(d,'div','art-detail-facts');
      var size=detailNode(d,'div','',null);size.appendChild(detailNode(d,'span','', 'Ölçü'));size.appendChild(detailNode(d,'b','',p.size||'Bilgi için bize yazın'));facts.appendChild(size);
      var price=Number(p.sale_price&&Number(p.sale_price)<Number(p.price)?p.sale_price:p.price);var cost=detailNode(d,'div','',null);cost.appendChild(detailNode(d,'span','', 'Fiyat'));cost.appendChild(detailNode(d,'b','',fmt(price)));facts.appendChild(cost);info.appendChild(facts);
      info.appendChild(detailNode(d,'h3','art-detail-story-title','Eserin hikâyesi'));
      info.appendChild(detailNode(d,'p','art-detail-story',p.article||p.description||'Bu eser hakkında daha fazla bilgi almak için bize yazabilirsiniz.'));
      var question=detailNode(d,'div','art-detail-question');question.appendChild(detailNode(d,'b','', 'Bu tablo hakkında bir sorunuz mu var?'));question.appendChild(detailNode(d,'p','', 'Ölçü, renk ve sipariş ayrıntılarını atölyeye danışın.'));
      var ask=detailNode(d,'a','art-detail-ask','Bu eser hakkında soru sor');ask.href=questionHref(d,p,cfg);ask.target='_blank';ask.rel='noopener noreferrer';question.appendChild(ask);info.appendChild(question);
      var discussion=detailNode(d,'section','art-comments');discussion.id='art-comments-'+Date.now();
      var commentsHead=detailNode(d,'div','art-comments-head');commentsHead.appendChild(detailNode(d,'h3','','Yorumlar'));var commentsCount=detailNode(d,'span','art-comments-count','0 yorum');commentsHead.appendChild(commentsCount);discussion.appendChild(commentsHead);
      var commentsList=detailNode(d,'div','art-comment-list');commentsList.setAttribute('aria-live','polite');discussion.appendChild(commentsList);
      var commentForm=detailNode(d,'form','art-comment-form');
      var commentFormHead=detailNode(d,'div','art-comment-form-head');var commentFormTitle=detailNode(d,'strong','','Yorumunu yaz');commentFormHead.appendChild(commentFormTitle);var replyCancel=detailNode(d,'button','art-comment-cancel','Yanıtı iptal et');replyCancel.type='button';replyCancel.hidden=true;commentFormHead.appendChild(replyCancel);commentForm.appendChild(commentFormHead);
      var replyNotice=detailNode(d,'p','art-comment-reply-notice','');replyNotice.hidden=true;commentForm.appendChild(replyNotice);
      var nameFields=detailNode(d,'div','art-comment-name-fields');
      function commentField(labelText,name,max){var label=detailNode(d,'label','',labelText);var input=detailNode(d,'input');input.name=name;input.type='text';input.maxLength=max;input.required=true;input.autocomplete=name==='first_name'?'given-name':'family-name';label.appendChild(input);nameFields.appendChild(label);return input}
      var firstName=commentField('İsim','first_name',60),lastName=commentField('Soyisim','last_name',60);commentForm.appendChild(nameFields);
      try{firstName.value=window.localStorage.getItem('gallery-comment-first-name')||'';lastName.value=window.localStorage.getItem('gallery-comment-last-name')||''}catch(ignore){}
      var bodyLabel=detailNode(d,'label','art-comment-body-label','Yorum');var bodyField=detailNode(d,'textarea');bodyField.name='body';bodyField.required=true;bodyField.maxLength=1600;bodyField.rows=3;bodyField.placeholder='Bu eser sende nasıl bir his uyandırdı?';bodyLabel.appendChild(bodyField);commentForm.appendChild(bodyLabel);
      var photoRow=detailNode(d,'div','art-comment-photo-row');var avatarPreview=detailNode(d,'div','art-comment-avatar-preview','PB');var avatarLabel=detailNode(d,'label','art-comment-photo-label','Profil fotoğrafı ekle (isteğe bağlı)');var avatarInput=detailNode(d,'input');avatarInput.type='file';avatarInput.accept='image/png,image/jpeg,image/webp';avatarLabel.appendChild(avatarInput);photoRow.appendChild(avatarPreview);photoRow.appendChild(avatarLabel);commentForm.appendChild(photoRow);
      var commentStatus=detailNode(d,'p','art-comment-status','');commentStatus.setAttribute('role','status');commentStatus.setAttribute('aria-live','polite');commentForm.appendChild(commentStatus);
      var submitComment=detailNode(d,'button','art-comment-submit','Yorumu paylaş');submitComment.type='submit';commentForm.appendChild(submitComment);discussion.appendChild(commentForm);info.appendChild(discussion);
      var replyParent=null;
      function fileAsDataURL(file){return new Promise(function(resolve,reject){var reader=new d.defaultView.FileReader();reader.onload=function(){resolve(String(reader.result||''))};reader.onerror=function(){reject(new Error('Fotoğraf okunamadı.'))};reader.readAsDataURL(file)})}
      avatarInput.addEventListener('change',function(){var file=avatarInput.files&&avatarInput.files[0];if(!file){avatarPreview.textContent='PB';return}if(file.size>2*1024*1024){avatarInput.value='';avatarPreview.textContent='PB';commentStatus.textContent='Profil fotoğrafı en fazla 2 MB olabilir.';return}var reader=new d.defaultView.FileReader();reader.onload=function(){var img=detailNode(d,'img');img.src=reader.result;img.alt='Profil fotoğrafı önizlemesi';avatarPreview.replaceChildren(img)};reader.readAsDataURL(file)});
      function avatarFor(c){var avatar=detailNode(d,'div','art-comment-avatar');if(c.avatar_url){var img=detailNode(d,'img');img.src=c.avatar_url;img.alt='';img.loading='lazy';avatar.appendChild(img)}else{avatar.textContent=((c.first_name||'')[0]||'')+((c.last_name||'')[0]||'')}return avatar}
      function renderComment(c,isReply){var item=detailNode(d,'article',isReply?'art-comment art-reply':'art-comment');item.appendChild(avatarFor(c));var text=detailNode(d,'div','art-comment-content');var meta=detailNode(d,'div','art-comment-meta');meta.appendChild(detailNode(d,'strong','',c.first_name+' '+c.last_name));if(c.created_at){var dateNode=detailNode(d,'time','',c.created_at);var parsedDate=new Date(String(c.created_at).replace(' ','T')+'Z');if(!isNaN(parsedDate.getTime()))dateNode.textContent=parsedDate.toLocaleDateString('tr-TR',{day:'numeric',month:'short',year:'numeric'});meta.appendChild(dateNode)}text.appendChild(meta);text.appendChild(detailNode(d,'p','art-comment-text',c.body));if(!isReply){var actions=detailNode(d,'div','art-comment-actions');var replyButton=detailNode(d,'button','','Yanıtla');replyButton.type='button';replyButton.addEventListener('click',function(){replyParent=c.id;commentFormTitle.textContent='Yanıt yazıyorsun';replyNotice.textContent=c.first_name+' '+c.last_name+' adlı kişinin yorumuna yanıt veriyorsun.';replyNotice.hidden=false;replyCancel.hidden=false;bodyField.focus();commentForm.scrollIntoView({behavior:'smooth',block:'nearest'})});actions.appendChild(replyButton);text.appendChild(actions)}item.appendChild(text);return item}
      function loadComments(){commentsList.replaceChildren(detailNode(d,'p','art-comments-loading','Yorumlar yükleniyor…'));fetch('/api/comments?code='+encodeURIComponent(p.code),{cache:'no-store'}).then(function(response){if(!response.ok)throw new Error('Yorumlar alınamadı.');return response.json()}).then(function(data){var rows=data.comments||[],roots=rows.filter(function(row){return !row.parent_id}),replies={};rows.filter(function(row){return row.parent_id}).forEach(function(row){(replies[row.parent_id]||(replies[row.parent_id]=[])).push(row)});commentsCount.textContent=rows.length+' yorum';commentsCount.dataset.count=rows.length;commentsList.replaceChildren();if(!roots.length){commentsList.appendChild(detailNode(d,'p','art-comments-empty','Henüz yorum yok. İlk yorumu sen bırak.'));return}roots.forEach(function(root){var thread=detailNode(d,'div','art-comment-thread');thread.appendChild(renderComment(root,false));var children=replies[root.id]||[];if(children.length){var repliesList=detailNode(d,'div','art-comment-replies');children.forEach(function(reply){repliesList.appendChild(renderComment(reply,true))});thread.appendChild(repliesList)}commentsList.appendChild(thread)})}).catch(function(){commentsList.replaceChildren(detailNode(d,'p','art-comments-empty','Yorumlar şu anda yüklenemedi. Biraz sonra tekrar dene.'))})}
      replyCancel.addEventListener('click',function(){replyParent=null;replyNotice.hidden=true;replyCancel.hidden=true;commentFormTitle.textContent='Yorumunu yaz';bodyField.focus()});
      commentForm.addEventListener('submit',function(event){event.preventDefault();if(!commentForm.reportValidity())return;commentStatus.textContent='Yorum gönderiliyor…';submitComment.disabled=true;var selectedFile=avatarInput.files&&avatarInput.files[0];var avatarPromise=selectedFile?fileAsDataURL(selectedFile):Promise.resolve('');avatarPromise.then(function(avatarData){return fetch('/api/comments',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:p.code,first_name:firstName.value,last_name:lastName.value,body:bodyField.value,parent_id:replyParent,visitor:likeVisitor,avatar_data:avatarData})})}).then(function(response){return response.json().then(function(data){if(!response.ok)throw new Error(data.error||'Yorum gönderilemedi.');return data})}).then(function(result){try{window.localStorage.setItem('gallery-comment-first-name',firstName.value.trim());window.localStorage.setItem('gallery-comment-last-name',lastName.value.trim())}catch(ignore){}bodyField.value='';avatarInput.value='';avatarPreview.textContent=((firstName.value[0]||'')+(lastName.value[0]||''));replyParent=null;replyNotice.hidden=true;replyCancel.hidden=true;commentFormTitle.textContent='Yorumunu yaz';commentStatus.textContent='Yorumun paylaşıldı.';loadComments();setCommentCount(d,p.code,result.count)}).catch(function(error){commentStatus.textContent=error.message||'Yorum gönderilemedi. Tekrar dene.'}).finally(function(){submitComment.disabled=false})});

      var previousOverflow=d.body.style.overflow;d.body.style.overflow='hidden';
      function dismiss(){if(!overlay.parentNode)return;overlay.classList.add('is-closing');d.body.style.overflow=previousOverflow;d.removeEventListener('keydown',onKeyDown);setTimeout(function(){overlay.remove()},240)}
      function onKeyDown(event){if(event.key==='Escape')dismiss()}
      close.addEventListener('click',dismiss);overlay.addEventListener('click',function(event){if(event.target===overlay)dismiss()});d.addEventListener('keydown',onKeyDown);d.body.appendChild(overlay);close.focus();loadComments();if(focusComments)setTimeout(function(){discussion.scrollIntoView({behavior:'smooth',block:'nearest'})},180);
    }
    function ensureUnifiedCardStyle(d){var style=d.getElementById('unified-gallery-card-style');if(!style){style=d.createElement('style');style.id='unified-gallery-card-style';style.textContent=`.card.gallery-work-card{box-sizing:border-box!important;display:flex!important;flex-direction:column!important;align-items:stretch!important;height:auto!important;min-height:0!important;padding:8px!important;border:1px solid rgba(217,199,193,.88)!important;border-radius:20px!important;background:rgba(255,253,251,.94)!important;box-shadow:0 12px 28px rgba(66,49,47,.09)!important;transform:none!important;transition:none!important}.card.gallery-work-card:hover{transform:none!important;box-shadow:0 12px 28px rgba(66,49,47,.09)!important}.card.gallery-work-card>.art{position:relative!important;isolation:isolate!important;box-sizing:border-box!important;width:100%!important;height:154px!important;min-height:154px!important;max-height:none!important;flex:0 0 154px!important;aspect-ratio:auto!important;overflow:hidden!important;border-radius:13px!important;background:rgba(235,229,225,.6)!important}.card.gallery-work-card>.art.has-art-backdrop:before{content:""!important;display:block!important;position:absolute!important;inset:-14px!important;z-index:0!important;background-image:var(--art-backdrop)!important;background-size:cover!important;background-position:center!important;background-repeat:no-repeat!important;filter:blur(20px) saturate(1.55) contrast(1.08)!important;opacity:.98!important;transform:scale(1.14)!important}.card.gallery-work-card>.art.has-art-backdrop:after{content:""!important;display:block!important;position:absolute!important;inset:0!important;z-index:1!important;background:linear-gradient(110deg,rgba(255,255,255,.08),rgba(255,255,255,.02) 52%,rgba(56,46,53,.06))!important;backdrop-filter:none!important;-webkit-backdrop-filter:none!important;pointer-events:none!important}.card.gallery-work-card>.art img{position:relative!important;inset:auto!important;z-index:2!important;display:block!important;width:100%!important;height:100%!important;object-fit:contain!important;background:transparent!important;border-radius:inherit!important}.card.gallery-work-card>.ct{box-sizing:border-box!important;width:100%!important;min-width:0!important;min-height:0!important;flex:1 1 auto!important;display:grid!important;grid-template-columns:minmax(0,1fr) auto!important;grid-auto-flow:row!important;grid-auto-rows:auto!important;align-content:start!important;align-items:center!important;gap:4px 8px!important;padding:8px 9px 7px!important;text-align:left!important}.card.gallery-work-card>.ct>.work-code-badge{position:static!important;grid-column:1/-1!important;grid-row:1!important;justify-self:start!important;width:max-content!important;height:26px!important;min-height:26px!important;max-width:100%!important;box-sizing:border-box!important;margin:0!important;padding:4px 7px!important;border:1px solid #ead9e1!important;border-radius:999px!important;background:rgba(251,241,245,.9)!important;color:#79546f!important;font:700 9px/1 Arial,sans-serif!important;letter-spacing:.08em!important;box-shadow:none!important}.card.gallery-work-card>.ct>.sf{grid-column:1!important;grid-row:2!important;justify-self:start!important;min-width:0!important;margin:0!important;text-align:left!important;font-size:14px!important;line-height:1.2!important}.card.gallery-work-card>.ct>span:not(.pr):not(.catalog-description):not(.work-code-badge){grid-column:1!important;grid-row:3!important;justify-self:start!important;min-width:0!important;margin:0!important;text-align:left!important;color:#827783!important;font-size:11px!important;line-height:1.2!important}.card.gallery-work-card>.ct>.pr{grid-column:2!important;grid-row:2/4!important;justify-self:end!important;align-self:center!important;display:flex!important;flex-direction:column!important;align-items:flex-end!important;gap:1px!important;min-width:0!important;margin:0!important;text-align:right!important;white-space:nowrap!important;font-size:13px!important;line-height:1.15!important}.card.gallery-work-card>.ct>.catalog-description{grid-column:1/-1!important;grid-row:auto!important;height:1.3em!important;min-height:1.3em!important;max-height:1.3em!important;box-sizing:border-box!important;margin:2px 0 0!important;overflow:hidden!important;text-overflow:ellipsis!important;white-space:nowrap!important;text-align:left!important;line-height:1.3!important}.card.gallery-work-card>.ct>.catalog-description[hidden]{display:none!important;visibility:visible!important;height:0!important;min-height:0!important;max-height:0!important;margin:0!important}.card.gallery-work-card>.ct>.card-actions{grid-column:1/-1!important;grid-row:auto!important;display:flex!important;flex-direction:row!important;grid-template-columns:none!important;width:100%!important;gap:6px!important;margin:4px 0 0!important}.card.gallery-work-card>.ct>.card-actions>.btn{box-sizing:border-box!important;min-width:0!important;min-height:33px!important;flex:1 1 0!important;padding:6px 7px!important}.card.gallery-work-card>.ct>.like-row{grid-column:1/-1!important;grid-row:auto!important;display:flex!important;flex-wrap:nowrap!important;align-items:center!important;justify-content:space-between!important;gap:4px!important;width:100%!important;margin:0!important;padding:0!important}.card.gallery-work-card>.ct>.like-row .like-actions{gap:2px!important;margin-left:auto!important}.card.gallery-work-card>.ct>.like-row .question-button{min-height:27px!important;padding:5px 8px!important;font-size:10px!important}.card.gallery-work-card>.ct>.like-row .like-button,.card.gallery-work-card>.ct>.like-row .comment-button{min-width:32px!important;min-height:28px!important;padding:3px 5px!important;gap:3px!important}.card.gallery-work-card>.ct>.like-row .like-button svg,.card.gallery-work-card>.ct>.like-row .comment-button svg{width:15px!important;height:15px!important}@media(max-width:700px){.card.gallery-work-card>.art{height:126px!important;min-height:126px!important;flex-basis:126px!important}.card.gallery-work-card>.ct{gap:4px 6px!important;padding:7px 8px 6px!important}.card.gallery-work-card>.ct>.sf{font-size:13px!important}.card.gallery-work-card>.ct>.pr{font-size:12px!important}.card.gallery-work-card>.ct>.card-actions{gap:5px!important;margin-top:3px!important}.card.gallery-work-card>.ct>.card-actions>.btn{min-height:30px!important;padding:5px 4px!important;font-size:10px!important}.card.gallery-work-card>.ct>.like-row .question-button{min-height:25px!important;padding:4px 6px!important;font-size:9px!important}.card.gallery-work-card>.ct>.like-row .like-button,.card.gallery-work-card>.ct>.like-row .comment-button{min-width:30px!important;min-height:27px!important;padding:3px 4px!important}}@media(max-width:700px){#yeni-gelenler .editorial-grid,#sanatcinin-secimi .curated-grid,#sold-works-grid,#admin-live-catalog .admin-catalog-grid{box-sizing:border-box!important;width:var(--gallery-viewport-width,100vw)!important;max-width:none!important;margin-left:calc((100% - var(--gallery-viewport-width,100vw))/2)!important;margin-right:calc((100% - var(--gallery-viewport-width,100vw))/2)!important;padding:0 10px!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;justify-content:stretch!important;gap:12px!important}}#yeni-gelenler .editorial-grid>.card.gallery-work-card,#sanatcinin-secimi .curated-grid>.card.gallery-work-card,#sold-works-grid>.card.gallery-work-card,#admin-live-catalog .admin-catalog-grid>.card.gallery-work-card{box-sizing:border-box!important;flex:0 0 262px!important;width:262px!important;min-width:262px!important;max-width:262px!important;height:370px!important;min-height:370px!important}#yeni-gelenler .editorial-grid>.card.gallery-work-card>.ct,#sanatcinin-secimi .curated-grid>.card.gallery-work-card>.ct,#sold-works-grid>.card.gallery-work-card>.ct,#admin-live-catalog .admin-catalog-grid>.card.gallery-work-card>.ct{display:grid!important;grid-template-columns:minmax(0,1fr) auto!important;grid-auto-flow:row!important;grid-auto-rows:auto!important;align-content:start!important;align-items:center!important;gap:4px 8px!important;padding:8px 9px 7px!important}#yeni-gelenler .editorial-grid>.card.gallery-work-card>.ct>.pr,#sanatcinin-secimi .curated-grid>.card.gallery-work-card>.ct>.pr,#sold-works-grid>.card.gallery-work-card>.ct>.pr,#admin-live-catalog .admin-catalog-grid>.card.gallery-work-card>.ct>.pr{margin:0!important}#yeni-gelenler .editorial-grid>.card.gallery-work-card>.ct>.catalog-description,#sanatcinin-secimi .curated-grid>.card.gallery-work-card>.ct>.catalog-description,#sold-works-grid>.card.gallery-work-card>.ct>.catalog-description,#admin-live-catalog .admin-catalog-grid>.card.gallery-work-card>.ct>.catalog-description{margin:2px 0 0!important}#yeni-gelenler .editorial-grid>.card.gallery-work-card>.ct>.card-actions,#sanatcinin-secimi .curated-grid>.card.gallery-work-card>.ct>.card-actions,#sold-works-grid>.card.gallery-work-card>.ct>.card-actions,#admin-live-catalog .admin-catalog-grid>.card.gallery-work-card>.ct>.card-actions{margin:8px 0 0!important}#yeni-gelenler .editorial-grid>.card.gallery-work-card>.ct>.like-row,#sanatcinin-secimi .curated-grid>.card.gallery-work-card>.ct>.like-row,#sold-works-grid>.card.gallery-work-card>.ct>.like-row,#admin-live-catalog .admin-catalog-grid>.card.gallery-work-card>.ct>.like-row{margin:0!important}@media(max-width:700px){#yeni-gelenler .editorial-grid>.card.gallery-work-card,#sanatcinin-secimi .curated-grid>.card.gallery-work-card,#sold-works-grid>.card.gallery-work-card,#admin-live-catalog .admin-catalog-grid>.card.gallery-work-card{flex:initial!important;width:100%!important;min-width:0!important;max-width:none!important;justify-self:stretch!important;height:310px!important;min-height:310px!important}#yeni-gelenler .editorial-grid>.card.gallery-work-card>.ct,#sanatcinin-secimi .curated-grid>.card.gallery-work-card>.ct,#sold-works-grid>.card.gallery-work-card>.ct,#admin-live-catalog .admin-catalog-grid>.card.gallery-work-card>.ct{gap:4px 6px!important;padding:7px 8px 6px!important}}#yeni-gelenler .editorial-grid>.card.gallery-work-card>.art.has-art-backdrop:before,#sanatcinin-secimi .curated-grid>.card.gallery-work-card>.art.has-art-backdrop:before,#sold-works-grid>.card.gallery-work-card>.art.has-art-backdrop:before,#admin-live-catalog .admin-catalog-grid>.card.gallery-work-card>.art.has-art-backdrop:before{filter:blur(20px) saturate(1.55) contrast(1.08)!important;opacity:.98!important;transform:scale(1.14)!important}#yeni-gelenler .editorial-grid>.card.gallery-work-card>.art.has-art-backdrop:after,#sanatcinin-secimi .curated-grid>.card.gallery-work-card>.art.has-art-backdrop:after,#sold-works-grid>.card.gallery-work-card>.art.has-art-backdrop:after,#admin-live-catalog .admin-catalog-grid>.card.gallery-work-card>.art.has-art-backdrop:after{backdrop-filter:none!important;-webkit-backdrop-filter:none!important} @media(max-width:700px){#yeni-gelenler .editorial-grid>.card.gallery-work-card,#sanatcinin-secimi .curated-grid>.card.gallery-work-card,#sold-works-grid>.card.gallery-work-card,#admin-live-catalog .admin-catalog-grid>.card.gallery-work-card{height:310px!important;min-height:310px!important}}@media(max-width:700px){.card.gallery-work-card{height:310px!important;min-height:310px!important}}body{background-color:#eab5c8!important}.pg{background:#eab5c8!important;background-image:none!important}.pg #eserler,.pg #yeni-gelenler,.pg #sanatcinin-secimi,.pg #tum-eserler,.pg .editorial-section{background-color:#eab5c8!important}`;}if(d.body&&(style.parentElement!==d.body||d.body.lastElementChild!==style))d.body.appendChild(style)}
    function install(d){var filterDetails=Array.from(d.querySelectorAll('details')).filter(function(x){var text=(x.querySelector('summary')||{}).textContent.trim().toLocaleLowerCase('tr');return text.startsWith('kategori')||text.startsWith('fiyat')||text.startsWith('sırala')});if(filterDetails.length){var controls=filterDetails[0].parentElement&&filterDetails[0].parentElement.parentElement;if(controls&&controls!==d.body&&controls!==d.documentElement)controls.remove()}Array.from(d.querySelectorAll('.carousel-arrow,[data-featured-step]')).forEach(function(button){button.remove()});var shimmerStyle=d.getElementById('artist-selection-shimmer');if(!shimmerStyle){shimmerStyle=d.createElement('style');shimmerStyle.id='artist-selection-shimmer';shimmerStyle.textContent='#sanatcinin-secimi .artist-signature,#sanatcinin-secimi .section-heading h2{background-size:220% 100%;background-repeat:no-repeat;background-position:100% 50%;-webkit-background-clip:text;background-clip:text;color:transparent!important;-webkit-text-fill-color:transparent}#sanatcinin-secimi .artist-signature{background-image:linear-gradient(105deg,#79546f 0%,#79546f 39%,#fff0bb 48%,#dfb56f 51%,#79546f 60%,#79546f 100%);animation:gallery-heading-shimmer 5.2s linear infinite}#sanatcinin-secimi .section-heading h2{background-image:linear-gradient(105deg,#344b43 0%,#344b43 39%,#fff2c5 48%,#d9ad69 51%,#344b43 60%,#344b43 100%);animation:gallery-heading-shimmer 5.2s linear infinite}@keyframes gallery-heading-shimmer{to{background-position:-220% 50%}}@media(prefers-reduced-motion:reduce){#sanatcinin-secimi .artist-signature,#sanatcinin-secimi .section-heading h2{animation:none}}';d.head.appendChild(shimmerStyle)}var visualFixStyle=d.getElementById('gallery-requested-visual-fixes');if(!visualFixStyle){visualFixStyle=d.createElement('style');visualFixStyle.id='gallery-requested-visual-fixes';visualFixStyle.textContent='#top .card.gallery-work-card>.art.has-art-backdrop:before{content:""!important;display:block!important;position:absolute!important;inset:-14px!important;z-index:0!important;background-image:var(--art-backdrop)!important;background-size:cover!important;background-position:center!important;background-repeat:no-repeat!important;filter:blur(20px) saturate(1.55) contrast(1.08)!important;opacity:.98!important;transform:scale(1.14)!important}#top .card.gallery-work-card>.art.has-art-backdrop:after{content:""!important;display:block!important;position:absolute!important;inset:0!important;z-index:1!important;background:linear-gradient(110deg,rgba(255,255,255,.08),rgba(255,255,255,.02) 52%,rgba(56,46,53,.06))!important;backdrop-filter:none!important;-webkit-backdrop-filter:none!important;pointer-events:none!important}.card.gallery-work-card>.ct>.card-actions>.sold-tag{background:#d7d7d7!important;border-color:#d7d7d7!important;color:#646464!important;box-shadow:none!important;cursor:default!important}.card.gallery-work-card>.ct>.like-row>.question-button{flex:1 1 0!important;min-width:74px!important;max-width:none!important;justify-content:center!important;margin-right:0!important}.card.gallery-work-card>.ct>.like-row>.like-actions{flex:0 0 auto!important;margin-left:auto!important}.card.gallery-work-card>.ct>.catalog-description[hidden]{display:none!important;visibility:visible!important;height:0!important;min-height:0!important;max-height:0!important;margin:0!important}@media(max-width:700px){.card.gallery-work-card{height:310px!important;min-height:310px!important}.card.gallery-work-card>.art{height:114px!important;min-height:114px!important;flex-basis:114px!important}.card.gallery-work-card>.ct{padding:6px 7px 4px!important;gap:3px 5px!important}.card.gallery-work-card>.ct>.work-code-badge{height:22px!important;min-height:22px!important;padding:3px 6px!important}.card.gallery-work-card>.ct>.catalog-description{height:1.3em!important;min-height:1.3em!important;max-height:1.3em!important;margin:1px 0 0!important}.card.gallery-work-card>.ct>.card-actions{margin-top:3px!important;gap:4px!important}.card.gallery-work-card>.ct>.like-row .question-button{min-height:27px!important;padding:4px 8px!important;font-size:10px!important}}.nav ul{margin-left:auto!important;flex-direction:row-reverse!important;justify-content:flex-start!important;gap:clamp(10px,2vw,28px)!important}.catalog-search{display:block!important;text-align:center!important}.catalog-search>span{display:inline-flex!important;align-items:center!important;justify-content:center!important;gap:7px!important;margin:0 auto!important;color:#72566b!important;font-weight:700!important}.catalog-search>span:before{content:"✿";color:#dc91ac;font-size:15px;line-height:1}.catalog-search input{padding-left:43px!important;background-image:url("data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%237b5a70%22 stroke-width=%222%22%3E%3Ccircle cx=%2211%22 cy=%2211%22 r=%227%22/%3E%3Cpath d=%22m16 16 4 4%22/%3E%3C/svg%3E")!important;background-repeat:no-repeat!important;background-position:15px 50%!important;background-size:17px 17px!important;border-color:#e8ccd7!important;background-color:#fffdfb!important;box-shadow:0 6px 20px rgba(121,84,111,.09)!important}.catalog-search input:focus{border-color:#bd7d9a!important;box-shadow:0 0 0 4px rgba(219,145,172,.14),0 8px 24px rgba(121,84,111,.12)!important}@media(max-width:640px){.nav{padding:14px 18px!important;gap:10px!important}.nav ul{width:100%!important;justify-content:space-between!important;gap:8px!important}.nav ul a{font-size:12px!important}}.hero-signature .signature-final{color:#805171!important;-webkit-text-fill-color:#805171!important}.hero-signature .signature-final:after{content:"Perihan Baktaş";position:absolute;inset:0;color:transparent;-webkit-text-fill-color:transparent;background:linear-gradient(105deg,transparent 18%,rgba(255,248,216,.92) 46%,rgba(255,255,255,.95) 51%,transparent 78%);background-size:240% 100%;-webkit-background-clip:text;background-clip:text;animation:hero-signature-glint 4.2s ease-in-out 2.5s infinite;pointer-events:none}@keyframes hero-signature-glint{0%,18%{background-position:120% 50%}68%,100%{background-position:-120% 50%}}#sanatcinin-secimi .artist-signature{color:#79546f!important;-webkit-text-fill-color:#79546f!important;background:none!important;animation:gallery-heading-glow 4.6s ease-in-out infinite!important}#sanatcinin-secimi .section-heading h2{color:#344b43!important;-webkit-text-fill-color:#344b43!important;background:none!important;animation:gallery-heading-glow 4.6s ease-in-out infinite!important}@keyframes gallery-heading-glow{0%,100%{text-shadow:0 0 0 rgba(255,235,188,0)}50%{text-shadow:0 0 9px rgba(255,235,188,.72),0 0 19px rgba(213,168,102,.28)}}@media(prefers-reduced-motion:reduce){.hero-signature .signature-final:after,#sanatcinin-secimi .artist-signature,#sanatcinin-secimi .section-heading h2{animation:none!important}}#eserler .ttl h2.sf,#yeni-gelenler .section-heading h2,#sanatcinin-secimi .section-heading h2,#admin-live-catalog .section-heading h2{color:#171316!important;-webkit-text-fill-color:#171316!important;background:none!important;background-image:none!important;-webkit-background-clip:border-box!important;background-clip:border-box!important;font-weight:700!important;font-size:clamp(30px,3.2vw,40px)!important;letter-spacing:-.02em!important;text-shadow:0 1px 0 rgba(255,255,255,.42)!important;animation:none!important}';d.head.appendChild(visualFixStyle)}var themeAnimationStyle=d.getElementById('gallery-pink-purple-painter-style');if(!themeAnimationStyle){themeAnimationStyle=d.createElement('style');themeAnimationStyle.id='gallery-pink-purple-painter-style';themeAnimationStyle.textContent=':root{--paper:#f8eff1;--paper-deep:#f2e7eb}html,body{background:#f8eff1!important}.pg{background:radial-gradient(circle at 8% 0,rgba(247,219,230,.72),transparent 40%),radial-gradient(circle at 100% 70%,rgba(229,220,241,.48),transparent 45%),radial-gradient(circle at 90% 20%,rgba(239,224,238,.48),transparent 35%),#f8eff1!important}.pt{background:#70449c!important;box-shadow:0 2px 8px rgba(75,40,112,.42)!important;opacity:.98!important}.pg svg[aria-hidden="true"] g[fill="#70449c"],.pg svg[aria-hidden="true"] g[fill="#70449c"] ellipse{fill:#70449c!important}.pg .story-mark{color:#70449c!important;background:#e8d9f0!important;text-shadow:0 2px 8px rgba(75,40,112,.26)}#top>svg path{fill:#f8eff1!important;fill-opacity:1!important}.herobg{background-image:linear-gradient(90deg,rgba(248,239,242,.99) 0%,rgba(248,239,242,.97) 34%,rgba(248,239,242,.82) 48%,rgba(248,239,242,.2) 74%,rgba(248,239,242,.02) 100%),url(\"75226ce7-fcbc-43ef-b93d-64f677de0085\")!important;background-color:#f8eff1!important}.share-button{box-sizing:border-box;display:inline-flex;align-items:center;justify-content:center;gap:4px;min-width:42px;min-height:29px;padding:5px 7px;border:1px solid #eadfe8;border-radius:999px;background:#fffafc;color:#80677c;font:700 11px/1 Arial,sans-serif;cursor:pointer;transition:background .18s ease,color .18s ease}.share-button:hover{background:#f8edf2;color:#76516b}.share-button:disabled{opacity:.55;cursor:wait}.share-button svg{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}.gallery-share-feedback{position:fixed;z-index:10000;left:50%;bottom:22px;max-width:calc(100vw - 28px);padding:10px 15px;border:1px solid rgba(121,84,111,.2);border-radius:999px;background:rgba(255,250,252,.94);color:#614a5e;font:600 13px/1.3 Arial,sans-serif;box-shadow:0 8px 28px rgba(61,43,58,.16);opacity:0;transform:translate(-50%,10px);pointer-events:none;transition:opacity .2s ease,transform .2s ease}.gallery-share-feedback.is-visible{opacity:1;transform:translate(-50%,0)}@media(max-width:680px){.herobg{background-image:linear-gradient(180deg,rgba(248,239,242,.98) 0%,rgba(248,239,242,.94) 45%,rgba(248,239,242,.58) 72%,rgba(248,239,242,.08) 100%),url(\"75226ce7-fcbc-43ef-b93d-64f677de0085\")!important}.like-row .share-button{min-width:32px;min-height:28px;padding:3px 4px;gap:2px}.like-row .share-button svg{width:14px;height:14px}.like-row .share-count{font-size:9px}}@media(max-width:360px){.card.gallery-work-card>.ct>.like-row{flex-wrap:wrap!important}.card.gallery-work-card>.ct>.like-row>.question-button{flex:1 0 100%!important}.card.gallery-work-card>.ct>.like-row .share-button{min-width:28px;padding:3px 3px}}';d.head.appendChild(themeAnimationStyle)}var collections=d.getElementById('koleksiyonlar');if(collections){collections.hidden=true;collections.setAttribute('aria-hidden','true');collections.style.display='none'}if(d.getElementById('admin-live-catalog'))return;var style=d.getElementById('admin-catalog-sync');if(!style){style=d.createElement('style');style.id='admin-catalog-sync';style.textContent='del,s{color:#b9b1b5!important;opacity:.58!important}#admin-live-catalog{max-width:1160px;margin:42px auto 56px;padding:0 24px;text-align:center}#admin-live-catalog h2{font:700 30px Georgia,serif;color:#3f5a46;margin:0 0 8px}#admin-live-catalog .admin-catalog-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,240px),250px));justify-content:center;gap:20px;margin-top:20px}#admin-live-catalog .catalog-search{display:block;max-width:440px;margin:20px auto 0;text-align:left;color:#72566b;font:600 13px/1.4 Arial,sans-serif}#admin-live-catalog .catalog-search input{box-sizing:border-box;display:block;width:100%;min-height:46px;margin-top:7px;padding:0 16px;border:1px solid #e4d3cb;border-radius:999px;background:#fffdfb;color:#3f5a46;font:500 15px/1.4 Arial,sans-serif;box-shadow:0 5px 18px rgba(72,53,45,.06)}#admin-live-catalog .catalog-search input:focus{outline:2px solid rgba(184,123,150,.28);border-color:#b87b96}#admin-live-catalog .catalog-search-count{min-height:1.2em;margin:8px 0 0;color:#827783;font:500 12px/1.4 Arial,sans-serif}#admin-live-catalog .catalog-search-empty{margin:24px auto 0;color:#827783;font-size:14px}.admin-filter-menu button{display:block;width:100%;border:0;background:transparent;text-align:left;cursor:pointer}#admin-live-catalog .card[hidden]{display:none!important}.editorial-section .editorial-grid,.editorial-section .curated-grid{grid-template-columns:repeat(auto-fit,minmax(min(100%,240px),280px))!important;justify-content:center!important}.editorial-section .card{width:100%;max-width:280px;min-width:0;justify-self:center}#koleksiyonlar .collection-art-grid{max-width:1000px;margin:24px auto 0;grid-template-columns:repeat(auto-fit,minmax(min(100%,240px),280px));justify-content:center;gap:20px}#koleksiyonlar .collection-art-grid .card{width:100%;max-width:280px;min-width:0;justify-self:center}.like-row{display:flex;align-items:center;justify-content:space-between;gap:6px;flex-wrap:wrap;margin-top:7px}.like-actions{display:inline-flex;align-items:center;justify-content:flex-end;gap:2px;flex:none}.question-button{display:inline-flex;align-items:center;justify-content:center;min-height:26px;padding:5px 9px;border:1px solid #eadbe2;border-radius:999px;background:#fbf4f6;color:#79546f;font:600 11px/1 Arial,sans-serif;text-decoration:none;white-space:nowrap;transition:background .18s ease,transform .18s ease}.question-button:hover{background:#f4e5ec;color:#5d4053;transform:translateY(-1px)}.question-button:focus-visible{outline:2px solid #b87b96;outline-offset:2px}.like-button{display:inline-flex;align-items:center;justify-content:center;gap:6px;min-width:44px;padding:5px 8px;border:0;border-radius:999px;background:transparent;color:#927282;font:700 12px/1 Arial,sans-serif;cursor:pointer;transition:color .18s ease,background .18s ease,transform .18s ease}.like-button:hover{background:#fbf0f3;color:#d64f79;transform:translateY(-1px)}.like-button svg{width:19px;height:19px;fill:transparent;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round;transition:fill .18s ease,transform .18s ease}.like-button[aria-pressed=true]{color:#df4f7b}.like-button[aria-pressed=true] svg{fill:currentColor;transform:scale(1.06)}.like-button:disabled{opacity:.62;cursor:wait}.like-button:focus-visible{outline:2px solid #b87b96;outline-offset:2px}@media(max-width:600px){#admin-live-catalog{padding:0 14px}}.art-frame{height:auto!important;aspect-ratio:3/4;background:#f2eee9}.art-frame img{object-fit:contain!important}.fw .art,#sold-works-grid .art,#admin-live-catalog .art,#yeni-gelenler .art,#sanatcinin-secimi .art,.editorial-section .art,#koleksiyonlar .collection-art-grid .art{aspect-ratio:3/4!important}';d.head.appendChild(style)}
    var compactStyle=d.getElementById('compact-product-cards');if(!compactStyle){compactStyle=d.createElement('style');compactStyle.id='compact-product-cards';compactStyle.textContent='.work-code-badge{position:absolute!important;z-index:20!important;top:10px!important;left:10px!important;display:inline-flex!important;align-items:center!important;padding:5px 9px!important;border:1px solid rgba(255,255,255,.72)!important;border-radius:999px!important;background:rgba(255,252,250,.95)!important;color:#73546a!important;font:700 10px/1 Arial,sans-serif!important;letter-spacing:.08em!important;box-shadow:0 3px 10px rgba(54,39,42,.12)!important;pointer-events:none!important}.art[data-work-code],.art-frame[data-work-code]{position:relative}@media(max-width:700px){.fw .ftt>.card>.art,.editorial-section .card>.art,#yeni-gelenler .editorial-grid>.card>.art,#sanatcinin-secimi .curated-grid>.card>.art,#sold-works-grid>.card>.art,#admin-live-catalog .card>.art{height:auto!important;min-height:0!important;aspect-ratio:1/1!important}.fw .ftt>.card>.ct,.editorial-section .card>.ct,#yeni-gelenler .editorial-grid>.card>.ct,#sanatcinin-secimi .curated-grid>.card>.ct,#sold-works-grid>.card>.ct,#admin-live-catalog .card>.ct{padding:8px 9px 9px!important}.fw .ftt>.card>.ct .catalog-description,.editorial-section .card>.ct .catalog-description,#yeni-gelenler .editorial-grid>.card>.ct .catalog-description,#sanatcinin-secimi .curated-grid>.card>.ct .catalog-description,#sold-works-grid>.card>.ct .catalog-description,#admin-live-catalog .card>.ct .catalog-description{display:-webkit-box!important;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden;min-height:0!important;margin:5px 0 7px!important}.fw .ftt>.card .card-actions,.editorial-section .card .card-actions,#yeni-gelenler .editorial-grid>.card .card-actions,#sanatcinin-secimi .curated-grid>.card .card-actions,#sold-works-grid .card .card-actions,#admin-live-catalog .card .card-actions{margin-top:6px!important;gap:7px!important}.fw .ftt>.card .like-row,.editorial-section .card .like-row,#yeni-gelenler .editorial-grid>.card .like-row,#sanatcinin-secimi .curated-grid>.card .like-row,#sold-works-grid .card .like-row,#admin-live-catalog .card .like-row{margin-top:3px!important}}';d.head.appendChild(compactStyle)}
    var detailStyle=d.getElementById('art-detail-style');if(!detailStyle){detailStyle=d.createElement('style');detailStyle.id='art-detail-style';detailStyle.textContent=`.art-detail-overlay{position:fixed;inset:0;z-index:99999;display:grid;place-items:center;padding:24px;background:rgba(42,34,39,.58);backdrop-filter:blur(6px);animation:detail-backdrop-in .25s ease both}.art-detail-panel{position:relative;width:min(1080px,100%);max-height:88vh;display:grid;grid-template-columns:minmax(0,1.05fr) minmax(320px,.95fr);background:#fffdf9;border:1px solid #efe2dc;border-radius:24px;overflow:auto;box-shadow:0 28px 90px rgba(36,27,33,.3);animation:detail-panel-in .55s cubic-bezier(.2,.8,.2,1) both}.art-detail-art{min-width:0;min-height:520px;padding:24px;display:grid;place-items:center;background:linear-gradient(145deg,#f5eee9,#f8f2ed)}.art-detail-art img{display:block;width:100%;height:100%;max-height:78vh;object-fit:contain;animation:artwork-expand-left .72s cubic-bezier(.2,.8,.2,1) both}.art-detail-art>.art{width:100%;height:100%;aspect-ratio:3/4!important}.art-detail-info{padding:clamp(26px,4vw,50px);align-self:center}.art-detail-kicker{font:700 10px Arial,sans-serif;letter-spacing:.2em;color:#a5637e}.art-detail-info h2{margin:12px 40px 6px 0;color:#344b43;font:600 clamp(27px,3.4vw,42px)/1.12 Georgia,serif}.art-detail-product-name{margin:0;color:#756a74;font-size:15px}.art-detail-code{margin:8px 0 20px;color:#927282;font-size:12px;letter-spacing:.05em}.art-detail-facts{display:flex;gap:28px;padding:15px 0;border-block:1px solid #eee3dc}.art-detail-facts div{display:grid;gap:3px}.art-detail-facts span{font-size:11px;color:#827783}.art-detail-facts b{font-size:16px;color:#486454}.art-detail-story-title{margin:20px 0 6px;color:#344b43;font:600 20px Georgia,serif}.art-detail-story{margin:0;color:#746d75;font-size:14px;line-height:1.75;white-space:pre-line}.art-detail-question{margin-top:22px;padding:17px;background:#f8eff1;border-radius:16px}.art-detail-question>b{color:#503f4b;font-size:14px}.art-detail-question>p{margin:5px 0 12px;color:#827783;font-size:12px}.art-detail-ask{display:inline-flex;align-items:center;justify-content:center;min-height:43px;padding:10px 17px;border-radius:24px;background:#486454;color:white;font-size:12px;font-weight:700}.art-detail-ask:hover{background:#354d41;color:white;transform:translateY(-1px)}.art-detail-close{position:absolute;right:14px;top:14px;z-index:2;width:42px;height:42px;border:1px solid #eadfd6;border-radius:50%;background:#fff;color:#79546f;font-size:27px;line-height:1;cursor:pointer}.art-detail-close:hover{background:#f8eff1}.art-detail-panel:has(.art-detail-close:focus-visible),.art-detail-close:focus-visible,.art-detail-ask:focus-visible{outline:3px solid #bd8ca3;outline-offset:3px}@keyframes detail-backdrop-in{from{opacity:0}to{opacity:1}}@keyframes detail-panel-in{from{opacity:0;transform:translateY(18px) scale(.94)}to{opacity:1;transform:translateY(0) scale(1)}}@keyframes artwork-expand-left{from{opacity:.35;transform:translate3d(36px,12px,0) scale(.66);transform-origin:left center}to{opacity:1;transform:translate3d(0,0,0) scale(1);transform-origin:left center}}.art-detail-overlay.is-closing{animation:detail-backdrop-out .22s ease both}.art-detail-overlay.is-closing .art-detail-panel{animation:detail-panel-out .22s ease both}@keyframes detail-backdrop-out{to{opacity:0}}@keyframes detail-panel-out{to{opacity:0;transform:translateY(8px) scale(.97)}}@media(max-width:720px){.art-detail-overlay{padding:10px}.art-detail-panel{grid-template-columns:1fr;max-height:94vh;border-radius:18px}.art-detail-art{min-height:0;height:38vh;max-height:340px;padding:14px}.art-detail-art img{max-height:36vh}.art-detail-info{padding:22px 20px 24px}.art-detail-info h2{font-size:29px}.art-detail-facts{gap:22px}}@media(prefers-reduced-motion:reduce){.art-detail-overlay,.art-detail-panel,.art-detail-art img{animation-duration:.01ms!important;animation-iteration-count:1!important}}`;d.head.appendChild(detailStyle)}
    var commentStyle=d.getElementById('gallery-comment-style');if(!commentStyle){commentStyle=d.createElement('style');commentStyle.id='gallery-comment-style';commentStyle.textContent='.like-row{align-items:center;gap:5px}.comment-button{display:inline-flex;align-items:center;justify-content:center;gap:5px;min-width:44px;padding:5px 8px;border:0;border-radius:999px;background:transparent;color:#927282;font:700 12px/1 Arial,sans-serif;cursor:pointer;transition:color .18s ease,background .18s ease,transform .18s ease}.comment-button:hover{background:#f7eef3;color:#79546f;transform:translateY(-1px)}.comment-button svg{width:19px;height:19px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}.comment-button:focus-visible,.art-comment-form button:focus-visible{outline:2px solid #b87b96;outline-offset:2px}.art-comments{margin-top:22px;padding-top:20px;border-top:1px solid #eee3dc}.art-comments-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:13px}.art-comments-head h3{margin:0;color:#344b43;font:600 21px Georgia,serif}.art-comments-count{color:#927282;font-size:12px}.art-comment-list{display:grid;gap:12px;margin:0 0 18px}.art-comment-thread{padding-bottom:12px;border-bottom:1px solid #f0e8e2}.art-comment,.art-comment-reply{display:grid;grid-template-columns:38px minmax(0,1fr);align-items:start;gap:10px}.art-comment-avatar,.art-comment-avatar-preview{width:38px;height:38px;overflow:hidden;display:grid;place-items:center;border-radius:50%;background:linear-gradient(145deg,#f6dce5,#e6ede4);color:#79546f;font-size:12px;font-weight:700}.art-comment-avatar img,.art-comment-avatar-preview img{width:100%;height:100%;object-fit:cover}.art-comment-content{min-width:0}.art-comment-meta{display:flex;align-items:baseline;gap:9px;flex-wrap:wrap}.art-comment-meta strong{color:#344b43;font-size:12px}.art-comment-meta time{color:#9a9097;font-size:10px}.art-comment-text{margin:4px 0 0;color:#625b63;font-size:12px;line-height:1.65;white-space:pre-wrap;overflow-wrap:anywhere}.art-comment-actions button,.art-comment-cancel{border:0;background:none;color:#79546f;padding:5px 0;font-size:11px;font-weight:700;cursor:pointer}.art-comment-actions button:hover,.art-comment-cancel:hover{text-decoration:underline}.art-comment-replies{display:grid;gap:11px;margin:10px 0 0 48px;padding-left:13px;border-left:2px solid #f1e3e9}.art-comment-reply .art-comment-avatar{width:32px;height:32px}.art-comment-form{padding:15px;border:1px solid #ece1dc;border-radius:15px;background:#fdf9f7}.art-comment-form-head{display:flex;align-items:center;justify-content:space-between;gap:8px;color:#344b43;font-size:13px}.art-comment-name-fields{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-top:12px}.art-comment-name-fields label,.art-comment-body-label,.art-comment-photo-label{display:grid;gap:5px;color:#6d626a;font-size:10px;font-weight:600}.art-comment-name-fields input,.art-comment-body-label textarea{width:100%;border:1px solid #e5d9d4;border-radius:9px;background:#fff;padding:9px 10px;color:#3f4843;font:12px Arial,sans-serif}.art-comment-body-label{margin-top:9px}.art-comment-body-label textarea{resize:vertical;min-height:68px}.art-comment-photo-row{display:flex;align-items:center;gap:10px;margin-top:10px}.art-comment-photo-label input{max-width:100%;font-size:10px}.art-comment-status,.art-comment-reply-notice{margin:8px 0 0;color:#79546f;font-size:11px}.art-comment-submit{margin-top:10px;padding:9px 14px;border:0;border-radius:22px;background:#486454;color:#fff;font-size:11px;font-weight:700;cursor:pointer}.art-comment-submit:disabled{opacity:.6;cursor:wait}.art-comments-empty,.art-comments-loading{margin:0;padding:12px 0;color:#827783;font-size:12px}@media(max-width:720px){.art-comment-name-fields{grid-template-columns:1fr}.art-comment-form{padding:12px}.art-comment-replies{margin-left:33px}}';d.head.appendChild(commentStyle)}
    if(!d.__artDetailBound){d.__artDetailBound=true;d.addEventListener('click',function(event){var commentButton=event.target.closest('.comment-button'),inspectButton=event.target.closest('.inspect-btn');if(!commentButton&&!inspectButton)return;event.preventDefault();event.stopImmediatePropagation();var button=commentButton||inspectButton,card=button.closest('.card');var code=card&&(card.dataset.productCode||(card.querySelector('.chip')||{}).textContent||'').trim();var product=(window.__adminProducts||[]).find(function(item){return item.code===code});if(product)openArtworkDetail(d,product,card,window.__adminSettings||{},!!commentButton)},true)}
    var floralStyle=d.getElementById('gallery-floral-accent-style');if(!floralStyle){floralStyle=d.createElement('style');floralStyle.id='gallery-floral-accent-style';floralStyle.textContent=`#yeni-gelenler,#sanatcinin-secimi,#koleksiyonlar{position:relative;background-image:radial-gradient(ellipse at 8% 18%,rgba(247,220,231,.28),transparent 31%),radial-gradient(ellipse at 92% 82%,rgba(221,234,224,.32),transparent 30%)}#yeni-gelenler:before,#sanatcinin-secimi:after,#koleksiyonlar:before{content:'✿';position:absolute;z-index:0;pointer-events:none;opacity:.32;font:clamp(25px,3.3vw,43px)/1 Georgia,serif;color:#70449c;text-shadow:0 7px 18px rgba(75,40,112,.32);animation:ambient-bloom-float 8s ease-in-out infinite alternate}#yeni-gelenler:before{left:clamp(12px,6vw,82px);top:74px}#sanatcinin-secimi:after{right:clamp(12px,6vw,82px);top:90px;color:#70449c;animation-delay:1.3s}#koleksiyonlar:before{right:clamp(14px,5vw,72px);top:56px;color:#70449c;animation-delay:2.1s}@keyframes ambient-bloom-float{from{transform:translate3d(0,0,0) rotate(-9deg)}to{transform:translate3d(0,-10px,0) rotate(9deg)}}@media(max-width:700px){#yeni-gelenler:before,#sanatcinin-secimi:after,#koleksiyonlar:before{font-size:27px;opacity:.58}#yeni-gelenler:before{top:48px;left:10px}#sanatcinin-secimi:after{top:52px;right:10px}#koleksiyonlar:before{top:26px;right:12px}}@media(prefers-reduced-motion:reduce){#yeni-gelenler:before,#sanatcinin-secimi:after,#koleksiyonlar:before{animation:none}}`;d.head.appendChild(floralStyle)}
    var purpleFlowerStyle=d.getElementById('gallery-purple-flower-style');if(!purpleFlowerStyle){purpleFlowerStyle=d.createElement('style');purpleFlowerStyle.id='gallery-purple-flower-style';purpleFlowerStyle.textContent='.ttl svg[aria-hidden="true"] g[fill="#70449c"]{fill:#70449c!important;fill-opacity:1!important}.ttl svg[aria-hidden="true"] g[fill="#70449c"] ellipse{fill:#70449c!important;fill-opacity:1!important}.ttl svg[aria-hidden="true"]{filter:drop-shadow(0 2px 5px rgba(75,40,112,.3))}#yeni-gelenler:before,#sanatcinin-secimi:after,#koleksiyonlar:before{color:#70449c!important;opacity:.62!important;text-shadow:0 2px 8px rgba(75,40,112,.32)!important}';d.head.appendChild(purpleFlowerStyle)}
    if(!d.__galleryCardTemplatesReady){var sampleCards=Array.from(d.querySelectorAll('.card')),sampleTemplates=new Map();sampleCards.forEach(function(card){var chip=card.querySelector('.chip'),code=chip&&chip.textContent.trim();if(code&&!sampleTemplates.has(code))sampleTemplates.set(code,card)});d.__galleryCardTemplates=sampleTemplates;d.__galleryBaseTemplate=sampleCards[0]||null;sampleCards.forEach(function(card){card.remove()});d.__galleryCardTemplatesReady=true;var featuredShell=d.querySelector('.fw');if(featuredShell)featuredShell.hidden=true;var arrivalsShell=d.querySelector('#yeni-gelenler .editorial-grid');if(arrivalsShell&&arrivalsShell.parentElement)arrivalsShell.parentElement.hidden=true;var curatedShell=d.querySelector('#sanatcinin-secimi .curated-grid');if(curatedShell&&curatedShell.parentElement)curatedShell.parentElement.hidden=true;var soldShell=d.querySelector('#sold-works-grid');if(soldShell&&soldShell.parentElement)soldShell.parentElement.hidden=true}
    var sold=d.querySelector('#sold-works-grid');
    if(!d.__galleryViewportWidthReady){var syncGalleryViewportWidth=function(){d.documentElement.style.setProperty('--gallery-viewport-width',(d.documentElement.clientWidth||d.defaultView.innerWidth)+'px')};syncGalleryViewportWidth();d.defaultView.addEventListener('resize',syncGalleryViewportWidth,{passive:true});d.__galleryViewportWidthReady=true}
    var compactSpacing=d.getElementById('compact-card-spacing');if(!compactSpacing){compactSpacing=d.createElement('style');compactSpacing.id='compact-card-spacing';compactSpacing.textContent='.card>.ct>.catalog-description{margin:6px auto 0!important;min-height:0!important;line-height:1.35!important;max-height:2.7em!important}.card>.ct>.catalog-description[hidden]{display:none!important}.card>.ct>.card-actions{margin-top:8px!important}.card>.ct>.like-row{margin-top:4px!important}.fw .ftt>.card>.ct>.catalog-description,.editorial-section .card>.ct>.catalog-description,#yeni-gelenler .editorial-grid>.card>.ct>.catalog-description,#sanatcinin-secimi .curated-grid>.card>.ct>.catalog-description,#sold-works-grid>.card>.ct>.catalog-description,#admin-live-catalog .card>.ct>.catalog-description{margin:6px auto 0!important;min-height:0!important;line-height:1.35!important;max-height:2.7em!important}.fw .ftt>.card>.ct>.catalog-description[hidden],.editorial-section .card>.ct>.catalog-description[hidden],#yeni-gelenler .editorial-grid>.card>.ct>.catalog-description[hidden],#sanatcinin-secimi .curated-grid>.card>.ct>.catalog-description[hidden],#sold-works-grid>.card>.ct>.catalog-description[hidden],#admin-live-catalog .card>.ct>.catalog-description[hidden]{display:none!important}.fw .ftt>.card>.ct>.card-actions,.editorial-section .card>.ct>.card-actions,#yeni-gelenler .editorial-grid>.card>.ct>.card-actions,#sanatcinin-secimi .curated-grid>.card>.ct>.card-actions,#sold-works-grid>.card>.ct>.card-actions,#admin-live-catalog .card>.ct>.card-actions{margin-top:8px!important}';d.head.appendChild(compactSpacing)}
    var socialControls=d.getElementById('gallery-social-controls-style');if(!socialControls){socialControls=d.createElement('style');socialControls.id='gallery-social-controls-style';socialControls.textContent='.like-row{gap:8px!important}.like-actions{gap:5px!important}.like-row .question-button{min-height:29px;padding:6px 10px;background:#fbf1f5;border:1px solid #e8cfda;color:#76516a;font-size:11px}.like-row .like-button,.like-row .comment-button{box-sizing:border-box;min-height:29px;min-width:42px;padding:5px 8px;border:1px solid #eadfe8;border-radius:999px;background:#fffafc;color:#80677c}.like-row .like-button[aria-pressed=true]{background:#fff0f4;color:#d64f79;border-color:#f0cbd9}.like-row .like-button:hover,.like-row .comment-button:hover{background:#f8edf2}.like-row .like-button svg,.like-row .comment-button svg{width:17px;height:17px}.like-row .like-count,.like-row .comment-count{font-size:11px;font-weight:700}@media(max-width:380px){.like-row{gap:4px!important}.like-actions{gap:2px!important}.like-row .question-button{padding:6px 8px;font-size:10px}.like-row .like-button,.like-row .comment-button{min-width:38px;padding:4px 6px}}';d.head.appendChild(socialControls)}
    var carouselStyle=d.getElementById('responsive-featured-carousel');if(!carouselStyle){carouselStyle=d.createElement('style');carouselStyle.id='responsive-featured-carousel';carouselStyle.textContent='@media(max-width:700px){.fw,.fw .ftt{-webkit-mask:none!important;mask:none!important;-webkit-mask-image:none!important;mask-image:none!important;opacity:1!important;filter:none!important}.fw:before,.fw:after,.fw .ftt:before,.fw .ftt:after{content:none!important;display:none!important;background:none!important;opacity:0!important}.fw .ftt>.card{opacity:1!important;filter:none!important;visibility:visible!important}}@media(max-width:700px){#eserler{padding-left:20px!important;padding-right:20px!important}.fw{box-sizing:border-box!important;width:auto!important;max-width:none!important;margin-left:-20px!important;margin-right:-20px!important;padding-left:12px!important;padding-right:12px!important;overflow-x:auto!important;scroll-snap-type:none!important}.fw .ftt{transition:none!important}.fw .ftt>.card{scroll-snap-align:none!important}#eserler .fw{padding-left:12px!important;padding-right:12px!important}#eserler .fw .ftt>.card{flex:0 0 calc((var(--gallery-viewport-width,100vw) - 22px)/2)!important;width:calc((var(--gallery-viewport-width,100vw) - 22px)/2)!important;max-width:calc((var(--gallery-viewport-width,100vw) - 22px)/2)!important;min-width:0!important}#yeni-gelenler,#sanatcinin-secimi,#koleksiyonlar{padding-left:16px!important;padding-right:16px!important}#sold-works-grid{width:calc(var(--gallery-viewport-width,100vw) - 32px)!important;margin-left:auto!important;margin-right:auto!important}#admin-live-catalog{padding-left:16px!important;padding-right:16px!important}.editorial-section .editorial-grid,.editorial-section .curated-grid,#yeni-gelenler .editorial-grid,#sanatcinin-secimi .curated-grid,#koleksiyonlar .collection-art-grid,#sold-works-grid,#admin-live-catalog .admin-catalog-grid{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;grid-auto-rows:1fr!important;justify-content:stretch!important;align-items:stretch!important;gap:12px!important;width:100%!important;max-width:none!important;margin:14px 0 0!important;padding:0!important}.editorial-section .editorial-grid,#yeni-gelenler .editorial-grid,#sanatcinin-secimi .curated-grid,#koleksiyonlar .collection-art-grid,#sold-works-grid,#admin-live-catalog .admin-catalog-grid{grid-template-columns:repeat(2,calc((var(--gallery-viewport-width,100vw) - 22px)/2))!important;grid-auto-rows:1fr!important;gap:12px!important}.editorial-section .editorial-grid>.card,.editorial-section .curated-grid>.card,#yeni-gelenler .editorial-grid>.card,#sanatcinin-secimi .curated-grid>.card,#koleksiyonlar .collection-art-grid>.card,#sold-works-grid>.card,#admin-live-catalog .admin-catalog-grid>.card{display:flex!important;flex:none!important;flex-direction:column!important;width:100%!important;max-width:none!important;min-width:0!important;height:100%!important;justify-self:stretch!important;align-self:stretch!important}.editorial-section .editorial-grid>.card>.ct,.editorial-section .curated-grid>.card>.ct,#yeni-gelenler .editorial-grid>.card>.ct,#sanatcinin-secimi .curated-grid>.card>.ct,#koleksiyonlar .collection-art-grid>.card>.ct,#sold-works-grid>.card>.ct,#admin-live-catalog .admin-catalog-grid>.card>.ct{display:flex!important;flex:1 1 auto!important;flex-direction:column!important}.editorial-section .card .card-actions,#yeni-gelenler .card .card-actions,#sanatcinin-secimi .card .card-actions,#koleksiyonlar .collection-art-grid .card .card-actions,#sold-works-grid .card .card-actions,#admin-live-catalog .card .card-actions{margin-top:auto!important}.fw .ftt>.card{flex:0 0 calc((100vw - 44px)/2)!important;width:calc((100vw - 44px)/2)!important;min-width:0!important;max-width:calc((100vw - 44px)/2)!important}.fw .art.has-art-backdrop,.editorial-section .art.has-art-backdrop,#yeni-gelenler .art.has-art-backdrop,#sanatcinin-secimi .art.has-art-backdrop,#koleksiyonlar .collection-art-grid .art.has-art-backdrop,#sold-works-grid .art.has-art-backdrop,#admin-live-catalog .art.has-art-backdrop{position:relative!important;isolation:isolate!important;overflow:hidden!important;background-color:#eeeae6!important}.fw .art.has-art-backdrop:before,.editorial-section .art.has-art-backdrop:before,#yeni-gelenler .art.has-art-backdrop:before,#sanatcinin-secimi .art.has-art-backdrop:before,#koleksiyonlar .collection-art-grid .art.has-art-backdrop:before,#sold-works-grid .art.has-art-backdrop:before,#admin-live-catalog .art.has-art-backdrop:before{content:""!important;display:block!important;position:absolute!important;inset:-12px!important;z-index:0!important;background-image:var(--art-backdrop)!important;background-size:cover!important;background-position:center!important;filter:blur(15px)!important;opacity:.72!important;transform:scale(1.08)!important;border-radius:inherit!important;pointer-events:none!important}.fw .art.has-art-backdrop>img,.editorial-section .art.has-art-backdrop>img,#yeni-gelenler .art.has-art-backdrop>img,#sanatcinin-secimi .art.has-art-backdrop>img,#koleksiyonlar .collection-art-grid .art.has-art-backdrop>img,#sold-works-grid .art.has-art-backdrop>img,#admin-live-catalog .art.has-art-backdrop>img{position:absolute!important;inset:0!important;z-index:3!important;width:100%!important;height:100%!important;object-fit:contain!important;background:transparent!important;filter:none!important;-webkit-filter:none!important;backdrop-filter:none!important;-webkit-backdrop-filter:none!important}.fw .ftt>.card,.editorial-section .editorial-grid>.card,#yeni-gelenler .editorial-grid>.card,#sanatcinin-secimi .curated-grid>.card,#koleksiyonlar .collection-art-grid>.card,#sold-works-grid>.card,#admin-live-catalog .admin-catalog-grid>.card{padding:7px!important;border-radius:15px!important}.fw .ftt>.card>.art,.editorial-section .editorial-grid>.card>.art,#yeni-gelenler .editorial-grid>.card>.art,#sanatcinin-secimi .curated-grid>.card>.art,#koleksiyonlar .collection-art-grid>.card>.art,#sold-works-grid>.card>.art,#admin-live-catalog .admin-catalog-grid>.card>.art{aspect-ratio:3/4!important;border-radius:11px!important}.fw .ftt>.card>.ct,.editorial-section .editorial-grid>.card>.ct,#yeni-gelenler .editorial-grid>.card>.ct,#sanatcinin-secimi .curated-grid>.card>.ct,#koleksiyonlar .collection-art-grid>.card>.ct,#sold-works-grid>.card>.ct,#admin-live-catalog .admin-catalog-grid>.card>.ct{padding:8px 3px 5px!important}.fw .ftt>.card>.ct>b,.editorial-section .editorial-grid>.card>.ct>b,#yeni-gelenler .editorial-grid>.card>.ct>b,#sanatcinin-secimi .curated-grid>.card>.ct>b,#koleksiyonlar .collection-art-grid>.card>.ct>b,#sold-works-grid>.card>.ct>b,#admin-live-catalog .admin-catalog-grid>.card>.ct>b{font-size:14px!important;line-height:17.5px!important}.fw .ftt>.card>.ct>span:not(.pr):not(.catalog-description),.editorial-section .editorial-grid>.card>.ct>span:not(.pr):not(.catalog-description),#yeni-gelenler .editorial-grid>.card>.ct>span:not(.pr):not(.catalog-description),#sanatcinin-secimi .curated-grid>.card>.ct>span:not(.pr):not(.catalog-description),#koleksiyonlar .collection-art-grid>.card>.ct>span:not(.pr):not(.catalog-description),#sold-works-grid>.card>.ct>span:not(.pr):not(.catalog-description),#admin-live-catalog .admin-catalog-grid>.card>.ct>span:not(.pr):not(.catalog-description){font-size:11px!important;line-height:15px!important}.fw .ftt>.card>.ct>.pr,.editorial-section .editorial-grid>.card>.ct>.pr,#yeni-gelenler .editorial-grid>.card>.ct>.pr,#sanatcinin-secimi .curated-grid>.card>.ct>.pr,#koleksiyonlar .collection-art-grid>.card>.ct>.pr,#sold-works-grid>.card>.ct>.pr,#admin-live-catalog .admin-catalog-grid>.card>.ct>.pr{font-size:14px!important;line-height:16px!important;margin:4px 0 7px!important}.fw .ftt>.card>.ct>.catalog-description,.editorial-section .editorial-grid>.card>.ct>.catalog-description,#yeni-gelenler .editorial-grid>.card>.ct>.catalog-description,#sanatcinin-secimi .curated-grid>.card>.ct>.catalog-description,#koleksiyonlar .collection-art-grid>.card>.ct>.catalog-description,#sold-works-grid>.card>.ct>.catalog-description,#admin-live-catalog .admin-catalog-grid>.card>.ct>.catalog-description{font-size:11px!important;line-height:15.95px!important;margin:8px 0 12px!important}.fw .ftt>.card .card-actions .btn,.editorial-section .editorial-grid>.card .card-actions .btn,#yeni-gelenler .editorial-grid>.card .card-actions .btn,#sanatcinin-secimi .curated-grid>.card .card-actions .btn,#koleksiyonlar .collection-art-grid>.card .card-actions .btn,#sold-works-grid>.card .card-actions .btn,#admin-live-catalog .admin-catalog-grid>.card .card-actions .btn{height:34px!important;min-height:34px!important;padding:7px 4px!important;font-size:11px!important;line-height:normal!important}}.fw.is-static .ftt[data-loop-copies="1"]{animation:none!important;transform:none!important;width:100%!important;justify-content:center!important;flex-wrap:wrap!important}@keyframes admin-featured-drift{from{transform:translateX(0)}to{transform:translateX(var(--featured-distance,0px))}}.fw.is-static .prev-default,.fw.is-static .next-default{display:none!important}.fw.is-manual .ftt{animation:none!important;transition:none!important}.card:hover,.card:active,.card:focus-within,.product-card:hover,.product-card:active,.product-card:focus-within,.fw .ftt>.card{transform:none!important;transition:none!important;animation:none!important;filter:none!important}.fw .ftt>.card:hover{box-shadow:0 8px 28px rgba(200,120,160,.16)!important}.fw .ftt>.card{touch-action:pan-x pan-y;-webkit-tap-highlight-color:transparent}.all-works-section{max-width:1160px;margin:48px auto 60px;padding:30px 24px;background:#fffdf9;border:1px solid #efe4dd;border-radius:22px;box-shadow:0 12px 35px #5441370b}.all-works-filter{display:flex;align-items:center;justify-content:center;flex-wrap:wrap;gap:10px;margin:0 auto 18px}.all-works-filter label{font-size:13px;color:#665c61}.all-works-filter select{min-width:220px;border:1px solid #e0d6d1;border-radius:999px;padding:10px 16px;background:#fff;color:#4b514e}.category-manager{border:1px solid #e8ddd7;border-radius:14px;padding:16px;margin:6px 0 18px}.category-manager legend,.size-choice legend,.category-checks legend{padding:0 8px;color:#4b514e;font-weight:700}.category-setting-row{display:flex;gap:9px;margin:8px 0}.category-setting-row input{flex:1;min-width:0}.size-choice{display:flex;align-items:end;gap:10px;border:1px solid #e8ddd7;border-radius:12px;padding:14px}.size-choice label{flex:1;display:grid;gap:6px}.size-choice input,.size-choice select{border:1px solid #e0d6d1;background:#fffdfb;border-radius:10px;padding:10px;width:100%}.size-x{padding-bottom:8px}.category-checks{display:flex;gap:16px;flex-wrap:wrap;border:1px solid #e8ddd7;border-radius:12px;padding:14px}.category-checks label{display:inline-flex;gap:7px;align-items:center}.code-input-row input{flex:1;min-width:0}.copy-code{border:0;border-radius:14px;background:#f6edf1;color:#704c67;font-size:11px;padding:5px 8px;cursor:pointer}.copy-code:hover{background:#ead9e2}@media(max-width:650px){.size-choice{flex-wrap:wrap}.all-works-section{margin:28px 12px;padding:20px 12px}}';d.head.appendChild(carouselStyle)}
    
    var cardLayoutC=d.getElementById('gallery-card-layout-c');if(!cardLayoutC){cardLayoutC=d.createElement('style');cardLayoutC.id='gallery-card-layout-c'}cardLayoutC.textContent='#top .card{box-sizing:border-box!important;height:auto!important;min-height:0!important;display:flex!important;flex-direction:column!important}#top .card>.art,#top .card>.art-frame{box-sizing:border-box!important;width:100%!important;height:154px!important;min-height:0!important;max-height:none!important;aspect-ratio:auto!important;flex:0 0 154px!important;overflow:hidden!important;border-radius:12px!important;background:#f2eee9!important}#top .card>.art.has-art-backdrop:before,#top .card>.art.has-art-backdrop:after{display:none!important;content:none!important}#top .card>.art img,#top .card>.art-frame img{object-fit:contain!important}#top .card>.ct{box-sizing:border-box!important;width:100%!important;display:grid!important;grid-template-columns:minmax(0,1fr) auto!important;grid-auto-rows:auto!important;grid-auto-flow:row!important;align-content:start!important;align-items:center!important;gap:4px 8px!important;padding:8px 10px 7px!important;flex:0 0 auto!important;min-height:0!important;text-align:left!important}#top .card>.ct>.work-code-badge{position:static!important;top:auto!important;left:auto!important;grid-column:1/-1!important;grid-row:1!important;width:max-content!important;max-width:100%;padding:4px 7px!important;margin:0!important;border:1px solid #ead9e1!important;border-radius:999px!important;background:#fbf1f5!important;color:#79546f!important;font:700 9px/1 Arial,sans-serif!important;letter-spacing:.08em!important;box-shadow:none!important}#top .card>.ct>.sf{grid-column:1!important;grid-row:2!important;min-width:0!important;margin:0!important;text-align:left!important;font-size:15px!important;line-height:1.2!important}#top .card>.ct>span:not(.pr):not(.catalog-description):not(.work-code-badge){grid-column:1!important;grid-row:3!important;min-width:0!important;margin:0!important;text-align:left!important;color:#827783!important;font-size:11px!important;line-height:1.2!important}#top .card>.ct>.pr{grid-column:2!important;grid-row:2/4!important;justify-self:end!important;align-self:center!important;margin:0!important;text-align:right!important;white-space:nowrap!important;font-size:14px!important;line-height:1.15!important}#top .card>.ct>.catalog-description{grid-column:1/-1!important;grid-row:auto!important;margin:2px 0 0!important;min-height:0!important;max-height:2.7em!important;text-align:left!important;line-height:1.3!important}#top .card>.ct>.catalog-description[hidden]{display:none!important}#top .card>.ct>.card-actions{grid-column:1/-1!important;grid-row:auto!important;display:flex!important;grid-template-columns:none!important;width:100%!important;gap:6px!important;margin-top:3px!important}#top .card>.ct>.card-actions>.btn{box-sizing:border-box!important;min-width:0!important;min-height:34px!important;flex:1 1 0!important;padding:6px 7px!important}#top .card>.ct>.like-row{grid-column:1/-1!important;grid-row:auto!important;display:flex!important;flex-wrap:nowrap!important;align-items:center!important;justify-content:space-between!important;gap:4px!important;width:100%!important;margin-top:0!important;padding-top:0!important}#top .card>.ct>.like-row .question-button{min-height:28px!important;padding:5px 8px!important;font-size:10px!important}#top .card>.ct>.like-row .like-actions{gap:2px!important;margin-left:auto!important}#top .card>.ct>.like-row .like-button,#top .card>.ct>.like-row .comment-button{min-width:34px!important;min-height:30px!important;padding:4px 6px!important;gap:3px!important}#top .card>.ct>.like-row .like-button svg,#top .card>.ct>.like-row .comment-button svg{width:15px!important;height:15px!important}#top .card>.ct>.like-row .like-count,#top .card>.ct>.like-row .comment-count{font-size:10px!important}#top .editorial-section .editorial-grid,#top .editorial-section .curated-grid,#top #yeni-gelenler .editorial-grid,#top #sanatcinin-secimi .curated-grid,#top #sold-works-grid,#top #admin-live-catalog .admin-catalog-grid{grid-template-columns:repeat(auto-fit,minmax(240px,262px))!important;justify-content:center!important;gap:18px!important}#top .editorial-section .card,#top #yeni-gelenler .editorial-grid>.card,#top #sanatcinin-secimi .curated-grid>.card,#top #sold-works-grid>.card,#top #admin-live-catalog .admin-catalog-grid>.card{width:262px!important;max-width:262px!important;min-width:0!important;justify-self:center!important}#top .fw .ftt>.card{box-sizing:border-box!important;flex:0 0 262px!important;width:262px!important;min-width:262px!important;max-width:262px!important}@media(max-width:700px){#top .card>.art,#top .card>.art-frame{height:126px!important;flex-basis:126px!important}#top .card>.ct{gap:4px 6px!important;padding:7px 8px 6px!important}#top .card>.ct>.sf{font-size:13px!important}#top .card>.ct>.pr{font-size:12px!important}#top .card>.ct>.card-actions{gap:5px!important;margin-top:2px!important}#top .card>.ct>.card-actions>.btn{min-height:30px!important;padding:5px 4px!important;font-size:10px!important}#top .card>.ct>.like-row{gap:3px!important}#top .card>.ct>.like-row .question-button{min-height:26px!important;padding:4px 6px!important;font-size:9px!important}#top .card>.ct>.like-row .like-button,#top .card>.ct>.like-row .comment-button{min-width:32px!important;min-height:28px!important;padding:3px 4px!important}#top .editorial-section .editorial-grid,#top .editorial-section .curated-grid,#top #yeni-gelenler .editorial-grid,#top #sanatcinin-secimi .curated-grid,#top #sold-works-grid,#top #admin-live-catalog .admin-catalog-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:10px!important}#top .editorial-section .card,#top #yeni-gelenler .editorial-grid>.card,#top #sanatcinin-secimi .curated-grid>.card,#top #sold-works-grid>.card,#top #admin-live-catalog .admin-catalog-grid>.card{width:100%!important;max-width:none!important;min-width:0!important;justify-self:stretch!important}#top .fw .ftt>.card{flex:0 0 calc((var(--gallery-viewport-width,100vw) - 22px)/2)!important;width:calc((var(--gallery-viewport-width,100vw) - 22px)/2)!important;max-width:calc((var(--gallery-viewport-width,100vw) - 22px)/2)!important;min-width:0!important}#top #sold-works-grid{width:calc(var(--gallery-viewport-width,100vw) - 32px)!important;margin-left:auto!important;margin-right:auto!important}}@media(max-width:360px){#top .card>.ct>.like-row{flex-wrap:wrap!important}#top .card>.ct>.like-row .question-button{font-size:10px!important;padding-inline:8px!important}}';if(cardLayoutC.parentElement!==d.body)d.body.appendChild(cardLayoutC)
    var section=d.createElement('section');section.id='admin-live-catalog';section.className='all-works-section';section.hidden=false;section.style.display='block';section.innerHTML='<header class="section-heading"><span class="eyebrow">ATÖLYEDEN TÜM ÇALIŞMALAR</span><h2>Tüm Eserler</h2><p>Atölyedeki eserleri ada veya eser koduna göre bulun.</p><label class="catalog-search" for="all-works-search"><span>Eser ara</span><input id="all-works-search" type="search" autocomplete="off" placeholder="Eser adı veya PB kodu" aria-controls="all-works-grid" aria-describedby="all-works-count"></label><p id="all-works-count" class="catalog-search-count" role="status" aria-live="polite"></p></header><div id="all-works-grid" class="admin-catalog-grid"></div><p id="all-works-empty" class="catalog-search-empty" hidden></p>';var contentAnchor=d.getElementById('sanatcinin-secimi')||d.querySelector('.editorial-section .curated-grid')&&d.querySelector('.editorial-section .curated-grid').closest('.editorial-section')||d.getElementById('yeni-gelenler')||d.getElementById('eserler');if(contentAnchor&&contentAnchor.parentNode)contentAnchor.parentNode.insertBefore(section,contentAnchor.nextSibling);else d.body.appendChild(section)
    if(!d.__galleryLikesBound){d.__galleryLikesBound=true;d.addEventListener('click',function(e){var b=e.target.closest('.like-button');if(!b||b.disabled)return;e.preventDefault();var code=b.dataset.likeCode,liked=b.dataset.liked!=='1';b.disabled=true;fetch('/api/likes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:code,visitor:likeVisitor,liked:liked})}).then(function(r){if(!r.ok)throw Error('like');return r.json()}).then(function(result){setLikeState(d,result.code,result)}).catch(function(){b.disabled=false}).finally(function(){b.disabled=false})},true);fetch('/api/likes?visitor='+encodeURIComponent(likeVisitor),{cache:'no-store'}).then(function(r){if(!r.ok)throw Error('likes');return r.json()}).then(function(data){Object.keys(data.likes||{}).forEach(function(code){setLikeState(d,code,data.likes[code])})}).catch(function(){})}
    if(!d.__gallerySharesBound){d.__gallerySharesBound=true;d.addEventListener('click',function(e){var b=e.target.closest('.share-button');if(!b||b.disabled)return;e.preventDefault();var code=b.dataset.shareCode||'',product=(window.__adminProducts||[]).find(function(item){return item.code===code});if(!code||!product)return;var url=new URL('/',d.location.href);url.searchParams.set('eser',code);var shareUrl=url.href,navigatorRef=d.defaultView.navigator,pending=window.__gallerySharePending||(window.__gallerySharePending={});if(pending[code])return;pending[code]=true;Array.from(d.querySelectorAll('.share-button')).filter(function(button){return button.dataset.shareCode===code}).forEach(function(button){button.disabled=true});function recordShare(){return fetch('/api/shares',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:code})}).then(function(response){return response.json().then(function(data){if(!response.ok)throw new Error(data.error||'Paylaşım kaydedilemedi.');return data})}).then(function(result){window.__publicShareCounts=window.__publicShareCounts||{};window.__publicShareCounts[code]=result.count;setShareCount(d,code,result.count);showShareFeedback(d,'Eser bağlantısı paylaşıldı.')})}function copyLink(){var clipboard=navigatorRef&&navigatorRef.clipboard;if(clipboard&&clipboard.writeText){clipboard.writeText(shareUrl).then(function(){return recordShare()}).then(function(){showShareFeedback(d,'Eser bağlantısı kopyalandı.')}).catch(function(){var accepted=d.defaultView.prompt('Eser bağlantısını kopyalayın:',shareUrl);if(accepted!==null)recordShare().catch(function(){showShareFeedback(d,'Paylaşım sayısı kaydedilemedi.')})})}else{var accepted=d.defaultView.prompt('Eser bağlantısını kopyalayın:',shareUrl);if(accepted!==null)recordShare().catch(function(){showShareFeedback(d,'Paylaşım sayısı kaydedilemedi.')})}}try{if(navigatorRef&&typeof navigatorRef.share==='function'){Promise.resolve(navigatorRef.share({title:product.title||'Sanat Atölyesi eseri',text:(product.code||code)+' kodlu esere göz atın.',url:shareUrl})).then(function(){return recordShare()}).catch(function(error){if(error&&error.name==='AbortError')return;copyLink()})}else copyLink()}catch(error){copyLink()}setTimeout(function(){pending[code]=false;Array.from(d.querySelectorAll('.share-button')).filter(function(button){return button.dataset.shareCode===code}).forEach(function(button){button.disabled=false})},1200)},true)}
    if(!d.__galleryCommentCountsLoaded){d.__galleryCommentCountsLoaded=true;fetch('/api/comments?counts=1',{cache:'no-store'}).then(function(r){if(!r.ok)throw Error('comments');return r.json()}).then(function(data){Object.keys(data.counts||{}).forEach(function(code){setCommentCount(d,code,data.counts[code])})}).catch(function(){})}
    d.addEventListener('click',function(e){var arrow=e.target.closest('[data-featured-step]');if(!arrow)return;e.preventDefault();e.stopImmediatePropagation();var track=d.querySelector('.fw .ftt'),root=track&&track.closest('.fw'),first=track&&track.children[0];if(!track||!root||!first)return;var direction=Number(arrow.dataset.featuredStep)>0?1:-1,gap=parseFloat(d.defaultView.getComputedStyle(track).columnGap)||parseFloat(d.defaultView.getComputedStyle(track).gap)||12,step=first.getBoundingClientRect().width+gap,distance=root.__featuredLoopDistance||0,next=root.scrollLeft+direction*step;if(distance>0){if(next>=distance)next-=distance;if(next<0)next+=distance}else next=Math.max(0,Math.min(next,root.scrollWidth-root.clientWidth));root.__featuredResumeAt=d.defaultView.performance.now()+1000;root.scrollTo({left:next,behavior:'smooth'})},true);
    }
    function ensureAllWorks(d){var section=d.getElementById('admin-live-catalog');if(!section){section=d.createElement('section');section.id='admin-live-catalog';section.className='all-works-section';section.innerHTML='<header class=\"section-heading\"><span class=\"eyebrow\">ATÖLYEDEN TÜM ÇALIŞMALAR</span><h2>Tüm Eserler</h2><p>Atölyedeki eserleri ada veya eser koduna göre bulun.</p><label class=\"catalog-search\" for=\"all-works-search\"><span>Eser ara</span><input id=\"all-works-search\" type=\"search\" autocomplete=\"off\" placeholder=\"Eser adı veya PB kodu\" aria-controls=\"all-works-grid\" aria-describedby=\"all-works-count\"></label><p id=\"all-works-count\" class=\"catalog-search-count\" role=\"status\" aria-live=\"polite\"></p></header><div id=\"all-works-grid\" class=\"admin-catalog-grid\"></div><p id=\"all-works-empty\" class=\"catalog-search-empty\" hidden></p>'}var search=section.querySelector('#all-works-search');if(search&&!search.dataset.searchBound){search.addEventListener('input',function(){applyCatalogSearch(d)});search.dataset.searchBound='1'}function removeFilterControls(){var filterDetails=Array.from(d.querySelectorAll('details')).filter(function(x){var summary=x.querySelector('summary');var text=summary?summary.textContent.trim().toLocaleLowerCase('tr'):'';return text.startsWith('kategori')||text.startsWith('fiyat')||text.startsWith('sırala')});if(filterDetails.length){var controls=filterDetails[0].parentElement&&filterDetails[0].parentElement.parentElement;if(controls&&controls!==d.body&&controls!==d.documentElement)controls.remove()}}function place(){var anchor=d.getElementById('sanatcinin-secimi');if(!anchor){var sections=Array.from(d.querySelectorAll('.editorial-section'));anchor=sections.find(function(node){return !!node.querySelector('.curated-grid')})||null}if(!anchor)anchor=d.getElementById('yeni-gelenler')||d.getElementById('eserler');if(anchor&&anchor.parentNode){if(section.parentNode!==anchor.parentNode||section.previousElementSibling!==anchor)anchor.parentNode.insertBefore(section,anchor.nextSibling);return true}if(section.parentNode!==d.body)d.body.appendChild(section);return false}removeFilterControls();place();if(d.body&&!d.__galleryLayoutObserver&&d.defaultView&&d.defaultView.MutationObserver){var observer=new d.defaultView.MutationObserver(function(){removeFilterControls();place()});observer.observe(d.body,{childList:true,subtree:true});d.__galleryLayoutObserver=observer}}
    function ensureFooterStats(d){var style=d.getElementById('gallery-footer-stats-style');if(!style){style=d.createElement('style');style.id='gallery-footer-stats-style';style.textContent='.gallery-footer-stats{max-width:1100px;margin:24px auto 36px;padding:24px clamp(14px,4vw,40px);border:1px solid #eadfd8;border-radius:20px;background:linear-gradient(135deg,#fffaf7,#f7f1ed);text-align:center}.gallery-footer-stats h2{margin:0 0 6px;color:#3f5a46;font:600 clamp(20px,2.4vw,28px) Georgia,serif}.gallery-footer-stats>p{margin:0;color:#827783;font-size:12px}.gallery-footer-stats-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:18px}.gallery-footer-stat{display:grid;gap:5px;padding:14px 8px;border-radius:14px;background:#fffdfb}.gallery-footer-stat strong{color:#79546f;font:700 clamp(21px,3vw,30px) Georgia,serif}.gallery-footer-stat span{color:#827783;font-size:11px}@media(max-width:520px){.gallery-footer-stats{margin:18px 12px 28px;padding:20px 10px}.gallery-footer-stats-grid{gap:7px}.gallery-footer-stat{padding:12px 4px}.gallery-footer-stat span{font-size:10px}}';d.head.appendChild(style)}var section=d.getElementById('gallery-footer-stats');if(!section){section=d.createElement('section');section.id='gallery-footer-stats';section.className='gallery-footer-stats';section.innerHTML='<h2>Atölyenin bugüne kadarki yolculuğu</h2><p>Her ziyaret ve her eser bu hikâyenin bir parçası.</p><div class="gallery-footer-stats-grid"><div class="gallery-footer-stat"><strong data-gallery-stat="visitors">—</strong><span>Tekil ziyaretçi</span></div><div class="gallery-footer-stat"><strong data-gallery-stat="sold">—</strong><span>Satılan eser</span></div><div class="gallery-footer-stat"><strong data-gallery-stat="available">—</strong><span>Yayındaki eser</span></div></div>';d.body.appendChild(section)}if(section.__statsLoaded)return;section.__statsLoaded=true;fetch('/api/stats',{cache:'no-store'}).then(function(response){if(!response.ok)throw Error('stats');return response.json()}).then(function(data){Object.keys(data).forEach(function(key){var node=section.querySelector('[data-gallery-stat="'+key+'"]');if(node)node.textContent=Number(data[key]||0).toLocaleString('tr-TR')})}).catch(function(){section.__statsLoaded=false})}
    function cardTemplate(d,p){var all=Array.from(d.querySelectorAll('.card')),found=all.find(function(x){var chip=x.querySelector('.chip');return chip&&chip.textContent.trim()===p.code});return found||d.__galleryCardTemplates&&d.__galleryCardTemplates.get(p.code)||d.__galleryBaseTemplate||all[0]}
    function paint(d,card,p,cfg){ensureUnifiedCardStyle(d);card.classList.add('gallery-work-card');card.hidden=false;card.style.flex='0 0 240px';card.style.display='flex';card.style.flexDirection='column';var galleryCardHeight=d.documentElement.clientWidth<=700?'310px':'354px';card.style.setProperty('height',galleryCardHeight,'important');card.style.setProperty('min-height',galleryCardHeight,'important');card.dataset.productCode=p.code;var chip=card.querySelector('.work-code-badge')||card.querySelector('.chip'),artForBadge=card.querySelector('.art')||card.querySelector('.art-frame');if(artForBadge){artForBadge.style.position='relative';artForBadge.setAttribute('data-work-code',p.code)}if(chip){chip.textContent=p.code;chip.classList.add('work-code-badge')}var title=card.querySelector('.ct .sf');if(title)title.textContent=p.title;var ct=card.querySelector('.ct');if(ct){if(chip)ct.insertBefore(chip,ct.firstChild);ct.style.display='grid';ct.style.gridTemplateColumns='minmax(0,1fr) auto';ct.style.flexDirection='column';ct.style.flex='1 1 auto';ct.style.minHeight='0';ct.style.gap='4px 8px';ct.style.textAlign='left';var size=ct.querySelector('span:not(.pr)');if(size)size.textContent=p.size;var price=ct.querySelector('.pr');if(price){price.replaceChildren();if(p.sale_price&&Number(p.sale_price)<Number(p.price)){var old=d.createElement('del');old.textContent=fmt(p.price);price.appendChild(old);price.appendChild(d.createTextNode(' '))}var current=d.createElement('b');current.textContent=fmt(p.sale_price&&Number(p.sale_price)<Number(p.price)?p.sale_price:p.price);price.appendChild(current)}var desc=ct.querySelector('.catalog-description');if(!desc){desc=d.createElement('span');desc.className='catalog-description';desc.style.cssText='display:block;margin:2px 0 0;max-width:100%;color:#827783;font-size:11px;line-height:1.3;text-align:left;min-height:0';var actions=ct.querySelector('.card-actions');ct.insertBefore(desc,actions||null)}desc.textContent=(p.description||'').trim();desc.hidden=!desc.textContent;var actions=ct.querySelector('.card-actions');if(actions){actions.replaceChildren();actions.style.setProperty('margin-top','4px','important');if(p.sold){var sold=d.createElement('span');sold.className='btn g sold-tag';sold.textContent='Satıldı';actions.appendChild(sold)}else{var buy=d.createElement('a');buy.className='btn g';buy.href=p.whatsapp_url||cfg.whatsapp_url||'#iletisim';buy.textContent='Satın Al';if(buy.href.indexOf('http')===0){buy.target='_blank';buy.rel='noopener'}actions.appendChild(buy)}var inspect=d.createElement('button');inspect.type='button';inspect.className='btn inspect-btn';inspect.textContent='İncele';actions.appendChild(inspect)}}var art=card.querySelector('.art');if(art){if(p.image){var img=art.querySelector('img');if(!img){art.replaceChildren();img=d.createElement('img');img.style.cssText='position:relative;width:100%;height:100%;object-fit:contain;background:transparent;border-radius:inherit';art.appendChild(img)}img.src='/'+p.image;img.alt=p.title;art.classList.add('has-art-backdrop');art.style.setProperty('--art-backdrop','url("'+img.src.replace(/"/g,'%22')+'")')}else if(art.querySelector('img')){art.querySelector('img').remove();art.classList.remove('has-art-backdrop');art.style.removeProperty('--art-backdrop')}}if(ct){var codeBadge=ct.querySelector('.work-code-badge');if(!codeBadge){codeBadge=d.createElement('span');codeBadge.className='work-code-badge';ct.insertBefore(codeBadge,ct.firstChild)}codeBadge.textContent=p.code}ensureLikeRow(d,card,p,cfg);var likeRow=ct&&ct.querySelector('.like-row');if(likeRow)likeRow.style.marginTop='4px'}
    function fmt(n){return '₺'+Number(n||0).toLocaleString('tr-TR')}
    function applyCatalogSearch(d){var section=d.getElementById('admin-live-catalog'),grid=section&&section.querySelector('.admin-catalog-grid'),search=section&&section.querySelector('#all-works-search');if(!grid||!search)return;var normalize=function(value){return String(value||'').toLocaleLowerCase('tr-TR').replace(/ı/g,'i').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/g,' ').trim()},query=normalize(search.value),terms=query.split(/\\s+/).filter(Boolean),codeQuery=/^(?:pb\\s*)?[0-9]+$/.test(query),cards=Array.from(grid.children),visible=0;cards.forEach(function(card){var title=card.querySelector('.ct .sf'),titleWords=normalize(title?title.textContent:'').split(/\\s+/).filter(Boolean),codeDigits=String(card.dataset.productCode||'').replace(/[^0-9]/g,''),matches=!terms.length||(codeQuery?codeDigits.indexOf(query.replace(/^pb\\s*/, '').replace(/\\s/g,''))!==-1:terms.every(function(term){return titleWords.some(function(word){return word.indexOf(term)===0})}));card.hidden=!matches;if(matches)visible++});var count=section.querySelector('#all-works-count'),empty=section.querySelector('#all-works-empty');if(count)count.textContent=query?visible+' eser bulundu':cards.length+' eser';if(empty){empty.hidden=visible>0;empty.textContent=query?'Bu aramayla eşleşen eser bulunamadı.':'Henüz yayımlanmış eser yok.'}}
    function renderCatalog(d,products,templates){var rows=products.filter(function(p){return !p.archived&&p.published!==false}).sort(function(a,b){return b.id-a.id}),grid=d.querySelector('#admin-live-catalog .admin-catalog-grid');if(!grid)return;var base=templates.values().next().value||d.querySelector('.card');if(base)grid.replaceChildren.apply(grid,rows.map(function(p){var clone=(templates.get(p.code)||base).cloneNode(true);paint(d,clone,p,window.__adminSettings||{});return clone}));applyCatalogSearch(d)}
    function renderAbout(d,cfg){var section=d.getElementById('hakkimda');if(!section)return;var style=d.getElementById('artist-about-style');if(!style){style=d.createElement('style');style.id='artist-about-style';style.textContent='.foot#hakkimda{text-align:left!important;padding:clamp(34px,6vw,76px) clamp(18px,5vw,64px) 38px!important;background:linear-gradient(135deg,#f9edf0 0%,#fbf8f3 54%,#eef2ec 100%)!important}.artist-about-content{max-width:1120px;margin:0 auto 26px}.artist-about-layout{display:grid;min-width:0;grid-template-columns:minmax(0,.88fr) minmax(0,1.12fr);align-items:center;gap:clamp(24px,5vw,62px);padding:clamp(18px,3vw,30px);border:1px solid rgba(224,207,203,.8);border-radius:26px;background:rgba(255,253,250,.82);box-shadow:0 20px 55px rgba(77,57,56,.08)}.artist-about-photo{position:relative;width:100%;min-width:0;min-height:0;height:auto;aspect-ratio:4/3;overflow:hidden;border-radius:19px;background:linear-gradient(145deg,#ead4dd,#f8eddf 55%,#dce8dc);box-shadow:0 12px 30px rgba(71,54,52,.13)}.artist-about-photo img{position:absolute;inset:0;width:100%;max-width:100%;height:100%;object-fit:cover}.artist-about-placeholder{position:absolute;inset:0;display:grid;place-items:center;color:#d88eaa;font:120px/1 Georgia,serif;text-shadow:0 9px 24px rgba(121,84,111,.16)}.artist-about-copy{min-width:0;overflow-wrap:anywhere}.artist-about-copy .eyebrow{font:700 10px/1.5 Arial,sans-serif;letter-spacing:.2em;color:#a5637e}.artist-about-copy h2{margin:10px 0 17px;color:#344b43;font:600 clamp(28px,4vw,46px)/1.12 Georgia,serif}.artist-about-copy p{margin:0 0 13px;color:#706773;font:15px/1.85 Arial,sans-serif;white-space:pre-wrap}.artist-about-contact{display:flex!important;width:max-content;margin:0 auto 20px!important;text-align:center}.foot#hakkimda>.soc{display:flex;justify-content:center;flex-wrap:wrap;margin:0 auto!important}@media(max-width:700px){.foot#hakkimda{padding:30px 16px 32px!important}.artist-about-layout{grid-template-columns:1fr;gap:18px;padding:13px;border-radius:20px}.artist-about-photo{width:100%;min-height:0;height:auto;aspect-ratio:4/3}.artist-about-copy{padding:2px 5px 6px}.artist-about-copy h2{font-size:30px}.artist-about-copy p{font-size:14px;line-height:1.75}.artist-about-placeholder{font-size:94px}}';d.head.appendChild(style)}var content=d.getElementById('artist-about-content');if(!content){content=d.createElement('div');content.id='artist-about-content';content.className='artist-about-content';section.insertBefore(content,section.firstChild)}var aboutSignature=JSON.stringify([cfg.site_name||'',cfg.about_heading||'',cfg.about_text||'',cfg.about_image||'']);if(content.dataset.aboutSignature!==aboutSignature){var layout=d.createElement('div');layout.className='artist-about-layout';var photo=d.createElement('div');photo.className='artist-about-photo';if(cfg.about_image){var img=d.createElement('img');img.src='/'+String(cfg.about_image).replace(/^[/]+/, '');img.alt=(cfg.site_name||'Sanatçı')+' atölyesinde';img.loading='lazy';photo.appendChild(img)}else{var placeholder=d.createElement('div');placeholder.className='artist-about-placeholder';placeholder.setAttribute('role','img');placeholder.setAttribute('aria-label','Sanat atölyesini temsil eden çiçek');placeholder.textContent='✿';photo.appendChild(placeholder)}var copy=d.createElement('div');copy.className='artist-about-copy';var label=d.createElement('span');label.className='eyebrow';label.textContent='SANATÇININ HİKÂYESİ';var title=d.createElement('h2');title.textContent=cfg.about_heading||'Sanatla İç İçe Bir Yaşam';copy.appendChild(label);copy.appendChild(title);String(cfg.about_text||'Sanat benim için renkleri, anıları ve doğadan aldığım ilhamı tuvale taşımak. Her eserimi atölyemde sabırla ve özenle hazırlıyorum.').split(String.fromCharCode(10)).forEach(function(line){var value=line.trim();if(!value)return;var p=d.createElement('p');p.textContent=value;copy.appendChild(p)});layout.appendChild(photo);layout.appendChild(copy);content.replaceChildren(layout);content.dataset.aboutSignature=aboutSignature}var cta=section.querySelector('.btn.g');if(cta){cta.classList.add('artist-about-contact');cta.textContent='Atölyeyle İletişime Geç';var contactUrl=String(cfg.whatsapp_url||'').trim();if(contactUrl.indexOf('https://')===0||contactUrl.indexOf('http://')===0){cta.href=contactUrl;cta.target='_blank';cta.rel='noopener noreferrer'}else{cta.href='#iletisim';cta.removeAttribute('target');cta.removeAttribute('rel')}section.insertBefore(cta,content.nextSibling)}var socials=section.querySelector('.soc');if(socials)section.appendChild(socials);Array.from(section.children).forEach(function(child){if(child!==content&&child!==cta&&child!==socials){child.hidden=true;child.setAttribute('aria-hidden','true')}})}
    function setupFeaturedMarquee(d,track,featured,templates,fallback,cfg){
      var root=track.closest('.fw');if(!root)return;
      var win=d.defaultView,mobile=d.documentElement.clientWidth<=700,viewportWidth=d.documentElement.clientWidth||win.innerWidth,gap=mobile?12:24,cardWidth=mobile?Math.max(0,(viewportWidth-32)/2):262,naturalWidth=featured.length*cardWidth+Math.max(0,featured.length-1)*gap+8,shouldLoop=featured.length>1&&naturalWidth>Math.max(0,viewportWidth-24);d.documentElement.style.setProperty('--gallery-viewport-width',viewportWidth+'px');
      var signature=featured.map(function(p){return[p.code,p.title,p.size,p.price,p.sale_price,p.image,p.description].join('~')}).join('|')+'|'+(shouldLoop?'loop':'static')+'|w:'+Math.round(root.clientWidth||win.innerWidth);
      root.style.setProperty('box-sizing','border-box','important');root.style.setProperty('display',featured.length?'block':'none','important');root.style.setProperty('width',mobile?viewportWidth+'px':'100%','important');root.style.setProperty('max-width',mobile?viewportWidth+'px':'100%','important');root.style.setProperty('min-width','0','important');if(mobile){root.style.setProperty('margin-left','calc((100% - '+viewportWidth+'px)/2)','important');root.style.setProperty('margin-right','calc((100% - '+viewportWidth+'px)/2)','important');root.style.setProperty('padding-left','10px','important');root.style.setProperty('padding-right','10px','important');root.style.setProperty('mask-image','none','important');root.style.setProperty('-webkit-mask-image','none','important')}else{root.style.removeProperty('position');root.style.removeProperty('left');root.style.removeProperty('margin-left');root.style.removeProperty('margin-right');root.style.removeProperty('padding-left');root.style.removeProperty('padding-right');root.style.removeProperty('mask-image');root.style.removeProperty('-webkit-mask-image')}root.style.setProperty('overflow-x',mobile&&shouldLoop?'auto':'hidden','important');root.style.setProperty('overflow-y','hidden','important');root.style.setProperty('scroll-behavior','auto','important');root.style.scrollSnapType='none';root.style.scrollbarWidth='none';root.style.webkitOverflowScrolling='touch';root.style.touchAction='pan-x pan-y';
      track.style.setProperty('display','flex','important');track.style.setProperty('width','max-content','important');track.style.setProperty('max-width','none','important');track.style.setProperty('flex-wrap','nowrap','important');track.style.setProperty('gap',gap+'px','important');if(mobile)track.style.setProperty('padding','0','important');else track.style.removeProperty('padding');
      if(track.dataset.featuredSignature!==signature){
        track.dataset.featuredSignature=signature;track.dataset.motionSignature='';track.style.setProperty('animation','none','important');track.style.setProperty('transform','none','important');
        var originals=featured.map(function(p){var card=(templates.get(p.code)||fallback).cloneNode(true);paint(d,card,p,cfg);if(mobile){card.style.setProperty('width',cardWidth+'px','important');card.style.setProperty('min-width',cardWidth+'px','important');card.style.setProperty('max-width',cardWidth+'px','important');card.style.setProperty('flex-basis',cardWidth+'px','important')}card.style.scrollSnapAlign='none';return card}),visible=originals.slice(),loopCopies=1;
        if(shouldLoop){var duplicateCycle=function(){return originals.map(function(card){var copy=card.cloneNode(true);copy.setAttribute('aria-hidden','true');copy.setAttribute('inert','');copy.inert=true;copy.dataset.marqueeClone='true';return copy})};visible=visible.concat(duplicateCycle());track.replaceChildren.apply(track,visible);var baseDistance=track.children[featured.length].getBoundingClientRect().left-track.children[0].getBoundingClientRect().left;loopCopies=Math.max(2,baseDistance>0?Math.ceil((root.clientWidth||win.innerWidth)/baseDistance)+1:2);for(var cycle=2;cycle<loopCopies;cycle++)visible=visible.concat(duplicateCycle())}
        track.dataset.loopCopies=String(loopCopies);track.dataset.featuredCount=String(featured.length);track.replaceChildren.apply(track,visible);root.scrollLeft=0;if(!featured.length)track.innerHTML='<p style="padding:24px;color:#827783">Yönetim panelinden öne çıkarılan eserler burada görünür.</p>';
      }
      root.classList.toggle('is-static',!shouldLoop);root.hidden=!featured.length;
      var first=track.children[0],repeat=shouldLoop?track.children[featured.length]:null,distance=repeat&&first?Math.max(0,repeat.getBoundingClientRect().left-first.getBoundingClientRect().left):0;root.__featuredLoopDistance=distance;
      if(mobile){
        track.style.setProperty('animation','none','important');track.style.setProperty('transform','none','important');track.style.setProperty('will-change','auto','important');
        if(shouldLoop&&distance>0){
          if(!root.__featuredInputReady){var gestureStart=null,horizontalGesture=false;root.addEventListener('pointerdown',function(event){gestureStart={x:event.clientX,y:event.clientY};horizontalGesture=false},{passive:true});d.addEventListener('pointermove',function(event){if(!gestureStart)return;var dx=Math.abs(event.clientX-gestureStart.x),dy=Math.abs(event.clientY-gestureStart.y);if(dx>8&&dx>dy*1.2){horizontalGesture=true;root.__featuredInteracting=true;root.__featuredResumeAt=Infinity}},{passive:true});var resumeHorizontal=function(){if(!gestureStart)return;gestureStart=null;if(horizontalGesture){root.__featuredInteracting=false;root.__featuredResumeAt=win.performance.now()+1000}horizontalGesture=false};d.addEventListener('pointerup',resumeHorizontal,{passive:true});d.addEventListener('pointercancel',resumeHorizontal,{passive:true});root.__featuredInputReady=true}
          if(!root.__featuredRaf){root.__featuredLastFrame=0;var tick=function(now){if(!root.isConnected){root.__featuredRaf=0;return}var previous=root.__featuredLastFrame||now,delta=Math.min(34,Math.max(0,now-previous)),current=root.scrollLeft;root.__featuredLastFrame=now;if(current>=distance){current=current%distance;root.scrollLeft=current}if(!d.hidden&&!root.__featuredInteracting&&now>=(root.__featuredResumeAt||0)){current+=88*delta/1000;if(current>=distance)current=current%distance;root.scrollLeft=current}root.__featuredRaf=win.requestAnimationFrame(tick)};root.__featuredRaf=win.requestAnimationFrame(tick)}
        }else if(root.__featuredRaf){win.cancelAnimationFrame(root.__featuredRaf);root.__featuredRaf=0;root.__featuredLastFrame=0;root.scrollLeft=0}
      }else{
        root.style.setProperty('will-change','auto','important');root.scrollLeft=0;
        if(shouldLoop&&distance>0){var motionStyle=d.getElementById('featured-marquee-motion-style');if(!motionStyle){motionStyle=d.createElement('style');motionStyle.id='featured-marquee-motion-style';motionStyle.textContent='@keyframes featured-marquee-linear{to{transform:translate3d(calc(0px - var(--featured-cycle-distance)),0,0)}}';d.head.appendChild(motionStyle)}var motionSignature=signature+'|distance:'+distance.toFixed(2);if(track.dataset.motionSignature!==motionSignature){track.style.setProperty('animation','none','important');track.style.removeProperty('transform');track.style.setProperty('--featured-cycle-distance',distance+'px');track.style.setProperty('will-change','transform','important');track.style.setProperty('animation','featured-marquee-linear '+(distance/210)+'s linear infinite','important');track.dataset.motionSignature=motionSignature}if(root.__featuredRaf){win.cancelAnimationFrame(root.__featuredRaf);root.__featuredRaf=0;root.__featuredLastFrame=0}}
        else{track.style.setProperty('animation','none','important');track.style.setProperty('transform','none','important');track.style.setProperty('will-change','auto','important');if(root.__featuredRaf){win.cancelAnimationFrame(root.__featuredRaf);root.__featuredRaf=0;root.__featuredLastFrame=0}}
      }
    }
    function sync(){try{var d=frame.contentDocument;if(!d||busy)return;try{install(d)}catch(installError){console.error('Gallery layout setup failed',installError)}ensureAllWorks(d);ensureFooterStats(d);busy=true;fetch('/api/products',{cache:'no-store'}).then(function(r){if(!r.ok)throw Error('catalog');return r.json()}).then(function(data){var products=data.products||[],cfg=data.settings||{},active=products.filter(function(p){return !p.archived&&!p.sold&&p.published!==false}),featured=Array.from(new Map(active.filter(function(p){return !!p.featured}).map(function(p){return[p.code,p]})).values()).sort(function(a,b){return b.id-a.id}),soldItems=products.filter(function(p){return !p.archived&&!!p.sold&&p.published!==false}).sort(function(a,b){return b.id-a.id}),templates=d.__galleryCardTemplates||new Map();if(!templates.size&&d.__galleryBaseTemplate)templates.set('default',d.__galleryBaseTemplate);window.__adminProducts=products;window.__adminTemplates=templates;window.__adminSettings=cfg;
    var ft=d.querySelector('.fw .ftt'),fallback=d.__galleryBaseTemplate||d.querySelector('.card');if(ft&&fallback)setupFeaturedMarquee(d,ft,featured,templates,fallback,cfg);
    var arrivals=d.querySelector('#yeni-gelenler .editorial-grid');if(arrivals){var fresh=active.filter(function(p){return !!p.show_new}).sort(function(a,b){return b.id-a.id});arrivals.replaceChildren.apply(arrivals,fresh.map(function(p){var c=(templates.get(p.code)||fallback).cloneNode(true);paint(d,c,p,cfg);return c}));arrivals.parentElement.hidden=!fresh.length}
    var curated=d.querySelector('#sanatcinin-secimi .curated-grid');if(curated){var picks=active.filter(function(p){return !!p.show_curated}).sort(function(a,b){return b.id-a.id});curated.replaceChildren.apply(curated,picks.map(function(p){var c=(templates.get(p.code)||fallback).cloneNode(true);paint(d,c,p,cfg);return c}));curated.parentElement.hidden=!picks.length}
    var soldGrid=d.querySelector('#sold-works-grid');if(soldGrid){soldGrid.classList.add('sold-works-grid');soldGrid.replaceChildren.apply(soldGrid,soldItems.map(function(p){var c=(templates.get(p.code)||fallback).cloneNode(true);paint(d,c,p,cfg);return c}));soldGrid.parentElement.hidden=!soldItems.length}
    var brand=d.querySelector('.brand small');if(brand)brand.textContent='EL YAPIMI TABLOLAR · '+(cfg.site_name||'Perihan Baktaş');var name=d.querySelector('#hakkimda .sc[style*="font-size:40px"]');if(name)name.textContent=cfg.site_name||'Perihan Baktaş';renderAbout(d,cfg);d.title=(cfg.site_name||'Perihan Baktaş')+' | Sanat Atölyesi';[['Instagram','instagram_url'],['TikTok','tiktok_url'],['Telegram','telegram_url'],['WhatsApp','whatsapp_url']].forEach(function(pair){var url=cfg[pair[1]];if(!url)return;Array.from(d.querySelectorAll('a')).filter(function(a){return a.textContent.trim()===pair[0]}).forEach(function(a){a.href=url;a.target='_blank';a.rel='noopener'})});renderCatalog(d,products,templates);var deepCode='';try{deepCode=new URLSearchParams(window.location.search).get('eser')||''}catch(ignore){}if(deepCode&&window.__galleryDeepLinkOpened!==deepCode){var deepProduct=products.find(function(item){return item.code===deepCode&&!item.archived&&item.published!==false}),deepCard=Array.from(d.querySelectorAll('.card.gallery-work-card')).find(function(card){return card.dataset.productCode===deepCode});if(deepProduct&&deepCard){window.__galleryDeepLinkOpened=deepCode;openArtworkDetail(d,deepProduct,deepCard,cfg,false)}}d.documentElement.style.setProperty('--gallery-viewport-width',(d.documentElement.clientWidth||d.defaultView.innerWidth)+'px');
    var sig=JSON.stringify([products.map(function(p){return[p.id,p.code,p.title,p.size,p.price,p.sale_price,p.description,p.image,p.whatsapp_url,p.featured,p.sold,p.archived,p.show_new,p.show_collections,p.show_curated]}),cfg]);if(sig!==lastSignature){lastSignature=sig;window.__adminSlide=0;if(ft){ft.style.setProperty('transform','none','important');}}}).catch(function(){}).finally(function(){busy=false})}catch(e){busy=false}}
    function relayHomepageHash(){try{var hash=window.location.hash;if(hash&&frame.contentWindow.location.hash!==hash)frame.contentWindow.location.hash=hash}catch(e){}}
    window.addEventListener('hashchange',relayHomepageHash);
    frame.addEventListener('load',function(){relayHomepageHash();if(frame.contentDocument)install(frame.contentDocument);revealPage();sync();setInterval(sync,2500);try{frame.contentWindow.addEventListener('resize',function(){lastSignature='';sync()})}catch(e){}});if(frame.contentDocument&&frame.contentDocument.readyState==='complete'){relayHomepageHash();install(frame.contentDocument);revealPage();sync();setInterval(sync,2500)}})();
    </script></body></html>"""


def input_field(label, name, value="", kind="text", required=False, extra=""):
    req = " required" if required else ""
    if kind == "textarea":
        control = f"<textarea name='{name}' {req} {extra}>{esc(value)}</textarea>"
    else:
        control = f"<input name='{name}' type='{kind}' value='{esc(value)}' {req} {extra}>"
    label_class = " class='span-2'" if "class='span-2'" in extra or 'class="span-2"' in extra else ""
    return f"<label{label_class}>{label}{control}</label>"


class SiteHandler(BaseHTTPRequestHandler):
    server_version = "SanatAtolyesi/1.0"

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} - {fmt % args}")

    def send_html(self, body, status=200, headers=None):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        for k, v in headers or []:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, location, headers=None):
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        for k, v in headers or []:
            self.send_header(k, v)
        self.end_headers()

    def static(self, urlpath):
        relative = urlpath.removeprefix("/static/")
        path = (ROOT / "static" / relative).resolve()
        if not path.is_relative_to((ROOT / "static").resolve()) or not path.is_file():
            self.send_error(404)
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def upload_file(self, fileitem, folder, prefix):
        if not fileitem or not fileitem["filename"]:
            return ""
        filename = Path(fileitem["filename"]).name
        ext = Path(filename).suffix.lower()
        data = fileitem["data"]
        if ext not in ALLOWED_EXT or not data or len(data) > MAX_FILE:
            raise ValueError("Görsel JPG, PNG veya WEBP olmalı ve 8 MB sınırını aşmamalı.")
        if not (data.startswith(b"\xff\xd8\xff") or data.startswith(b"\x89PNG\r\n\x1a\n") or (data.startswith(b"RIFF") and data[8:12] == b"WEBP")):
            raise ValueError("Dosyanın içeriği geçerli bir JPG, PNG veya WEBP görseli değil.")
        name = prefix + uuid.uuid4().hex + ext
        target = UPLOADS / folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return f"uploads/{folder}/{name}"

    def parse_form(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_REQUEST:
            raise ValueError("İstek boyutu çok büyük.")
        body = self.rfile.read(length)
        ctype = self.headers.get("Content-Type", "")
        if ctype.lower().startswith("multipart/form-data"):
            message = BytesParser(policy=policy.default).parsebytes(b"Content-Type: " + ctype.encode() + b"\r\nMIME-Version: 1.0\r\n\r\n" + body)
            fields, files = {}, {}
            for part in message.iter_parts():
                name = part.get_param("name", header="content-disposition")
                if not name:
                    continue
                payload = part.get_payload(decode=True) or b""
                filename = part.get_filename()
                if filename:
                    files[name] = {"filename": filename, "data": payload}
                else:
                    fields[name] = payload.decode("utf-8", "replace")
            return fields, files
        parsed = parse_qs(body.decode("utf-8", "replace"), keep_blank_values=True)
        return {k: v[-1] for k, v in parsed.items()}, {}

    def get_admin(self):
        raw = self.headers.get("Cookie", "")
        value = next((x.strip().split("=", 1)[1] for x in raw.split(";") if x.strip().startswith("gallery_admin=")), "")
        try:
            payload, sig = value.split(".", 1)
            secret = settings()["session_secret"]
            expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
            data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
            if hmac.compare_digest(sig, expected) and data.get("exp", 0) > time.time() and data.get("id") == 1:
                return data
        except Exception:
            pass
        return None

    def require_admin(self):
        data = self.get_admin()
        if data:
            return data
        self.redirect("/atolye-yonetim-8f31/login")
        return None

    def csrf_ok(self, fields):
        session = self.get_admin()
        return bool(session and hmac.compare_digest(str(fields.get("csrf", "")), str(session.get("csrf", ""))))

    def register_visitor(self):
        match = re.search(r"(?:^|;\s*)gallery_visitor=([a-f0-9]{32})(?:;|$)", self.headers.get("Cookie", ""))
        visitor_id = match.group(1) if match else uuid.uuid4().hex
        with connect() as c:
            exists = c.execute("SELECT 1 FROM site_visitors WHERE visitor_id=?", (visitor_id,)).fetchone()
            c.execute("INSERT INTO site_visitors(visitor_id) VALUES(?) ON CONFLICT(visitor_id) DO UPDATE SET last_seen=CURRENT_TIMESTAMP", (visitor_id,))
        cookie = f"gallery_visitor={visitor_id}; HttpOnly; SameSite=Lax; Path=/; Max-Age=31536000"
        if self.headers.get("X-Forwarded-Proto", "").lower() == "https":
            cookie += "; Secure"
        return cookie, not bool(exists)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path == "/legacy-homepage.html":
            self.send_response(302)
            self.send_header("Location", "/")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        if path == "/legacy-home-content":
            legacy = ROOT / "legacy-homepage.html"
            data = legacy.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)
            return
        if path == "/api/products":
            with connect() as c:
                items = [dict(r) for r in c.execute("SELECT * FROM products ORDER BY id")]
                share_counts = {r["product_id"]: r["count"] for r in c.execute("SELECT product_id,COUNT(*) AS count FROM product_shares GROUP BY product_id")}
                for item in items:
                    item["published"] = not item.get("publish_at") or item["publish_at"] <= site_now_string()
                    item["share_count"] = share_counts.get(item["id"], 0)
                    item.pop("category", None)
            cfg = settings()
            public_settings = {k: cfg.get(k, "") for k in ("site_name", "whatsapp_url", "instagram_url", "tiktok_url", "telegram_url", "question_message", "about_heading", "about_text", "about_image")}
            payload = json.dumps({"products": items, "settings": public_settings}, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if path == "/api/stats":
            return self.send_json(display_site_stats())
        if path == "/api/comments":
            code = query.get("code", [""])[0].strip()[:64]
            now = site_now_string()
            with connect() as c:
                if query.get("counts", [""])[0] == "1":
                    rows = c.execute("""
                        SELECT p.code, COUNT(cm.id) AS count
                        FROM products p LEFT JOIN product_comments cm ON cm.product_id=p.id
                        WHERE p.archived=0 AND (p.publish_at='' OR p.publish_at<=?)
                        GROUP BY p.id ORDER BY p.id
                    """, (now,)).fetchall()
                    return self.send_json({"counts": {r["code"]: r["count"] for r in rows}})
                if not code:
                    return self.send_json({"error": "Eser kodu gerekli."}, 400)
                product = c.execute("SELECT id FROM products WHERE code=? AND archived=0 AND (publish_at='' OR publish_at<=?)", (code, now)).fetchone()
                if not product:
                    return self.send_json({"error": "Eser bulunamadı."}, 404)
                rows = c.execute("""
                    SELECT id,parent_id,first_name,last_name,body,avatar_path,created_at
                    FROM product_comments WHERE product_id=? ORDER BY id
                """, (product["id"],)).fetchall()
            comments = [{"id": r["id"], "parent_id": r["parent_id"], "first_name": r["first_name"],
                         "last_name": r["last_name"], "body": r["body"],
                         "avatar_url": ("/" + r["avatar_path"]) if r["avatar_path"] else "",
                         "created_at": r["created_at"]} for r in rows]
            return self.send_json({"code": code, "comments": comments, "count": len(comments)})
        if path == "/api/likes":
            visitor = query.get("visitor", [""])[0]
            if not re.fullmatch(r"[a-f0-9-]{16,64}", visitor):
                visitor = ""
            with connect() as c:
                rows = c.execute("""
                    SELECT p.code, COUNT(l.visitor_id) AS count,
                    MAX(CASE WHEN l.visitor_id=? THEN 1 ELSE 0 END) AS liked
                    FROM products p LEFT JOIN product_likes l ON l.product_id=p.id
                    WHERE p.archived=0 GROUP BY p.id ORDER BY p.id
                """, (visitor,)).fetchall()
            return self.send_json({"likes": {r["code"]: {"count": r["count"], "liked": bool(r["liked"])} for r in rows}})
        if path.startswith("/static/"):
            return self.static(path)
        if path.startswith("/uploads/"):
            relative = path.removeprefix("/")
            if relative.startswith("uploads/requests/") and not self.get_admin():
                return self.send_error(404)
            file = (DATA_ROOT / relative).resolve()
            if file.is_relative_to(UPLOADS.resolve()) and file.is_file():
                data = file.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", mimetypes.guess_type(file.name)[0] or "application/octet-stream")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(data)
                return
            return self.send_error(404)
        if path == "/":
            visitor_cookie, _ = self.register_visitor()
            return self.send_html(render_legacy_home(), headers=[("Set-Cookie", visitor_cookie)])
        if path == "/new-home":
            visitor_cookie, _ = self.register_visitor()
            now = site_now_string()
            with connect() as c:
                rows = c.execute("SELECT * FROM products WHERE archived=0 AND sold=0 AND (publish_at='' OR publish_at<=?) ORDER BY featured DESC,created_at DESC", (now,)).fetchall()
                featured = c.execute("SELECT * FROM products WHERE archived=0 AND sold=0 AND featured=1 AND (publish_at='' OR publish_at<=?) ORDER BY id DESC LIMIT 8", (now,)).fetchall()
                sold = c.execute("SELECT * FROM products WHERE archived=0 AND sold=1 AND (publish_at='' OR publish_at<=?) ORDER BY id DESC", (now,)).fetchall()
            hero = "<section class='hero'><div class='hero-copy'><span class='eyebrow'>EL YAPIMI · ÖZGÜN ESERLER</span><h1>Sanatla Dolu<br><em>Huzurlu Bir Bahar</em></h1><p>İlkbaharın sakinliği, fırçanın dokunuşuyla duvarınıza gelsin. Her eser kendine özgü bir renk ve hikâye taşır.</p><a class='button' href='#eserler'>Eserleri Keşfet</a></div><div class='hero-art'><div class='hero-canvas'><span>✿</span><span>✿</span><span>✿</span><span>✿</span></div><small>Perihan Baktaş · Atölyeden</small></div></section>"
            content = hero
            if featured:
                content += f"<section class='section'><div class='section-heading'><span class='eyebrow'>ATÖLYEDEN SEÇKİ</span><h2>Öne Çıkan Eserler</h2><p>Sanatın en özel parçalarını keşfedin.</p></div><div class='carousel'><button class='carousel-arrow' type='button' data-carousel='prev' aria-label='Önceki eserler'>‹</button><div class='product-grid carousel-track'>{product_cards(featured)}</div><button class='carousel-arrow' type='button' data-carousel='next' aria-label='Sonraki eserler'>›</button></div></section>"
            content += f"<section class='section' id='eserler'><div class='section-heading'><span class='eyebrow'>ÖZGÜN ÇALIŞMALAR</span><h2>Tüm Eserler</h2><p>Atölyedeki tüm eserleri keşfedin.</p></div><div class='product-grid'>{product_cards(rows)}</div></section>"
            if sold:
                content += f"<section class='section sold-section'><div class='section-heading'><span class='eyebrow'>YENİ SAHİPLERİNE ULAŞTILAR</span><h2>Satılan Eserler</h2><p>Sahiplerine ulaşmış güzel parçalar.</p></div><div class='product-grid'>{product_cards(sold)}</div></section>"
            content += "<section id='hakkimda' class='about'><span class='eyebrow'>ATÖLYEDEN BİR NOT</span><h2>Her Eserde Bir Bahar Hikâyesi</h2><p>Perihan Baktaş’ın el yapımı eserleri; çiçeklerin, doğanın ve mevsimlerin renklerinden ilham alır.</p></section>"
            return self.send_html(render("Ana Sayfa", content), headers=[("Set-Cookie", visitor_cookie)])
        if path == "/arsiv":
            with connect() as c: rows = c.execute("SELECT * FROM products WHERE archived=1 ORDER BY created_at DESC").fetchall()
            content = f"<section class='page-intro'><span class='eyebrow'>ATÖLYE KAYITLARI</span><h1>Eser Arşivi</h1><p>Arşive alınan eserler bu listede saklanır.</p></section><div class='product-grid'>{product_cards(rows)}</div>"
            return self.send_html(render("Eser Arşivi", content))
        if path in ("/atolye-yonetim-8f31", "/atolye-yonetim-8f31/"):
            return self.redirect("/atolye-yonetim-8f31/products" if self.get_admin() else "/atolye-yonetim-8f31/login")
        if path == "/atolye-yonetim-8f31/setup":
            with connect() as c: exists = c.execute("SELECT 1 FROM admin WHERE id=1").fetchone()
            if exists: return self.redirect("/atolye-yonetim-8f31/login")
            content = "<section class='page-intro'><span class='eyebrow'>İLK KURULUM</span><h1>Yönetici Parolası Oluştur</h1><p>Bu panel yalnızca sizin belirleyeceğiniz parola ile açılır. En az 10 karakter kullanın.</p></section><section class='narrow form-card'><form method='post' action='/atolye-yonetim-8f31/setup'><label>Yeni parola<input type='password' name='password' minlength='10' required></label><label>Parolayı doğrula<input type='password' name='confirm' minlength='10' required></label><button class='button wide'>Yönetici Hesabı Oluştur</button></form></section>"
            return self.send_html(render("İlk Kurulum", content))
        if path == "/atolye-yonetim-8f31/login":
            content = "<section class='page-intro'><span class='eyebrow'>YÖNETİM PANELİ</span><h1>Yönetici Girişi</h1><p>Atölye yönetimine devam etmek için giriş yapın.</p></section><section class='narrow form-card'><form method='post' action='/atolye-yonetim-8f31/login'><label>Parola<input type='password' name='password' required autofocus></label><button class='button wide'>Giriş Yap</button></form></section>"
            with connect() as c: exists = c.execute("SELECT 1 FROM admin WHERE id=1").fetchone()
            return self.send_html(render("Yönetici Girişi", content + ("" if exists else "<p class='center'><a href='/atolye-yonetim-8f31/setup'>İlk yönetici parolasını oluştur</a></p>")))
        if not path.startswith("/atolye-yonetim-8f31/"):
            return self.send_error(404)
        admin = self.require_admin()
        if not admin: return
        csrf = esc(admin["csrf"])
        if path == "/atolye-yonetim-8f31/logout":
            return self.redirect("/atolye-yonetim-8f31/login", [("Set-Cookie", "gallery_admin=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0")])
        if path == "/atolye-yonetim-8f31/products":
            with connect() as c:
                rows = c.execute("SELECT * FROM products WHERE archived=0 ORDER BY featured DESC,id").fetchall()
                archived_rows = c.execute("SELECT * FROM products WHERE archived=1 ORDER BY created_at DESC,id DESC").fetchall()
                likes = {r["product_id"]: r["count"] for r in c.execute("SELECT product_id,COUNT(*) AS count FROM product_likes GROUP BY product_id")}
                comments = {r["product_id"]: r["count"] for r in c.execute("SELECT product_id,COUNT(*) AS count FROM product_comments GROUP BY product_id")}
                shares = {r["product_id"]: r["count"] for r in c.execute("SELECT product_id,COUNT(*) AS count FROM product_shares GROUP BY product_id")}
            listing = "".join(admin_product_row(p, csrf, likes.get(p["id"], 0), comments.get(p["id"], 0), shares.get(p["id"], 0)) for p in rows)
            archived_listing = "".join(admin_product_row(p, csrf, likes.get(p["id"], 0), comments.get(p["id"], 0), shares.get(p["id"], 0), archived=True) for p in archived_rows)
            if not listing:
                listing = "<tr><td colspan='10' class='empty'>Yayındaki eser yok.</td></tr>"
            if not archived_listing:
                archived_listing = "<tr><td colspan='10' class='empty'>Arşivde henüz eser yok.</td></tr>"
            copy_script = "<script>document.querySelectorAll('.copy-code').forEach(function(b){b.addEventListener('click',function(){navigator.clipboard.writeText(b.dataset.copy).then(function(){var old=b.textContent;b.textContent='Kopyalandı';setTimeout(function(){b.textContent=old},1200)})})})</script>"
            table_head = "<thead><tr><th>Kod</th><th>Eser</th><th>Ölçü</th><th>Fiyat</th><th>Beğeni</th><th>Yorumlar</th><th>Paylaşım</th><th>Ana sayfa bölümleri</th><th>Durum / yayın tarihi</th><th>İşlem</th></tr></thead>"
            content = f"<section class='admin-top'><div><span class='eyebrow'>KATALOG</span><h1>Tablolar</h1><p>Fiyat, ölçü, açıklama ve öne çıkarma ayarları.</p></div>{admin_nav('products')}</section><div class='admin-actions' style='box-sizing:border-box;width:100%;max-width:1280px;margin:0 auto 15px;padding:0 24px;display:flex;justify-content:flex-start;align-items:center'><a class='button small' href='/atolye-yonetim-8f31/products/new'>+ Yeni Tablo Ekle</a></div><div class='table-wrap'><table>{table_head}<tbody>{listing}</tbody></table></div><h2>Arşiv</h2><div class='table-wrap'><table>{table_head}<tbody>{archived_listing}</tbody></table></div><p class='center'><a href='/arsiv'>Arşiv sayfasını görüntüle</a></p>{copy_script}"
            return self.send_html(render("Yönetim · Tablolar", content))
        if path == "/atolye-yonetim-8f31/products/new" or re.fullmatch(r"/atolye-yonetim-8f31/products/\d+", path):
            product = None
            if path != "/atolye-yonetim-8f31/products/new":
                with connect() as c: product = c.execute("SELECT * FROM products WHERE id=?", (int(path.rsplit('/',1)[-1]),)).fetchone()
                if not product: return self.send_error(404)
            val = lambda key, default="": product[key] if product else default
            size_match = re.match(r"\s*(\d+)\s*[x×]\s*(\d+)\s*(.*)", str(val("size", "")), re.I)
            width_val, height_val, unit_val = (size_match.group(1), size_match.group(2), size_match.group(3).strip() or "cm") if size_match else ("", "", "cm")
            if not product:
                with connect() as c:
                    while True:
                        code = "PB-" + str(secrets.randbelow(900) + 100)
                        if not c.execute("SELECT 1 FROM products WHERE code=?", (code,)).fetchone(): break
            else:
                code = product["code"]
            code_match = re.fullmatch(r"([A-Z]+-)([0-9]+)", str(code).upper())
            code_prefix = code_match.group(1) if code_match else "PB-"
            code_digits = code_match.group(2) if code_match else re.sub(r"[^0-9]", "", str(code))
            code_field = f"<label>Eser kodu<div class='code-input-row' style='display:flex;align-items:center;gap:0;border:1px solid #e0d6d1;border-radius:10px;background:#fffdfb;overflow:hidden'><span style='padding:10px 0 10px 12px;color:#79546f;font-weight:700'>{esc(code_prefix)}</span><input name='code_digits' type='text' inputmode='numeric' pattern='[0-9]+' maxlength='12' value='{esc(code_digits)}' aria-label='Eser kodu rakamları' required oninput='this.value=this.value.replace(/[^0-9]/g,"");this.nextElementSibling.dataset.copy=this.previousElementSibling.textContent+this.value' style='min-width:0;flex:1;border:0!important;background:transparent!important'><button type='button' class='copy-code' data-copy='{esc(code_prefix + code_digits)}'>Kopyala</button></div><small>Ön ek otomatik eklenir; yalnızca rakam girin.</small></label>"
            featured = "checked" if product and product["featured"] else ""
            sold = "checked" if product and product["sold"] else ""
            show_new = "checked" if product and product["show_new"] else ""
            show_curated = "checked" if product and product["show_curated"] else ""
            section_choices = f"<fieldset class='section-choice span-2'><legend>Ana sayfada hangi bölümlerde öne çıksın?</legend><div class='section-checks'><label><input type='checkbox' name='show_new' value='1' {show_new}> Yeni Gelenler</label><label><input type='checkbox' name='show_curated' value='1' {show_curated}> Sanatçının Seçkisi</label></div><small>Tüm eserler bölümünde ayrıca otomatik görünür.</small></fieldset>"
            size_fields = f"<fieldset class='span-2 size-choice'><legend>Tablo ölçüsü</legend><label>Genişlik<input type='number' inputmode='numeric' name='width' min='1' max='500' value='{esc(width_val)}' required></label><span class='size-x'>×</span><label>Yükseklik<input type='number' inputmode='numeric' name='height' min='1' max='500' value='{esc(height_val)}' required></label><label>Birim<select name='size_unit'><option {'selected' if unit_val=='cm' else ''}>cm</option><option {'selected' if unit_val=='mm' else ''}>mm</option><option {'selected' if unit_val=='inç' else ''}>inç</option></select></label></fieldset>"
            publish_at = val("publish_at", "")
            if publish_at and len(publish_at) == 10: publish_at += "T00:00"
            wa_accounts = parse_whatsapp_accounts(settings().get("whatsapp_accounts", "[]"))
            wa_options = ["<option value=''>Kayıtlı hesap seçin</option>"]
            for account_index, account in enumerate(wa_accounts):
                selected = "selected" if account["url"] == val("whatsapp_url") else ""
                wa_options.append(f"<option value='{account_index}' data-url='{esc(account['url'])}' {selected}>{esc(account['name'])}</option>")
            whatsapp_picker = f"<label class='span-2'>Hazır WhatsApp hesabı<select id='whatsapp-account-picker' name='whatsapp_account'>{''.join(wa_options)}</select><small>Hesapları Site Ayarları bölümünden kaydedip burada seçebilirsiniz.</small></label>"
            content = f"<section class='admin-top'><div><span class='eyebrow'>KATALOG</span><h1>{'Tabloyu Düzenle' if product else 'Yeni Tablo Ekle'}</h1><p>Eser bilgilerini düzenli bölümlerden yönetin.</p></div>{admin_nav('products')}</section><section class='form-card admin-form'><form method='post' enctype='multipart/form-data' action='/atolye-yonetim-8f31/products/save'><input type='hidden' name='csrf' value='{csrf}'><input type='hidden' name='id' value='{esc(val('id'))}'><input type='hidden' name='whatsapp_url' value='{esc(val('whatsapp_url'))}'><input type='hidden' name='description' value='{esc(val('description'))}'><div class='admin-form-layout'><fieldset class='admin-form-section'><legend>Tablo bilgileri</legend><div class='form-grid'>{code_field}{input_field('Eser adı', 'title', val('title'), required=True)}</div></fieldset><fieldset class='admin-form-section'><legend>Ölçü ve fiyat</legend><div class='form-grid'>{size_fields}{input_field('Liste fiyatı (₺)', 'price', val('price'), 'number', True, "min='0'")}{input_field('İndirimli fiyat (₺, isteğe bağlı)', 'sale_price', val('sale_price') or '', 'number', False, "min='0'")}</div></fieldset><fieldset class='admin-form-section'><legend>Yayın ve iletişim</legend><div class='form-grid'>{input_field('Yayın zamanı (boş bırakılırsa hemen yayınlanır)', 'publish_at', publish_at, 'datetime-local')}{whatsapp_picker}</div></fieldset><fieldset class='admin-form-section'><legend>İncele sayfası</legend><div class='form-grid'>{input_field('İncele başlığı (isteğe bağlı)', 'inspect_title', val('inspect_title'), 'text', False, "maxlength='160'")}{input_field('Makale / eser hikâyesi (isteğe bağlı)', 'article', val('article'), 'textarea', False, "rows='5' maxlength='12000' class='span-2'")}</div></fieldset><fieldset class='admin-form-section span-2'><legend>Eser görseli</legend><label class='admin-upload-field'>Görsel dosyası<input type='file' name='image' accept='.jpg,.jpeg,.jfif,.png,.webp'><small>JPG, PNG veya WEBP · en fazla 8 MB{(' · Mevcut görsel: '+esc(val('image'))) if product and val('image') else ''}</small></label></fieldset><fieldset class='admin-form-section span-2'><legend>Yayın durumu</legend><div class='check-row'><label><input type='checkbox' name='featured' value='1' {featured}> Öne Çıkan Eserler şeridinde göster</label><label><input type='checkbox' name='sold' value='1' {sold}> Satıldı olarak göster</label></div></fieldset>{section_choices}</div><div class='admin-form-actions'><button class='button'>Kaydet</button><a class='button ghost' href='/atolye-yonetim-8f31/products'>İptal</a></div></form></section><script src='/static/admin-product-form.js' defer></script>"
            return self.send_html(render("Yönetim · Tablo", content))
        if path == "/atolye-yonetim-8f31/settings":
            cfg = settings()
            displayed_stats = display_site_stats(cfg)
            stats_fields = "".join((
                input_field("Tekil ziyaretçi toplamı", "stat_visitors", displayed_stats["visitors"], "number", True, "min='0' step='1' inputmode='numeric'"),
                input_field("Satılan eser toplamı", "stat_sold", displayed_stats["sold"], "number", True, "min='0' step='1' inputmode='numeric'"),
                input_field("Yayındaki eser toplamı", "stat_available", displayed_stats["available"], "number", True, "min='0' step='1' inputmode='numeric'"),
            ))
            wa_accounts = parse_whatsapp_accounts(cfg.get("whatsapp_accounts", "[]"))
            account_rows = "".join(f"<div class='wa-account-row' data-wa-account-row><label>Hesap adı<input type='text' data-wa-name maxlength='60' value='{esc(account['name'])}'></label><label>WhatsApp bağlantısı<input type='url' data-wa-url placeholder='https://wa.me/905...' value='{esc(account['url'])}'></label><button type='button' class='button ghost wa-remove-account'>Kaldır</button></div>" for account in wa_accounts)
            if not account_rows:
                account_rows = "<div class='wa-account-row' data-wa-account-row><label>Hesap adı<input type='text' data-wa-name maxlength='60' placeholder='Örn. Atölye'></label><label>WhatsApp bağlantısı<input type='url' data-wa-url placeholder='https://wa.me/905...'></label><button type='button' class='button ghost wa-remove-account'>Kaldır</button></div>"
            accounts_manager = f"<fieldset class='wa-account-manager'><legend>Tablolar için hazır WhatsApp hesapları</legend><p>Bu hesapları burada kaydedin; yeni tablo eklerken listeden seçin.</p><div id='wa-account-list'>{account_rows}</div><button type='button' class='button ghost' id='wa-add-account'>+ WhatsApp hesabı ekle</button><input type='hidden' name='whatsapp_accounts' id='wa-accounts-json' value='{esc(json.dumps(wa_accounts, ensure_ascii=False, separators=(',', ':')))}'></fieldset>"
            accounts_script = "<script>(function(){var form=document.getElementById('settings-form'),list=document.getElementById('wa-account-list'),hidden=document.getElementById('wa-accounts-json');function bindRow(row){row.querySelector('.wa-remove-account').addEventListener('click',function(){row.remove()})}Array.from(list.querySelectorAll('[data-wa-account-row]')).forEach(bindRow);document.getElementById('wa-add-account').addEventListener('click',function(){var row=document.createElement('div');row.className='wa-account-row';row.setAttribute('data-wa-account-row','');row.innerHTML='<label>Hesap adı<input type=\"text\" data-wa-name maxlength=\"60\" placeholder=\"Örn. Atölye\"></label><label>WhatsApp bağlantısı<input type=\"url\" data-wa-url placeholder=\"https://wa.me/905...\"></label><button type=\"button\" class=\"button ghost wa-remove-account\">Kaldır</button>';list.appendChild(row);bindRow(row)});form.addEventListener('submit',function(event){var accounts=[],valid=true;Array.from(list.querySelectorAll('[data-wa-account-row]')).forEach(function(row){var name=row.querySelector('[data-wa-name]'),url=row.querySelector('[data-wa-url]'),n=name.value.trim(),u=url.value.trim();name.setCustomValidity('');url.setCustomValidity('');if(!n&&!u)return;if(!n){name.setCustomValidity('Hesap adı gerekli.');name.reportValidity();valid=false;return}if(!u){url.setCustomValidity('WhatsApp bağlantısı gerekli.');url.reportValidity();valid=false;return}accounts.push({name:n,url:u})});if(accounts.length>20){event.preventDefault();alert('En fazla 20 WhatsApp hesabı kaydedebilirsiniz.');return}if(!valid){event.preventDefault();return}hidden.value=JSON.stringify(accounts)})})();</script>"
            accounts_style = "<style>.wa-account-manager{display:grid;gap:12px;margin:14px 0 4px;padding:15px;border:1px solid #e8ddd7;border-radius:14px;background:#fffdfb}.wa-account-manager legend{padding:0 8px;color:#4b514e;font-weight:700}.wa-account-manager>p{margin:0;color:#827783;font-size:13px}.wa-account-row{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.4fr) auto;align-items:end;gap:10px;padding:12px;background:#faf6f2;border-radius:12px}.wa-account-row label{display:grid;gap:6px;color:#5f565d;font-size:12px;font-weight:600}.wa-account-row input{width:100%;min-width:0;padding:10px;border:1px solid #e0d6d1;border-radius:9px;background:#fff}.wa-account-row .button{white-space:nowrap}@media(max-width:620px){.wa-account-row{grid-template-columns:1fr}.wa-account-row .button{justify-self:start}}</style>"
            about_image = cfg.get("about_image", "")
            if not re.fullmatch(r"uploads/about/[A-Za-z0-9._-]+", about_image):
                about_image = ""
            about_image_preview = f"<div class='about-image-preview'><img src='/{esc(about_image)}' alt='Mevcut Hakkımda fotoğrafı'><small>Mevcut fotoğraf</small></div>" if about_image else "<div class='about-image-preview is-empty'><span>✿</span><small>Henüz fotoğraf yüklenmedi</small></div>"
            about_crop_style = """<style>.about-crop-editor{width:min(100%,400px);margin:12px 0}.about-crop-frame,.about-image-preview{position:relative;width:min(100%,400px);aspect-ratio:4/3;overflow:hidden;border:1px solid #e6d9d4;border-radius:14px;background:linear-gradient(145deg,#ead4dd,#f8eddf 55%,#dce8dc)}.about-crop-frame{touch-action:none;cursor:grab}.about-crop-frame:active{cursor:grabbing}.about-crop-frame img{position:absolute;max-width:none!important;max-height:none!important;user-select:none;-webkit-user-drag:none;pointer-events:none}.about-crop-guide{position:absolute;inset:0;pointer-events:none;border:1px solid rgba(255,255,255,.72);box-shadow:inset 0 0 0 999px rgba(43,32,39,.04)}.about-crop-zoom{display:grid;gap:6px;margin:10px 0 6px;color:#5f565d;font-size:12px;font-weight:600}.about-crop-zoom input{width:100%;accent-color:#79546f}.about-crop-help,.about-crop-status{display:block;margin:6px 0;color:#827783;font-size:12px;line-height:1.5}.about-image-preview{display:grid;place-items:center;margin-top:12px}.about-image-preview img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}.about-image-preview small{position:absolute;left:9px;bottom:9px;padding:5px 8px;border-radius:999px;background:rgba(49,43,47,.65);color:#fff}.about-image-preview.is-empty span{color:#d88eaa;font:90px/1 Georgia,serif}@media(max-width:620px){.about-crop-editor,.about-image-preview{width:100%}}</style>"""
            about_crop_script = """<script>(function(){var form=document.getElementById('settings-form'),input=form&&form.querySelector('input[name=about_image]'),editor=document.getElementById('about-crop-editor'),frame=document.getElementById('about-crop-frame'),image=document.getElementById('about-crop-source'),zoom=document.getElementById('about-crop-zoom'),status=document.getElementById('about-crop-status');if(!form||!input||!editor||!frame||!image)return;var objectUrl='',scale=1,x=0,y=0,renderW=0,renderH=0,drag=null;function paint(){var rect=frame.getBoundingClientRect();if(!image.naturalWidth||!rect.width)return;var cover=Math.max(rect.width/image.naturalWidth,rect.height/image.naturalHeight);scale=cover*Number(zoom.value||1);renderW=image.naturalWidth*scale;renderH=image.naturalHeight*scale;x=Math.min(0,Math.max(rect.width-renderW,x));y=Math.min(0,Math.max(rect.height-renderH,y));image.style.width=renderW+'px';image.style.height=renderH+'px';image.style.left=x+'px';image.style.top=y+'px'}input.addEventListener('change',function(){var file=input.files&&input.files[0];if(!file)return;if(objectUrl)URL.revokeObjectURL(objectUrl);objectUrl=URL.createObjectURL(file);image.onload=function(){editor.hidden=false;var rect=frame.getBoundingClientRect(),cover=Math.max(rect.width/image.naturalWidth,rect.height/image.naturalHeight),factor=Number(zoom.value||1);renderW=image.naturalWidth*cover*factor;renderH=image.naturalHeight*cover*factor;x=(rect.width-renderW)/2;y=(rect.height-renderH)/2;paint();status.textContent='';};image.src=objectUrl});zoom.addEventListener('input',function(){var rect=frame.getBoundingClientRect(),cx=rect.width/2,cy=rect.height/2,ratio=Number(zoom.value||1);if(renderW&&renderH){var oldW=renderW,oldH=renderH;paint();x=cx-(cx-x)*renderW/oldW;y=cy-(cy-y)*renderH/oldH;paint()}else paint()});frame.addEventListener('pointerdown',function(e){if(!image.naturalWidth)return;drag={pointer:e.pointerId,startX:e.clientX,startY:e.clientY,x:x,y:y};frame.setPointerCapture(e.pointerId)});frame.addEventListener('pointermove',function(e){if(!drag||drag.pointer!==e.pointerId)return;x=drag.x+e.clientX-drag.startX;y=drag.y+e.clientY-drag.startY;paint()});['pointerup','pointercancel'].forEach(function(type){frame.addEventListener(type,function(){drag=null})});window.addEventListener('resize',paint);form.addEventListener('submit',function(event){if(event.defaultPrevented)return;var file=input.files&&input.files[0];if(!file||!image.naturalWidth)return;event.preventDefault();var button=form.querySelector('button[type=submit]');if(button)button.disabled=true;status.textContent='Fotoğraf seçtiğiniz kadraja göre hazırlanıyor…';var rect=frame.getBoundingClientRect(),canvas=document.createElement('canvas');canvas.width=1200;canvas.height=900;var context=canvas.getContext('2d'),sx=Math.max(0,-x/scale),sy=Math.max(0,-y/scale),sw=Math.min(image.naturalWidth-sx,rect.width/scale),sh=Math.min(image.naturalHeight-sy,rect.height/scale);context.drawImage(image,sx,sy,sw,sh,0,0,canvas.width,canvas.height);canvas.toBlob(function(blob){if(!blob){status.textContent='Fotoğraf hazırlanamadı. Lütfen yeniden deneyin.';if(button)button.disabled=false;return}try{var transfer=new DataTransfer();transfer.items.add(new File([blob],'about-photo-cropped.jpg',{type:'image/jpeg',lastModified:Date.now()}));input.files=transfer.files;HTMLFormElement.prototype.submit.call(form)}catch(error){status.textContent='Kırpılan fotoğraf forma eklenemedi. Lütfen yeniden deneyin.';if(button)button.disabled=false}},'image/jpeg',.9)});})();</script>"""
            content = f"""<section class='admin-top'><div><span class='eyebrow'>SİTE AYARLARI</span><h1>Site Ayarları</h1><p>Ana sayfa tanıtımını, iletişim ve sosyal hesapları yönetin.</p></div>{admin_nav('settings')}</section>{accounts_style}{about_crop_style}<section class='form-card admin-settings-card'><form id='settings-form' method='post' enctype='multipart/form-data' action='/atolye-yonetim-8f31/settings'><input type='hidden' name='csrf' value='{csrf}'><div class='admin-settings-layout'><fieldset class='admin-settings-section'><legend>Atölye kimliği</legend>{input_field('Atölye adı', 'site_name', cfg.get('site_name'), required=True)}</fieldset><fieldset class='admin-settings-section'><legend>WhatsApp ve iletişim</legend>{input_field('WhatsApp bağlantısı', 'whatsapp_url', cfg.get('whatsapp_url'), 'url')}{accounts_manager}<label>“Soru Sor” hazır mesajı<textarea name='question_message' rows='3' maxlength='1000' placeholder='Merhaba, {{{{code}}}} kodlu tablonuz hakkında soru sormak istiyorum.'>{esc(cfg.get('question_message'))}</textarea><small>{{{{code}}}} eser kodunu, {{{{title}}}} eser adını ekler. Mesajda {{{{code}}}} yoksa eser kodu otomatik sona eklenir.</small></label></fieldset><fieldset class='admin-settings-section span-2'><legend>Hakkımda bölümü</legend><p class='settings-help'>Ana sayfadaki “Hakkımda” menüsü buraya gelir. Fotoğraf solda, hikâyeniz yanında görünür.</p><div class='admin-settings-about'><div>{input_field('Başlık', 'about_heading', cfg.get('about_heading'), extra="maxlength='160'")}<label>Hayat hikâyesi / tanıtım yazısı<textarea name='about_text' rows='7' maxlength='8000' placeholder='Atölyenizi, sanata yaklaşımınızı ve ilhamınızı anlatın.'>{esc(cfg.get('about_text'))}</textarea><small>Boş satır bırakarak yazıyı paragraflara ayırabilirsiniz.</small></label></div><div><label>Yazının yanında görünecek fotoğraf<input type='file' name='about_image' accept='.jpg,.jpeg,.jfif,.png,.webp'><small>JPG, PNG veya WEBP · en fazla 8 MB</small></label><div class='about-crop-editor' id='about-crop-editor' hidden><div class='about-crop-frame' id='about-crop-frame' aria-label='Fotoğraf kırpma alanı'><img id='about-crop-source' alt='Kırpma önizlemesi'><span class='about-crop-guide' aria-hidden='true'></span></div><label class='about-crop-zoom'>Yakınlaştır<input id='about-crop-zoom' type='range' min='1' max='2.5' step='0.05' value='1'></label><small class='about-crop-help'>Fotoğrafı sürükleyerek kadrajı seçin. Kaydedilen görsel, ana sayfadaki 4:3 fotoğraf alanına göre kırpılır.</small><small class='about-crop-status' id='about-crop-status' role='status'></small></div>{about_image_preview}</div></div></fieldset><fieldset class='admin-settings-section span-2'><legend>Sosyal medya hesapları</legend><div class='admin-settings-socials'>{input_field('Instagram URL', 'instagram_url', cfg.get('instagram_url'), 'url')}{input_field('TikTok URL', 'tiktok_url', cfg.get('tiktok_url'), 'url')}{input_field('Telegram URL', 'telegram_url', cfg.get('telegram_url'), 'url')}</div></fieldset><fieldset class='admin-settings-section span-2'><legend>Ana sayfa sayaçları</legend><p>Değerleri buradan ayarlayabilirsiniz. Bundan sonraki yeni ziyaretler ve eser durumundaki değişiklikler sayaca eklenmeye devam eder.</p><div class='admin-settings-socials'>{stats_fields}</div></fieldset></div><button class='button wide'>Ayarları Kaydet</button></form></section>{accounts_script}{about_crop_script}"""
            return self.send_html(render("Yönetim · Ayarlar", content))
        return self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/shares":
            length = int(self.headers.get("Content-Length", "0"))
            if length > 2048:
                return self.send_json({"error": "İstek çok büyük."}, 413)
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                code = str(data.get("code", "")).strip()[:64]
                if not code:
                    return self.send_json({"error": "Eser kodu gerekli."}, 400)
                now = site_now_string()
                with connect() as c:
                    product = c.execute("SELECT id FROM products WHERE code=? AND archived=0 AND (publish_at='' OR publish_at<=?)", (code, now)).fetchone()
                    if not product:
                        return self.send_json({"error": "Eser bulunamadı."}, 404)
                    c.execute("INSERT INTO product_shares(product_id) VALUES(?)", (product["id"],))
                    count = c.execute("SELECT COUNT(*) FROM product_shares WHERE product_id=?", (product["id"],)).fetchone()[0]
                return self.send_json({"code": code, "count": count}, 201)
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                return self.send_json({"error": "İstek okunamadı."}, 400)
        if path == "/api/comments":
            length = int(self.headers.get("Content-Length", "0"))
            if length > 4 * 1024 * 1024:
                return self.send_json({"error": "Yorum ve profil görseli toplamı 4 MB sınırını aşıyor."}, 413)
            avatar_path = ""
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                code = str(data.get("code", "")).strip()[:64]
                first_name = re.sub(r"\s+", " ", str(data.get("first_name", ""))).strip()
                last_name = re.sub(r"\s+", " ", str(data.get("last_name", ""))).strip()
                body = str(data.get("body", "")).strip()
                visitor = str(data.get("visitor", ""))
                visitor = visitor if re.fullmatch(r"[a-f0-9-]{16,64}", visitor) else ""
                raw_parent = data.get("parent_id")
                parent_id = int(raw_parent) if raw_parent not in (None, "", 0, "0") else None
                if not code or not first_name or len(first_name) > 60 or not last_name or len(last_name) > 60:
                    return self.send_json({"error": "Ad, soyad ve eser bilgisi gerekli. İsimler en fazla 60 karakter olabilir."}, 400)
                if not body or len(body) > 1600:
                    return self.send_json({"error": "Yorum 1–1600 karakter arasında olmalı."}, 400)
                image_data = b""
                image_ext = ""
                avatar = data.get("avatar_data", "")
                if avatar:
                    match = re.fullmatch(r"data:image/(jpeg|png|webp);base64,([A-Za-z0-9+/=]+)", str(avatar))
                    if not match:
                        return self.send_json({"error": "Profil görseli JPG, PNG veya WEBP olmalı."}, 400)
                    image_data = base64.b64decode(match.group(2), validate=True)
                    if not image_data or len(image_data) > 2 * 1024 * 1024:
                        return self.send_json({"error": "Profil görseli en fazla 2 MB olabilir."}, 400)
                    image_ext = {"jpeg": ".jpg", "png": ".png", "webp": ".webp"}[match.group(1)]
                    valid_image = (image_ext == ".jpg" and image_data.startswith(b"\xff\xd8\xff")) or (image_ext == ".png" and image_data.startswith(b"\x89PNG\r\n\x1a\n")) or (image_ext == ".webp" and image_data.startswith(b"RIFF") and image_data[8:12] == b"WEBP")
                    if not valid_image:
                        return self.send_json({"error": "Yüklenen dosya geçerli bir görsel değil."}, 400)
                now = site_now_string()
                with connect() as c:
                    product = c.execute("SELECT id FROM products WHERE code=? AND archived=0 AND (publish_at='' OR publish_at<=?)", (code, now)).fetchone()
                    if not product:
                        return self.send_json({"error": "Eser bulunamadı."}, 404)
                    if parent_id is not None:
                        parent = c.execute("SELECT id FROM product_comments WHERE id=? AND product_id=? AND parent_id IS NULL", (parent_id, product["id"])).fetchone()
                        if not parent:
                            return self.send_json({"error": "Yanıtlanacak yorum bulunamadı."}, 400)
                    if image_data:
                        filename = "comment-" + uuid.uuid4().hex + image_ext
                        target = (UPLOADS / "comments" / filename).resolve()
                        if not target.is_relative_to(UPLOADS.resolve()):
                            return self.send_json({"error": "Profil görseli kaydedilemedi."}, 500)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(image_data)
                        avatar_path = f"uploads/comments/{filename}"
                    cursor = c.execute("""
                        INSERT INTO product_comments(product_id,parent_id,visitor_id,first_name,last_name,body,avatar_path)
                        VALUES(?,?,?,?,?,?,?)
                    """, (product["id"], parent_id, visitor, first_name, last_name, body, avatar_path))
                    comment_id = cursor.lastrowid
                    created = c.execute("SELECT created_at FROM product_comments WHERE id=?", (comment_id,)).fetchone()[0]
                    count = c.execute("SELECT COUNT(*) FROM product_comments WHERE product_id=?", (product["id"],)).fetchone()[0]
                return self.send_json({"comment": {"id": comment_id, "parent_id": parent_id, "first_name": first_name,
                                   "last_name": last_name, "body": body,
                                   "avatar_url": ("/" + avatar_path) if avatar_path else "", "created_at": created},
                                   "count": count}, 201)
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as e:
                if avatar_path:
                    try: (DATA_ROOT / avatar_path).unlink(missing_ok=True)
                    except OSError: pass
                return self.send_json({"error": "Yorum bilgileri okunamadı."}, 400)
        if path == "/api/likes":
            length = int(self.headers.get("Content-Length", "0"))
            if length > 2048:
                return self.send_json({"error": "İstek çok büyük."}, 413)
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                code = str(data.get("code", "")).strip()[:64]
                visitor = str(data.get("visitor", ""))
                liked = data.get("liked")
                if not code or not re.fullmatch(r"[a-f0-9-]{16,64}", visitor) or not isinstance(liked, bool):
                    return self.send_json({"error": "Beğeni bilgisi geçersiz."}, 400)
                with connect() as c:
                    product = c.execute("SELECT id FROM products WHERE code=? AND archived=0", (code,)).fetchone()
                    if not product:
                        return self.send_json({"error": "Eser bulunamadı."}, 404)
                    if liked:
                        c.execute("INSERT OR IGNORE INTO product_likes(product_id,visitor_id) VALUES(?,?)", (product["id"], visitor))
                    else:
                        c.execute("DELETE FROM product_likes WHERE product_id=? AND visitor_id=?", (product["id"], visitor))
                    count = c.execute("SELECT COUNT(*) FROM product_likes WHERE product_id=?", (product["id"],)).fetchone()[0]
                return self.send_json({"code": code, "count": count, "liked": liked})
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                return self.send_json({"error": "İstek okunamadı."}, 400)
        try:
            fields, files = self.parse_form()
        except ValueError as e:
            return self.send_html(render("İstek Hatası", f"<section class='narrow form-card'><h1>İşlem tamamlanamadı</h1><p>{esc(e)}</p><a href='/'>Ana sayfaya dön</a></section>"), 400)
        if path == "/atolye-yonetim-8f31/setup":
            with connect() as c: exists = c.execute("SELECT 1 FROM admin WHERE id=1").fetchone()
            pw = fields.get("password", "")
            if exists: return self.redirect("/atolye-yonetim-8f31/login")
            if len(pw) < 10 or pw != fields.get("confirm"):
                return self.send_html(render("İlk Kurulum", "<section class='narrow form-card'><h1>Parolalar eşleşmiyor</h1><p>En az 10 karakterli, aynı parolayı tekrar girin.</p><a href='/atolye-yonetim-8f31/setup'>Geri dön</a></section>"), 400)
            salt = secrets.token_bytes(16)
            digest = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 310000)
            stored = base64.b64encode(salt + digest).decode()
            with connect() as c: c.execute("INSERT INTO admin(id,password_hash) VALUES(1,?)", (stored,))
            return self.redirect("/atolye-yonetim-8f31/login")
        if path == "/atolye-yonetim-8f31/login":
            with connect() as c: row = c.execute("SELECT password_hash FROM admin WHERE id=1").fetchone()
            if row:
                try:
                    raw = base64.b64decode(row["password_hash"])
                    digest = hashlib.pbkdf2_hmac("sha256", fields.get("password", "").encode(), raw[:16], 310000)
                    if hmac.compare_digest(raw[16:], digest):
                        csrf = secrets.token_urlsafe(24)
                        payload = base64.urlsafe_b64encode(json.dumps({"id":1,"csrf":csrf,"exp":time.time()+86400*7}).encode()).decode().rstrip("=")
                        sig = hmac.new(settings()["session_secret"].encode(), payload.encode(), hashlib.sha256).hexdigest()
                        return self.redirect("/atolye-yonetim-8f31/products", [("Set-Cookie", f"gallery_admin={payload}.{sig}; HttpOnly; SameSite=Lax; Path=/; Max-Age=604800")])
                except Exception: pass
            return self.send_html(render("Giriş Hatası", "<section class='narrow form-card'><h1>Parola hatalı</h1><p>Yönetici parolasını kontrol edip yeniden deneyin.</p><a href='/atolye-yonetim-8f31/login'>Geri dön</a></section>"), 401)
        if path.startswith("/atolye-yonetim-8f31/"):
            admin = self.get_admin()
            if not admin: return self.redirect("/atolye-yonetim-8f31/login")
            if not self.csrf_ok(fields):
                message = "<section class='narrow form-card'><h1>İstek doğrulanamadı</h1><p>Güvenlik anahtarı geçersiz veya süresi dolmuş. Sayfayı yenileyip tekrar deneyin.</p><a href='/atolye-yonetim-8f31/products'>Yönetim paneline dön</a></section>"
                return self.send_html(render("İstek doğrulanamadı", message), 403)
        if path == "/atolye-yonetim-8f31/products/save":
            try:
                def form_value(*names):
                    for name in names:
                        value = fields.get(name, "")
                        if isinstance(value, (list, tuple)):
                            value = next((item for item in reversed(value) if str(item).strip()), "")
                        value = str(value or "").strip()
                        if value:
                            return value
                    return ""

                pid = int(form_value("id") or 0)
                code_digits = form_value("code_digits")
                if code_digits:
                    existing_code = ""
                    if pid:
                        with connect() as c:
                            existing = c.execute("SELECT code FROM products WHERE id=?", (pid,)).fetchone()
                        existing_code = existing["code"] if existing else ""
                    code = product_code_from_digits(code_digits, existing_code)
                else:
                    # Accept a previously opened form while enforcing a valid prefix + digit format.
                    code = form_value("code").upper()[:30]
                    if code and not re.fullmatch(r"[A-Z]+-[0-9]+", code):
                        raise ValueError("Eser kodu harfli bir ön ek ve yalnızca rakamlardan oluşmalıdır.")
                title = form_value("title")[:120]
                width_text, height_text = form_value("width"), form_value("height")
                unit = (form_value("size_unit") or "cm")[:8]
                size = ""
                if width_text and height_text:
                    try:
                        width, height = int(width_text), int(height_text)
                    except ValueError:
                        width = height = 0
                    if 0 < width <= 500 and 0 < height <= 500:
                        size = f"{width}x{height} {unit}"
                else:
                    # Accept older admin forms that submitted a single formatted size field.
                    legacy_size = form_value("size", "dimensions", "measurement")
                    match = re.fullmatch(r"\s*(\d+)\s*[x×]\s*(\d+)\s*(cm|mm|inç|inch)?\s*", legacy_size, re.I)
                    if match:
                        size_unit = (match.group(3) or unit).lower()
                        size_unit = "inç" if size_unit == "inch" else size_unit
                        size = f"{int(match.group(1))}x{int(match.group(2))} {size_unit}"
                category = ""
                publish_at = form_value("publish_at")
                if publish_at:
                    try: publish_at = datetime.fromisoformat(publish_at).strftime("%Y-%m-%dT%H:%M")
                    except ValueError: raise ValueError("Yayın tarihi ve saati geçerli değil.")
                try:
                    price = int(form_value("price") or "-1")
                    sale_text = form_value("sale_price")
                    sale = int(sale_text) if sale_text else None
                except ValueError:
                    raise ValueError("Liste ve indirim fiyatlarını tam sayı olarak girin.")
                desc = form_value("description")[:1500]
                inspect_title = form_value("inspect_title", "review_title")[:160]
                article = form_value("article", "story", "review_article")[:12000]
                wa = safe_url(form_value("whatsapp_url"))
                account_choice = form_value("whatsapp_account")
                if account_choice:
                    try:
                        selected_account = int(account_choice)
                    except ValueError:
                        raise ValueError("Seçilen WhatsApp hesabı geçerli değil.")
                    saved_accounts = parse_whatsapp_accounts(settings().get("whatsapp_accounts", "[]"))
                    if selected_account < 0 or selected_account >= len(saved_accounts):
                        raise ValueError("Seçilen WhatsApp hesabı bulunamadı. Ayarlardan hesabı yeniden seçin.")
                    wa = saved_accounts[selected_account]["url"]
                missing = []
                if not code: missing.append("eser kodu")
                if not title: missing.append("eser adı")
                if not size: missing.append("geçerli ölçü (genişlik × yükseklik)")
                if price < 0: missing.append("geçerli liste fiyatı")
                if missing: raise ValueError("Eksik veya geçersiz alan: " + ", ".join(missing) + ".")
                image = self.upload_file(files.get("image"), "works", "work-")
                featured, sold = int(fields.get("featured") == "1"), int(fields.get("sold") == "1")
                show_new = int(fields.get("show_new") == "1")
                show_collections = 0
                show_curated = int(fields.get("show_curated") == "1")
                with connect() as c:
                    if pid:
                        old = c.execute("SELECT image,category,show_collections FROM products WHERE id=?", (pid,)).fetchone()
                        if not old: return self.send_error(404)
                        image = image or old["image"]
                        category = old["category"]
                        show_collections = old["show_collections"]
                        c.execute("UPDATE products SET code=?,title=?,size=?,price=?,sale_price=?,category=?,description=?,inspect_title=?,article=?,image=?,whatsapp_url=?,featured=?,sold=?,show_new=?,show_collections=?,show_curated=?,publish_at=? WHERE id=?", (code,title,size,price,sale,category,desc,inspect_title,article,image,wa,featured,sold,show_new,show_collections,show_curated,publish_at,pid))
                    else:
                        c.execute("INSERT INTO products(code,title,size,price,sale_price,category,description,inspect_title,article,image,whatsapp_url,featured,sold,show_new,show_collections,show_curated,publish_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (code,title,size,price,sale,category,desc,inspect_title,article,image,wa,featured,sold,show_new,show_collections,show_curated,publish_at))
                return self.redirect("/atolye-yonetim-8f31/products")
            except (ValueError, sqlite3.IntegrityError) as e:
                return self.send_html(render("Tablo Kaydedilemedi", f"<section class='narrow form-card'><h1>Tablo kaydedilemedi</h1><p>{esc(e) or 'Eser kodu başka bir tabloda kullanılıyor.'}</p><p>Girdiğin bilgileri korumak için forma geri dön.</p><button class='button ghost' type='button' onclick='history.back()'>Forma geri dön</button> <a href='/atolye-yonetim-8f31/products'>Tablolara dön</a></section>"), 400)
        delete_product = re.fullmatch(r"/atolye-yonetim-8f31/products/(\d+)/delete", path)
        if delete_product:
            product_id = int(delete_product.group(1))
            with connect() as c:
                product = c.execute("SELECT image FROM products WHERE id=?", (product_id,)).fetchone()
                if not product:
                    return self.send_error(404)
                comment_avatars = [row[0] for row in c.execute("SELECT avatar_path FROM product_comments WHERE product_id=? AND avatar_path<>''", (product_id,)).fetchall()]
                image = product["image"] or ""
                shared_image = c.execute("SELECT 1 FROM products WHERE image=? AND id<>? LIMIT 1", (image, product_id)).fetchone() if image else None
                if image and not shared_image:
                    image_path = (DATA_ROOT / image).resolve()
                    if image_path.is_relative_to(UPLOADS.resolve()) and image_path.is_file():
                        try:
                            image_path.unlink()
                        except OSError:
                            return self.send_html(render("Silme Tamamlanamadı", "<section class='narrow form-card'><h1>Görsel silinemedi</h1><p>Eser kaydı korunuyor. Görsel dosyası kullanımda olabilir; tekrar deneyin.</p><a href='/atolye-yonetim-8f31/products'>Tablolara dön</a></section>"), 500)
                for avatar in comment_avatars:
                    avatar_file = (DATA_ROOT / avatar).resolve()
                    if avatar_file.is_relative_to(UPLOADS.resolve()) and avatar_file.is_file():
                        try:
                            avatar_file.unlink()
                        except OSError:
                            return self.send_html(render("Silme Tamamlanamadı", "<section class='narrow form-card'><h1>Yorum fotoğrafı silinemedi</h1><p>Eser kaydı korunuyor. Yorum görseli kullanımda olabilir; tekrar deneyin.</p><a href='/atolye-yonetim-8f31/products'>Tablolara dön</a></section>"), 500)
                c.execute("DELETE FROM product_likes WHERE product_id=?", (product_id,))
                c.execute("DELETE FROM products WHERE id=?", (product_id,))
            return self.redirect("/atolye-yonetim-8f31/products")
        archive = re.fullmatch(r"/atolye-yonetim-8f31/products/(\d+)/archive", path)
        if archive:
            with connect() as c: c.execute("UPDATE products SET archived=1 WHERE id=?", (int(archive.group(1)),))
            return self.redirect("/atolye-yonetim-8f31/products")
        unarchive = re.fullmatch(r"/atolye-yonetim-8f31/products/(\d+)/unarchive", path)
        if unarchive:
            with connect() as c: c.execute("UPDATE products SET archived=0 WHERE id=?", (int(unarchive.group(1)),))
            return self.redirect("/atolye-yonetim-8f31/products")
        mark_sold = re.fullmatch(r"/atolye-yonetim-8f31/products/(\d+)/sold", path)
        if mark_sold:
            with connect() as c: c.execute("UPDATE products SET sold=CASE sold WHEN 1 THEN 0 ELSE 1 END WHERE id=?", (int(mark_sold.group(1)),))
            return self.redirect("/atolye-yonetim-8f31/products")
        if path == "/atolye-yonetim-8f31/settings":
            actual_stats = actual_site_stats()
            current_stats = display_site_stats(settings(), actual_stats)
            stat_offsets = {}
            for stat_name in ("visitors", "sold", "available"):
                form_name = "stat_" + stat_name
                raw_total = str(fields.get(form_name, current_stats[stat_name])).strip()
                if not re.fullmatch(r"[0-9]{1,12}", raw_total):
                    message = esc("Sayaç değerleri yalnızca 0–12 basamaklı tam sayı olabilir.")
                    return self.send_html(render("Sayaçlar kaydedilemedi", f"<section class='narrow form-card'><h1>Sayaçlar kaydedilemedi</h1><p>{message}</p><a href='/atolye-yonetim-8f31/settings'>Ayarlara dön</a></section>"), 400)
                stat_offsets["stat_" + stat_name + "_offset"] = str(int(raw_total) - int(actual_stats[stat_name]))
            try:
                raw_accounts = json.loads(fields.get("whatsapp_accounts", "[]") or "[]")
                if not isinstance(raw_accounts, list) or len(raw_accounts) > 20:
                    raise ValueError("En fazla 20 WhatsApp hesabı kaydedebilirsiniz.")
                cleaned_accounts = []
                for item in raw_accounts:
                    if not isinstance(item, dict):
                        raise ValueError("WhatsApp hesabı bilgileri geçersiz.")
                    name = str(item.get("name", "")).strip()[:60]
                    raw_url = str(item.get("url", "")).strip()[:500]
                    if not name and not raw_url:
                        continue
                    url = safe_url(raw_url)
                    if not name or not url:
                        raise ValueError("Her WhatsApp hesabı için ad ve http(s) bağlantısı girin.")
                    cleaned_accounts.append({"name": name, "url": url})
            except (json.JSONDecodeError, ValueError) as error:
                message = esc(error) or "WhatsApp hesapları kaydedilemedi."
                return self.send_html(render("Ayarlar kaydedilemedi", f"<section class='narrow form-card'><h1>Ayarlar kaydedilemedi</h1><p>{message}</p><a href='/atolye-yonetim-8f31/settings'>Ayarlara dön</a></section>"), 400)
            new_about_image = ""
            try:
                if files.get("about_image", {}).get("filename"):
                    new_about_image = self.upload_file(files["about_image"], "about", "about-")
            except ValueError as error:
                message = esc(error)
                return self.send_html(render("Fotoğraf kaydedilemedi", f"<section class='narrow form-card'><h1>Fotoğraf kaydedilemedi</h1><p>{message}</p><a href='/atolye-yonetim-8f31/settings'>Ayarlara dön</a></section>"), 400)
            old_about_image = settings().get("about_image", "")
            allowed = ("site_name", "whatsapp_url", "instagram_url", "tiktok_url", "telegram_url", "question_message", "about_heading", "about_text")
            with connect() as c:
                for key in allowed:
                    val = fields.get(key, "").strip()
                    if key.endswith("_url"): val = safe_url(val)
                    max_length = 8000 if key == "about_text" else (1000 if key == "question_message" else (160 if key == "about_heading" else 500))
                    c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key,val[:max_length]))
                c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('whatsapp_accounts',?)", (json.dumps(cleaned_accounts, ensure_ascii=False),))
                for key, value in stat_offsets.items():
                    c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, value))
                if new_about_image:
                    c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('about_image',?)", (new_about_image,))
            if new_about_image and old_about_image and re.fullmatch(r"uploads/about/[A-Za-z0-9._-]+", old_about_image):
                old_image_path = (DATA_ROOT / old_about_image).resolve()
                if old_image_path.is_relative_to(UPLOADS.resolve() / "about"):
                    try:
                        old_image_path.unlink(missing_ok=True)
                    except OSError:
                        pass
            return self.redirect("/atolye-yonetim-8f31/settings")
        return self.send_error(404)


def admin_nav(active):
    links = (("products", "Tablolar", "/atolye-yonetim-8f31/products"), ("settings", "Site Ayarları", "/atolye-yonetim-8f31/settings"))
    return "<nav class='admin-nav'>" + "".join(f"<a class='{'active' if key==active else ''}' href='{url}'>{label}</a>" for key,label,url in links) + "<a href='/atolye-yonetim-8f31/logout'>Çıkış</a></nav>"


if __name__ == "__main__":
    init_db()
    host = os.environ.get("GALLERY_HOST", "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1")
    port = int(os.environ.get("PORT", os.environ.get("GALLERY_PORT", "8000")))
    print(f"Sanat Atölyesi is running at http://{host}:{port}")
    print("First visit: /atolye-yonetim-8f31/setup to create the administrator password.")
    ThreadingHTTPServer((host, port), SiteHandler).serve_forever()

