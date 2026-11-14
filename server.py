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
from datetime import date, datetime
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlencode, urlparse

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
        CREATE INDEX IF NOT EXISTS product_comments_product_idx ON product_comments(product_id, id);
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
            "tiktok_url": "", "telegram_url": "", "categories": "Çiçekler, Manzaralar, Yumuşak Tonlar",
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


def esc(s):
    return html.escape(str(s or ""), quote=True)


def money(n):
    return f"₺{int(n or 0):,}".replace(",", ".")


def product_sections(product):
    choices = (("show_new", "Yeni Gelenler"), ("show_collections", "Koleksiyonlar"), ("show_curated", "Sanatçının Seçkisi"))
    return " · ".join(label for key, label in choices if product[key]) or "Seçilmedi"


def admin_product_row(product, csrf, likes, archived=False):
    code = product["code"]
    product_id = product["id"]
    code_cell = f"<code>{esc(code)}</code> <button type='button' class='copy-code' data-copy='{esc(code)}' title='Eser kodunu kopyala' aria-label='Eser kodunu kopyala'>Kopyala</button>"
    if archived:
        state = "Arşivde"
        actions = f"<a href='/atolye-yonetim-8f31/products/{product_id}'>Düzenle</a> · <form class='inline-form' method='post' action='/atolye-yonetim-8f31/products/{product_id}/unarchive'><input type='hidden' name='csrf' value='{csrf}'><button class='text-button'>Arşivden Çıkar</button></form>"
    else:
        state = "Taslak" if product["publish_at"] and product["publish_at"] > date.today().isoformat() else ("Satıldı" if product["sold"] else "Yayında")
        sold_button = "Satışa Aç" if product["sold"] else "Satıldı Olarak İşaretle"
        actions = f"<a href='/atolye-yonetim-8f31/products/{product_id}'>Düzenle</a> · <form class='inline-form' method='post' action='/atolye-yonetim-8f31/products/{product_id}/sold'><input type='hidden' name='csrf' value='{csrf}'><button class='text-button'>{sold_button}</button></form> · <form class='inline-form' method='post' action='/atolye-yonetim-8f31/products/{product_id}/archive'><input type='hidden' name='csrf' value='{csrf}'><button class='text-button'>Arşivle</button></form>"
    actions += f" · <form class='inline-form' method='post' action='/atolye-yonetim-8f31/products/{product_id}/delete' onsubmit='return confirm(&quot;Eser kalıcı olarak silinecek; görseli, beğeni kayıtları ve yorumları da kaldırılacak. Bu işlem geri alınamaz.&quot;)'><input type='hidden' name='csrf' value='{csrf}'><button class='text-button delete-button'>Sil</button></form>"
    status = f"{state}{(' · '+esc(product['publish_at'])) if product['publish_at'] else ''}"
    return f"<tr><td>{code_cell}</td><td>{esc(product['title'])}</td><td>{esc(product['size'])}</td><td>{esc(product['category'])}</td><td>{money(product['sale_price'] or product['price'])}</td><td>{likes} ♥</td><td>{esc(product_sections(product))}</td><td>{status}</td><td>{actions}</td></tr>"


def safe_url(value):
    v = (value or "").strip()
    return v if v.startswith(("https://", "http://")) else ""


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
    return f"<article class='product-card'>{badge}<div class='art-frame'>{image}</div><div class='product-info'><span class='product-code'>{esc(product['code'])}</span><h3>{esc(product['title'])}</h3><p>{esc(product['size'])} · {esc(product['category'])}</p><p class='product-price'>{old}<b>{money(price)}</b></p><p class='description'>{esc(product['description'])}</p><div class='actions'>{buy}</div>{like}</div></article>"


def product_cards(rows):
    return "".join(artwork(row) for row in rows) or "<p class='empty'>Bu bölümde henüz eser yok.</p>"


def render_legacy_home():
    """Keep the supplied homepage and continuously bind its artwork to the admin catalog."""
    return """<!doctype html><html lang='tr'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Perihan Baktaş | Sanat Atölyesi</title><style>
    *{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;overflow:hidden}iframe{display:block;width:100%;height:100%;border:0;background:#fbf8f3;opacity:0;transition:opacity .7s ease}.page-loader{position:fixed;inset:0;z-index:100;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:7px;background:radial-gradient(ellipse at 20% 22%,#f9e7ec 0,transparent 29%),radial-gradient(ellipse at 82% 76%,#e7eee9 0,transparent 28%),#fbf8f3;color:#344b43;transition:opacity .55s ease,visibility .55s ease}.page-loader.is-hidden{opacity:0;visibility:hidden;pointer-events:none}.loader-bloom{position:relative;width:72px;height:72px;margin-bottom:10px;color:#e9a2b9;font:64px/1 Georgia,serif;animation:loader-bloom-turn 5s ease-in-out infinite}.loader-bloom:before{content:'✿';position:absolute;inset:0;display:grid;place-items:center;text-shadow:0 7px 18px #d889a944}.loader-bloom:after{content:'';position:absolute;width:9px;height:9px;left:32px;top:32px;border-radius:50%;background:#f3c966}.page-loader strong{font:600 23px/1.2 Georgia,serif;color:#3f5a46}.page-loader p{margin:0;color:#827783;font:13px/1.5 Arial,sans-serif}.loader-brush-line{width:160px;height:3px;margin-top:14px;border-radius:9px;background:#eadfd6;overflow:hidden}.loader-brush-line i{display:block;width:45%;height:100%;border-radius:9px;background:linear-gradient(90deg,#e9a2b9,#79546f,#e9a2b9);transform-origin:left;animation:loader-brush-sweep 1.6s ease-in-out infinite alternate}@keyframes loader-bloom-turn{0%,100%{transform:rotate(-8deg) scale(.94)}50%{transform:rotate(9deg) scale(1.04)}}@keyframes loader-brush-sweep{from{transform:translateX(-8%)}to{transform:translateX(135%)}}@media(prefers-reduced-motion:reduce){.loader-bloom,.loader-brush-line i{animation-duration:.01ms!important;animation-iteration-count:1!important}}
    </style></head><body><iframe id='legacy-home' src='/legacy-homepage.html' title='Perihan Baktaş sanat galerisi'></iframe><div class='page-loader' id='page-loader' role='status' aria-live='polite'><div class='loader-bloom' aria-hidden='true'></div><strong>Atölye hazırlanıyor</strong><p>Sanat eserleri yükleniyor…</p><span class='loader-brush-line' aria-hidden='true'><i></i></span></div><script>
    (function(){var frame=document.getElementById('legacy-home'),loader=document.getElementById('page-loader'),busy=false,lastSignature='',filter={category:'',price:'',sort:'new'};function revealPage(){if(frame)frame.style.opacity='1';if(loader){loader.classList.add('is-hidden');loader.setAttribute('aria-hidden','true')}}window.setTimeout(revealPage,15000);
    var likeVisitor=(function(){var key='perihan-gallery-visitor';try{var id=localStorage.getItem(key);if(!id){id=(window.crypto&&crypto.randomUUID)?crypto.randomUUID():'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g,function(c){var r=Math.random()*16|0;return(c==='x'?r:(r&3|8)).toString(16)});localStorage.setItem(key,id)}return id}catch(e){return 'session-'+Math.random().toString(16).slice(2)+Date.now().toString(16)}})();
    function setLikeState(d,code,value){window.__publicLikes=window.__publicLikes||{};window.__publicLikes[code]=value;Array.from(d.querySelectorAll('.like-button')).forEach(function(b){if(b.dataset.likeCode!==code)return;b.dataset.liked=value.liked?'1':'0';b.setAttribute('aria-pressed',value.liked?'true':'false');b.setAttribute('aria-label',value.count+' beğeni'+(value.liked?', beğendin':''));var n=b.querySelector('.like-count');if(n)n.textContent=value.count})}
    function setCommentCount(d,code,count){window.__publicCommentCounts=window.__publicCommentCounts||{};window.__publicCommentCounts[code]=Number(count||0);Array.from(d.querySelectorAll('.comment-button')).forEach(function(b){if(b.dataset.commentCode!==code)return;var n=b.querySelector('.comment-count');if(n)n.textContent=String(count||0);b.setAttribute('aria-label',String(count||0)+' yorum')})}
    function ensureLikeRow(d,card,code){var ct=card.querySelector('.ct');if(!ct)return;var row=ct.querySelector('.like-row');if(!row){row=d.createElement('div');row.className='like-row';var actions=ct.querySelector('.card-actions');if(actions)actions.insertAdjacentElement('afterend',row);else ct.appendChild(row)}var b=row.querySelector('.like-button');if(!b){row.insertAdjacentHTML('afterbegin','<button type="button" class="like-button" data-like-code="" data-liked="0" aria-pressed="false" aria-label="0 beğeni"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8l1.1 1.1L12 21l7.8-7.5 1.1-1.1a5.5 5.5 0 0 0-.1-7.8Z"/></svg><span class="like-count">0</span></button>');b=row.querySelector('.like-button')}var comment=row.querySelector('.comment-button');if(!comment){comment=d.createElement('button');comment.type='button';comment.className='comment-button';comment.setAttribute('aria-label','0 yorum');comment.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 11.5a8.4 8.4 0 0 1-12.7 7.2L3 20l1.4-4.1A8.4 8.4 0 1 1 20 11.5Z"/><path d="M8 11h8M8 14h5"/></svg><span class="comment-count">0</span>';row.appendChild(comment)}b.dataset.likeCode=code;comment.dataset.commentCode=code;var state=(window.__publicLikes||{})[code]||{count:0,liked:false};setLikeState(d,code,state);setCommentCount(d,code,(window.__publicCommentCounts||{})[code]||0)}
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
      info.appendChild(detailNode(d,'p','art-detail-code',(p.code||'')+(p.category?' · '+p.category:'')));
      var facts=detailNode(d,'div','art-detail-facts');
      var size=detailNode(d,'div','',null);size.appendChild(detailNode(d,'span','', 'Ölçü'));size.appendChild(detailNode(d,'b','',p.size||'Bilgi için bize yazın'));facts.appendChild(size);
      var price=Number(p.sale_price&&Number(p.sale_price)<Number(p.price)?p.sale_price:p.price);var cost=detailNode(d,'div','',null);cost.appendChild(detailNode(d,'span','', 'Fiyat'));cost.appendChild(detailNode(d,'b','',fmt(price)));facts.appendChild(cost);info.appendChild(facts);
      info.appendChild(detailNode(d,'h3','art-detail-story-title','Eserin hikâyesi'));
      info.appendChild(detailNode(d,'p','art-detail-story',p.article||p.description||'Bu eser hakkında daha fazla bilgi almak için bize yazabilirsiniz.'));
      var question=detailNode(d,'div','art-detail-question');question.appendChild(detailNode(d,'b','', 'Bu tablo hakkında bir sorunuz mu var?'));question.appendChild(detailNode(d,'p','', 'Ölçü, renk ve sipariş ayrıntılarını atölyeye danışın.'));
      var ask=detailNode(d,'a','art-detail-ask','Bu eser hakkında soru sor');var contact=p.whatsapp_url||cfg.whatsapp_url||'#iletisim';ask.href=contact;
      if(contact.indexOf('http')===0){try{var url=new URL(contact,d.location.href);url.searchParams.set('text','Merhaba, '+p.title+' ('+p.code+') eseri hakkında bilgi almak istiyorum.');ask.href=url.href;ask.target='_blank';ask.rel='noopener'}catch(ignore){}}
      question.appendChild(ask);info.appendChild(question);
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
    function install(d){if(d.getElementById('admin-live-catalog'))return;var style=d.getElementById('admin-catalog-sync');if(!style){style=d.createElement('style');style.id='admin-catalog-sync';style.textContent='del,s{color:#b9b1b5!important;opacity:.58!important}#admin-live-catalog{max-width:1160px;margin:42px auto 56px;padding:0 24px;text-align:center}#admin-live-catalog h2{font:700 30px Georgia,serif;color:#3f5a46;margin:0 0 8px}#admin-live-catalog .admin-catalog-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,240px),250px));justify-content:center;gap:20px;margin-top:20px}.admin-filter-menu button{display:block;width:100%;border:0;background:transparent;text-align:left;cursor:pointer}#admin-live-catalog .card[hidden]{display:none!important}.editorial-section .editorial-grid,.editorial-section .curated-grid{grid-template-columns:repeat(auto-fit,minmax(min(100%,240px),280px))!important;justify-content:center!important}.editorial-section .card{width:100%;max-width:280px;min-width:0;justify-self:center}#koleksiyonlar .collection-art-grid{max-width:1000px;margin:24px auto 0;grid-template-columns:repeat(auto-fit,minmax(min(100%,240px),280px));justify-content:center;gap:20px}#koleksiyonlar .collection-art-grid .card{width:100%;max-width:280px;min-width:0;justify-self:center}.like-row{display:flex;justify-content:flex-end;margin-top:5px}.like-button{display:inline-flex;align-items:center;justify-content:center;gap:6px;min-width:44px;padding:5px 8px;border:0;border-radius:999px;background:transparent;color:#927282;font:700 12px/1 Arial,sans-serif;cursor:pointer;transition:color .18s ease,background .18s ease,transform .18s ease}.like-button:hover{background:#fbf0f3;color:#d64f79;transform:translateY(-1px)}.like-button svg{width:19px;height:19px;fill:transparent;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round;transition:fill .18s ease,transform .18s ease}.like-button[aria-pressed=true]{color:#df4f7b}.like-button[aria-pressed=true] svg{fill:currentColor;transform:scale(1.06)}.like-button:disabled{opacity:.62;cursor:wait}.like-button:focus-visible{outline:2px solid #b87b96;outline-offset:2px}@media(max-width:600px){#admin-live-catalog{padding:0 14px}}.art-frame{height:auto!important;aspect-ratio:3/4;background:#f2eee9}.art-frame img{object-fit:contain!important}.fw .art,#sold-works-grid .art,#admin-live-catalog .art,#yeni-gelenler .art,#sanatcinin-secimi .art,.editorial-section .art,#koleksiyonlar .collection-art-grid .art{aspect-ratio:3/4!important}';d.head.appendChild(style)}
    var detailStyle=d.getElementById('art-detail-style');if(!detailStyle){detailStyle=d.createElement('style');detailStyle.id='art-detail-style';detailStyle.textContent=`.art-detail-overlay{position:fixed;inset:0;z-index:99999;display:grid;place-items:center;padding:24px;background:rgba(42,34,39,.58);backdrop-filter:blur(6px);animation:detail-backdrop-in .25s ease both}.art-detail-panel{position:relative;width:min(1080px,100%);max-height:88vh;display:grid;grid-template-columns:minmax(0,1.05fr) minmax(320px,.95fr);background:#fffdf9;border:1px solid #efe2dc;border-radius:24px;overflow:auto;box-shadow:0 28px 90px rgba(36,27,33,.3);animation:detail-panel-in .55s cubic-bezier(.2,.8,.2,1) both}.art-detail-art{min-width:0;min-height:520px;padding:24px;display:grid;place-items:center;background:linear-gradient(145deg,#f5eee9,#f8f2ed)}.art-detail-art img{display:block;width:100%;height:100%;max-height:78vh;object-fit:contain;animation:artwork-expand-left .72s cubic-bezier(.2,.8,.2,1) both}.art-detail-art>.art{width:100%;height:100%;aspect-ratio:3/4!important}.art-detail-info{padding:clamp(26px,4vw,50px);align-self:center}.art-detail-kicker{font:700 10px Arial,sans-serif;letter-spacing:.2em;color:#a5637e}.art-detail-info h2{margin:12px 40px 6px 0;color:#344b43;font:600 clamp(27px,3.4vw,42px)/1.12 Georgia,serif}.art-detail-product-name{margin:0;color:#756a74;font-size:15px}.art-detail-code{margin:8px 0 20px;color:#927282;font-size:12px;letter-spacing:.05em}.art-detail-facts{display:flex;gap:28px;padding:15px 0;border-block:1px solid #eee3dc}.art-detail-facts div{display:grid;gap:3px}.art-detail-facts span{font-size:11px;color:#827783}.art-detail-facts b{font-size:16px;color:#486454}.art-detail-story-title{margin:20px 0 6px;color:#344b43;font:600 20px Georgia,serif}.art-detail-story{margin:0;color:#746d75;font-size:14px;line-height:1.75;white-space:pre-line}.art-detail-question{margin-top:22px;padding:17px;background:#f8eff1;border-radius:16px}.art-detail-question>b{color:#503f4b;font-size:14px}.art-detail-question>p{margin:5px 0 12px;color:#827783;font-size:12px}.art-detail-ask{display:inline-flex;align-items:center;justify-content:center;min-height:43px;padding:10px 17px;border-radius:24px;background:#486454;color:white;font-size:12px;font-weight:700}.art-detail-ask:hover{background:#354d41;color:white;transform:translateY(-1px)}.art-detail-close{position:absolute;right:14px;top:14px;z-index:2;width:42px;height:42px;border:1px solid #eadfd6;border-radius:50%;background:#fff;color:#79546f;font-size:27px;line-height:1;cursor:pointer}.art-detail-close:hover{background:#f8eff1}.art-detail-panel:has(.art-detail-close:focus-visible),.art-detail-close:focus-visible,.art-detail-ask:focus-visible{outline:3px solid #bd8ca3;outline-offset:3px}@keyframes detail-backdrop-in{from{opacity:0}to{opacity:1}}@keyframes detail-panel-in{from{opacity:0;transform:translateY(18px) scale(.94)}to{opacity:1;transform:translateY(0) scale(1)}}@keyframes artwork-expand-left{from{opacity:.35;transform:translate3d(36px,12px,0) scale(.66);transform-origin:left center}to{opacity:1;transform:translate3d(0,0,0) scale(1);transform-origin:left center}}.art-detail-overlay.is-closing{animation:detail-backdrop-out .22s ease both}.art-detail-overlay.is-closing .art-detail-panel{animation:detail-panel-out .22s ease both}@keyframes detail-backdrop-out{to{opacity:0}}@keyframes detail-panel-out{to{opacity:0;transform:translateY(8px) scale(.97)}}@media(max-width:720px){.art-detail-overlay{padding:10px}.art-detail-panel{grid-template-columns:1fr;max-height:94vh;border-radius:18px}.art-detail-art{min-height:0;height:38vh;max-height:340px;padding:14px}.art-detail-art img{max-height:36vh}.art-detail-info{padding:22px 20px 24px}.art-detail-info h2{font-size:29px}.art-detail-facts{gap:22px}}@media(prefers-reduced-motion:reduce){.art-detail-overlay,.art-detail-panel,.art-detail-art img{animation-duration:.01ms!important;animation-iteration-count:1!important}}`;d.head.appendChild(detailStyle)}
    var commentStyle=d.getElementById('gallery-comment-style');if(!commentStyle){commentStyle=d.createElement('style');commentStyle.id='gallery-comment-style';commentStyle.textContent='.like-row{align-items:center;gap:5px}.comment-button{display:inline-flex;align-items:center;justify-content:center;gap:5px;min-width:44px;padding:5px 8px;border:0;border-radius:999px;background:transparent;color:#927282;font:700 12px/1 Arial,sans-serif;cursor:pointer;transition:color .18s ease,background .18s ease,transform .18s ease}.comment-button:hover{background:#f7eef3;color:#79546f;transform:translateY(-1px)}.comment-button svg{width:19px;height:19px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}.comment-button:focus-visible,.art-comment-form button:focus-visible{outline:2px solid #b87b96;outline-offset:2px}.art-comments{margin-top:22px;padding-top:20px;border-top:1px solid #eee3dc}.art-comments-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:13px}.art-comments-head h3{margin:0;color:#344b43;font:600 21px Georgia,serif}.art-comments-count{color:#927282;font-size:12px}.art-comment-list{display:grid;gap:12px;margin:0 0 18px}.art-comment-thread{padding-bottom:12px;border-bottom:1px solid #f0e8e2}.art-comment,.art-comment-reply{display:grid;grid-template-columns:38px minmax(0,1fr);align-items:start;gap:10px}.art-comment-avatar,.art-comment-avatar-preview{width:38px;height:38px;overflow:hidden;display:grid;place-items:center;border-radius:50%;background:linear-gradient(145deg,#f6dce5,#e6ede4);color:#79546f;font-size:12px;font-weight:700}.art-comment-avatar img,.art-comment-avatar-preview img{width:100%;height:100%;object-fit:cover}.art-comment-content{min-width:0}.art-comment-meta{display:flex;align-items:baseline;gap:9px;flex-wrap:wrap}.art-comment-meta strong{color:#344b43;font-size:12px}.art-comment-meta time{color:#9a9097;font-size:10px}.art-comment-text{margin:4px 0 0;color:#625b63;font-size:12px;line-height:1.65;white-space:pre-wrap;overflow-wrap:anywhere}.art-comment-actions button,.art-comment-cancel{border:0;background:none;color:#79546f;padding:5px 0;font-size:11px;font-weight:700;cursor:pointer}.art-comment-actions button:hover,.art-comment-cancel:hover{text-decoration:underline}.art-comment-replies{display:grid;gap:11px;margin:10px 0 0 48px;padding-left:13px;border-left:2px solid #f1e3e9}.art-comment-reply .art-comment-avatar{width:32px;height:32px}.art-comment-form{padding:15px;border:1px solid #ece1dc;border-radius:15px;background:#fdf9f7}.art-comment-form-head{display:flex;align-items:center;justify-content:space-between;gap:8px;color:#344b43;font-size:13px}.art-comment-name-fields{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-top:12px}.art-comment-name-fields label,.art-comment-body-label,.art-comment-photo-label{display:grid;gap:5px;color:#6d626a;font-size:10px;font-weight:600}.art-comment-name-fields input,.art-comment-body-label textarea{width:100%;border:1px solid #e5d9d4;border-radius:9px;background:#fff;padding:9px 10px;color:#3f4843;font:12px Arial,sans-serif}.art-comment-body-label{margin-top:9px}.art-comment-body-label textarea{resize:vertical;min-height:68px}.art-comment-photo-row{display:flex;align-items:center;gap:10px;margin-top:10px}.art-comment-photo-label input{max-width:100%;font-size:10px}.art-comment-status,.art-comment-reply-notice{margin:8px 0 0;color:#79546f;font-size:11px}.art-comment-submit{margin-top:10px;padding:9px 14px;border:0;border-radius:22px;background:#486454;color:#fff;font-size:11px;font-weight:700;cursor:pointer}.art-comment-submit:disabled{opacity:.6;cursor:wait}.art-comments-empty,.art-comments-loading{margin:0;padding:12px 0;color:#827783;font-size:12px}@media(max-width:720px){.art-comment-name-fields{grid-template-columns:1fr}.art-comment-form{padding:12px}.art-comment-replies{margin-left:33px}}';d.head.appendChild(commentStyle)}
    if(!d.__artDetailBound){d.__artDetailBound=true;d.addEventListener('click',function(event){var commentButton=event.target.closest('.comment-button'),inspectButton=event.target.closest('.inspect-btn');if(!commentButton&&!inspectButton)return;event.preventDefault();event.stopImmediatePropagation();var button=commentButton||inspectButton,card=button.closest('.card');var code=card&&(card.dataset.productCode||(card.querySelector('.chip')||{}).textContent||'').trim();var product=(window.__adminProducts||[]).find(function(item){return item.code===code});if(product)openArtworkDetail(d,product,card,window.__adminSettings||{},!!commentButton)},true)}
    var floralStyle=d.getElementById('gallery-floral-accent-style');if(!floralStyle){floralStyle=d.createElement('style');floralStyle.id='gallery-floral-accent-style';floralStyle.textContent=`#yeni-gelenler,#sanatcinin-secimi,#koleksiyonlar{position:relative;background-image:radial-gradient(ellipse at 8% 18%,rgba(247,220,231,.28),transparent 31%),radial-gradient(ellipse at 92% 82%,rgba(221,234,224,.32),transparent 30%)}#yeni-gelenler:before,#sanatcinin-secimi:after,#koleksiyonlar:before{content:'✿';position:absolute;z-index:0;pointer-events:none;opacity:.32;font:clamp(25px,3.3vw,43px)/1 Georgia,serif;color:#eaa0b8;text-shadow:0 7px 18px rgba(208,137,163,.16);animation:ambient-bloom-float 8s ease-in-out infinite alternate}#yeni-gelenler:before{left:clamp(12px,6vw,82px);top:74px}#sanatcinin-secimi:after{right:clamp(12px,6vw,82px);top:90px;color:#d6a94f;animation-delay:1.3s}#koleksiyonlar:before{right:clamp(14px,5vw,72px);top:56px;color:#b598cd;animation-delay:2.1s}@keyframes ambient-bloom-float{from{transform:translate3d(0,0,0) rotate(-9deg)}to{transform:translate3d(0,-10px,0) rotate(9deg)}}@media(max-width:700px){#yeni-gelenler:before,#sanatcinin-secimi:after,#koleksiyonlar:before{font-size:27px;opacity:.25}#yeni-gelenler:before{top:48px;left:10px}#sanatcinin-secimi:after{top:52px;right:10px}#koleksiyonlar:before{top:26px;right:12px}}@media(prefers-reduced-motion:reduce){#yeni-gelenler:before,#sanatcinin-secimi:after,#koleksiyonlar:before{animation:none}}`;d.head.appendChild(floralStyle)}
    if(!d.__galleryCardTemplatesReady){var sampleCards=Array.from(d.querySelectorAll('.card')),sampleTemplates=new Map();sampleCards.forEach(function(card){var chip=card.querySelector('.chip'),code=chip&&chip.textContent.trim();if(code&&!sampleTemplates.has(code))sampleTemplates.set(code,card)});d.__galleryCardTemplates=sampleTemplates;d.__galleryBaseTemplate=sampleCards[0]||null;sampleCards.forEach(function(card){card.remove()});d.__galleryCardTemplatesReady=true;var featuredShell=d.querySelector('.fw');if(featuredShell)featuredShell.hidden=true;var arrivalsShell=d.querySelector('#yeni-gelenler .editorial-grid');if(arrivalsShell&&arrivalsShell.parentElement)arrivalsShell.parentElement.hidden=true;var curatedShell=d.querySelector('#sanatcinin-secimi .curated-grid');if(curatedShell&&curatedShell.parentElement)curatedShell.parentElement.hidden=true;var soldShell=d.querySelector('#sold-works-grid');if(soldShell&&soldShell.parentElement)soldShell.parentElement.hidden=true}
    var sold=d.querySelector('#sold-works-grid');
    if(!d.__galleryViewportWidthReady){var syncGalleryViewportWidth=function(){d.documentElement.style.setProperty('--gallery-viewport-width',(d.documentElement.clientWidth||d.defaultView.innerWidth)+'px')};syncGalleryViewportWidth();d.defaultView.addEventListener('resize',syncGalleryViewportWidth,{passive:true});d.__galleryViewportWidthReady=true}
    var carouselStyle=d.getElementById('responsive-featured-carousel');if(!carouselStyle){carouselStyle=d.createElement('style');carouselStyle.id='responsive-featured-carousel';carouselStyle.textContent='@media(max-width:700px){.fw,.fw .ftt{-webkit-mask:none!important;mask:none!important;-webkit-mask-image:none!important;mask-image:none!important;opacity:1!important;filter:none!important}.fw:before,.fw:after,.fw .ftt:before,.fw .ftt:after{content:none!important;display:none!important;background:none!important;opacity:0!important}.fw .ftt>.card{opacity:1!important;filter:none!important;visibility:visible!important}}@media(max-width:700px){#eserler{padding-left:20px!important;padding-right:20px!important}.fw{box-sizing:border-box!important;width:auto!important;max-width:none!important;margin-left:-20px!important;margin-right:-20px!important;padding-left:12px!important;padding-right:12px!important;overflow-x:auto!important;scroll-snap-type:none!important}.fw .ftt{animation:none!important;transform:none!important}.fw .ftt>.card{scroll-snap-align:none!important}#eserler .fw{padding-left:12px!important;padding-right:12px!important}#eserler .fw .ftt>.card{flex:0 0 calc((var(--gallery-viewport-width,100vw) - 44px)/2)!important;width:calc((var(--gallery-viewport-width,100vw) - 44px)/2)!important;max-width:calc((var(--gallery-viewport-width,100vw) - 44px)/2)!important;min-width:0!important}#yeni-gelenler,#sanatcinin-secimi,#koleksiyonlar{padding-left:16px!important;padding-right:16px!important}#sold-works-grid{width:calc(var(--gallery-viewport-width,100vw) - 32px)!important;margin-left:auto!important;margin-right:auto!important}#admin-live-catalog{padding-left:16px!important;padding-right:16px!important}.editorial-section .editorial-grid,.editorial-section .curated-grid,#yeni-gelenler .editorial-grid,#sanatcinin-secimi .curated-grid,#koleksiyonlar .collection-art-grid,#sold-works-grid,#admin-live-catalog .admin-catalog-grid{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;grid-auto-rows:1fr!important;justify-content:stretch!important;align-items:stretch!important;gap:12px!important;width:100%!important;max-width:none!important;margin:14px 0 0!important;padding:0!important}.editorial-section .editorial-grid,#yeni-gelenler .editorial-grid,#sanatcinin-secimi .curated-grid,#koleksiyonlar .collection-art-grid,#sold-works-grid,#admin-live-catalog .admin-catalog-grid{grid-template-columns:repeat(2,calc((var(--gallery-viewport-width,100vw) - 44px)/2))!important;grid-auto-rows:1fr!important;gap:12px!important}.editorial-section .editorial-grid>.card,.editorial-section .curated-grid>.card,#yeni-gelenler .editorial-grid>.card,#sanatcinin-secimi .curated-grid>.card,#koleksiyonlar .collection-art-grid>.card,#sold-works-grid>.card,#admin-live-catalog .admin-catalog-grid>.card{display:flex!important;flex:none!important;flex-direction:column!important;width:100%!important;max-width:none!important;min-width:0!important;height:100%!important;justify-self:stretch!important;align-self:stretch!important}.editorial-section .editorial-grid>.card>.ct,.editorial-section .curated-grid>.card>.ct,#yeni-gelenler .editorial-grid>.card>.ct,#sanatcinin-secimi .curated-grid>.card>.ct,#koleksiyonlar .collection-art-grid>.card>.ct,#sold-works-grid>.card>.ct,#admin-live-catalog .admin-catalog-grid>.card>.ct{display:flex!important;flex:1 1 auto!important;flex-direction:column!important}.editorial-section .card .card-actions,#yeni-gelenler .card .card-actions,#sanatcinin-secimi .card .card-actions,#koleksiyonlar .collection-art-grid .card .card-actions,#sold-works-grid .card .card-actions,#admin-live-catalog .card .card-actions{margin-top:auto!important}.fw .ftt>.card{flex:0 0 calc((100vw - 44px)/2)!important;width:calc((100vw - 44px)/2)!important;min-width:0!important;max-width:calc((100vw - 44px)/2)!important}.fw .art.has-art-backdrop,.editorial-section .art.has-art-backdrop,#yeni-gelenler .art.has-art-backdrop,#sanatcinin-secimi .art.has-art-backdrop,#koleksiyonlar .collection-art-grid .art.has-art-backdrop,#sold-works-grid .art.has-art-backdrop,#admin-live-catalog .art.has-art-backdrop{position:relative!important;isolation:isolate!important;overflow:hidden!important;background-color:#eeeae6!important}.fw .art.has-art-backdrop:before,.editorial-section .art.has-art-backdrop:before,#yeni-gelenler .art.has-art-backdrop:before,#sanatcinin-secimi .art.has-art-backdrop:before,#koleksiyonlar .collection-art-grid .art.has-art-backdrop:before,#sold-works-grid .art.has-art-backdrop:before,#admin-live-catalog .art.has-art-backdrop:before{content:""!important;display:block!important;position:absolute!important;inset:-12px!important;z-index:0!important;background-image:var(--art-backdrop)!important;background-size:cover!important;background-position:center!important;filter:blur(15px)!important;opacity:.72!important;transform:scale(1.08)!important;border-radius:inherit!important;pointer-events:none!important}.fw .art.has-art-backdrop>img,.editorial-section .art.has-art-backdrop>img,#yeni-gelenler .art.has-art-backdrop>img,#sanatcinin-secimi .art.has-art-backdrop>img,#koleksiyonlar .collection-art-grid .art.has-art-backdrop>img,#sold-works-grid .art.has-art-backdrop>img,#admin-live-catalog .art.has-art-backdrop>img{position:absolute!important;inset:0!important;z-index:1!important;width:100%!important;height:100%!important;object-fit:contain!important;background:transparent!important}.fw .ftt>.card,.editorial-section .editorial-grid>.card,#yeni-gelenler .editorial-grid>.card,#sanatcinin-secimi .curated-grid>.card,#koleksiyonlar .collection-art-grid>.card,#sold-works-grid>.card,#admin-live-catalog .admin-catalog-grid>.card{padding:7px!important;border-radius:15px!important}.fw .ftt>.card>.art,.editorial-section .editorial-grid>.card>.art,#yeni-gelenler .editorial-grid>.card>.art,#sanatcinin-secimi .curated-grid>.card>.art,#koleksiyonlar .collection-art-grid>.card>.art,#sold-works-grid>.card>.art,#admin-live-catalog .admin-catalog-grid>.card>.art{aspect-ratio:3/4!important;border-radius:11px!important}.fw .ftt>.card>.ct,.editorial-section .editorial-grid>.card>.ct,#yeni-gelenler .editorial-grid>.card>.ct,#sanatcinin-secimi .curated-grid>.card>.ct,#koleksiyonlar .collection-art-grid>.card>.ct,#sold-works-grid>.card>.ct,#admin-live-catalog .admin-catalog-grid>.card>.ct{padding:8px 3px 5px!important}.fw .ftt>.card>.ct>b,.editorial-section .editorial-grid>.card>.ct>b,#yeni-gelenler .editorial-grid>.card>.ct>b,#sanatcinin-secimi .curated-grid>.card>.ct>b,#koleksiyonlar .collection-art-grid>.card>.ct>b,#sold-works-grid>.card>.ct>b,#admin-live-catalog .admin-catalog-grid>.card>.ct>b{font-size:14px!important;line-height:17.5px!important}.fw .ftt>.card>.ct>span:not(.pr):not(.catalog-description),.editorial-section .editorial-grid>.card>.ct>span:not(.pr):not(.catalog-description),#yeni-gelenler .editorial-grid>.card>.ct>span:not(.pr):not(.catalog-description),#sanatcinin-secimi .curated-grid>.card>.ct>span:not(.pr):not(.catalog-description),#koleksiyonlar .collection-art-grid>.card>.ct>span:not(.pr):not(.catalog-description),#sold-works-grid>.card>.ct>span:not(.pr):not(.catalog-description),#admin-live-catalog .admin-catalog-grid>.card>.ct>span:not(.pr):not(.catalog-description){font-size:11px!important;line-height:15px!important}.fw .ftt>.card>.ct>.pr,.editorial-section .editorial-grid>.card>.ct>.pr,#yeni-gelenler .editorial-grid>.card>.ct>.pr,#sanatcinin-secimi .curated-grid>.card>.ct>.pr,#koleksiyonlar .collection-art-grid>.card>.ct>.pr,#sold-works-grid>.card>.ct>.pr,#admin-live-catalog .admin-catalog-grid>.card>.ct>.pr{font-size:14px!important;line-height:16px!important;margin:4px 0 7px!important}.fw .ftt>.card>.ct>.catalog-description,.editorial-section .editorial-grid>.card>.ct>.catalog-description,#yeni-gelenler .editorial-grid>.card>.ct>.catalog-description,#sanatcinin-secimi .curated-grid>.card>.ct>.catalog-description,#koleksiyonlar .collection-art-grid>.card>.ct>.catalog-description,#sold-works-grid>.card>.ct>.catalog-description,#admin-live-catalog .admin-catalog-grid>.card>.ct>.catalog-description{font-size:11px!important;line-height:15.95px!important;margin:8px 0 12px!important}.fw .ftt>.card .card-actions .btn,.editorial-section .editorial-grid>.card .card-actions .btn,#yeni-gelenler .editorial-grid>.card .card-actions .btn,#sanatcinin-secimi .curated-grid>.card .card-actions .btn,#koleksiyonlar .collection-art-grid>.card .card-actions .btn,#sold-works-grid>.card .card-actions .btn,#admin-live-catalog .admin-catalog-grid>.card .card-actions .btn{height:34px!important;min-height:34px!important;padding:7px 4px!important;font-size:11px!important;line-height:normal!important}}.fw.is-static .ftt[data-loop-copies="1"]{animation:none!important;transform:none!important;width:100%!important;justify-content:center!important;flex-wrap:wrap!important}@keyframes admin-featured-drift{to{transform:translateX(var(--featured-distance,0px))}}.fw.is-static .prev-default,.fw.is-static .next-default{display:none!important}.fw.is-manual .ftt{animation:none!important;transition:transform .65s ease!important}.all-works-section{max-width:1160px;margin:48px auto 60px;padding:30px 24px;background:#fffdf9;border:1px solid #efe4dd;border-radius:22px;box-shadow:0 12px 35px #5441370b}.all-works-filter{display:flex;align-items:center;justify-content:center;flex-wrap:wrap;gap:10px;margin:0 auto 18px}.all-works-filter label{font-size:13px;color:#665c61}.all-works-filter select{min-width:220px;border:1px solid #e0d6d1;border-radius:999px;padding:10px 16px;background:#fff;color:#4b514e}.category-manager{border:1px solid #e8ddd7;border-radius:14px;padding:16px;margin:6px 0 18px}.category-manager legend,.size-choice legend,.category-checks legend{padding:0 8px;color:#4b514e;font-weight:700}.category-setting-row{display:flex;gap:9px;margin:8px 0}.category-setting-row input{flex:1;min-width:0}.size-choice{display:flex;align-items:end;gap:10px;border:1px solid #e8ddd7;border-radius:12px;padding:14px}.size-choice label{flex:1;display:grid;gap:6px}.size-choice input,.size-choice select{border:1px solid #e0d6d1;background:#fffdfb;border-radius:10px;padding:10px;width:100%}.size-x{padding-bottom:8px}.category-checks{display:flex;gap:16px;flex-wrap:wrap;border:1px solid #e8ddd7;border-radius:12px;padding:14px}.category-checks label{display:inline-flex;gap:7px;align-items:center}.code-input-row input{flex:1;min-width:0}.copy-code{border:0;border-radius:14px;background:#f6edf1;color:#704c67;font-size:11px;padding:5px 8px;cursor:pointer}.copy-code:hover{background:#ead9e2}@media(max-width:650px){.size-choice{flex-wrap:wrap}.all-works-section{margin:28px 12px;padding:20px 12px}}';d.head.appendChild(carouselStyle)}
    var filterMenu=Array.from(d.querySelectorAll('details')).find(function(x){return (x.querySelector('summary')||{}).textContent.trim().startsWith('Kategori')}),oldControls=filterMenu&&filterMenu.parentElement&&filterMenu.parentElement.parentElement;if(oldControls){oldControls.classList.add('admin-filter-menu');var menus=oldControls.querySelectorAll('details');menus.forEach(function(menu,index){var label=index===0?'Kategori':index===1?'Fiyat':'Sırala',summary=menu.querySelector('summary'),list=menu.querySelector('div');if(summary)summary.dataset.menuLabel=label;if(list)list.dataset.menu=label.toLowerCase()})}
    var section=d.createElement('section');section.id='admin-live-catalog';section.className='all-works-section';section.hidden=false;section.style.display='block';section.innerHTML='<header class="section-heading"><span class="eyebrow">ATÖLYEDEN TÜM ÇALIŞMALAR</span><h2>Tüm Eserler</h2><p>Atölyedeki eserleri kategoriye göre keşfedin.</p></header><div class="all-works-filter"><label for="all-works-category">Kategori</label><select id="all-works-category"><option value="">Tüm kategoriler</option></select></div><div class="admin-catalog-grid"></div>';var footerAnchor=d.querySelector('.foot')||d.querySelector('#hakkimda')||d.querySelector('.soc');if(footerAnchor)footerAnchor.insertAdjacentElement('beforebegin',section);else{var contentAnchor=d.querySelector('#sanatcinin-secimi')||d.querySelector('#koleksiyonlar')||d.querySelector('#yeni-gelenler')||d.querySelector('#eserler')||d.body;contentAnchor.insertAdjacentElement('afterend',section)}var allFilter=section.querySelector('.all-works-filter');if(oldControls)oldControls.remove()
    if(!d.__galleryLikesBound){d.__galleryLikesBound=true;d.addEventListener('click',function(e){var b=e.target.closest('.like-button');if(!b||b.disabled)return;e.preventDefault();var code=b.dataset.likeCode,liked=b.dataset.liked!=='1';b.disabled=true;fetch('/api/likes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:code,visitor:likeVisitor,liked:liked})}).then(function(r){if(!r.ok)throw Error('like');return r.json()}).then(function(result){setLikeState(d,result.code,result)}).catch(function(){b.disabled=false}).finally(function(){b.disabled=false})},true);fetch('/api/likes?visitor='+encodeURIComponent(likeVisitor),{cache:'no-store'}).then(function(r){if(!r.ok)throw Error('likes');return r.json()}).then(function(data){Object.keys(data.likes||{}).forEach(function(code){setLikeState(d,code,data.likes[code])})}).catch(function(){})}
    if(!d.__galleryCommentCountsLoaded){d.__galleryCommentCountsLoaded=true;fetch('/api/comments?counts=1',{cache:'no-store'}).then(function(r){if(!r.ok)throw Error('comments');return r.json()}).then(function(data){Object.keys(data.counts||{}).forEach(function(code){setCommentCount(d,code,data.counts[code])})}).catch(function(){})}
    d.addEventListener('change',function(e){if(e.target&&e.target.id==='all-works-category'){filter.category=e.target.value;renderCatalog(d,window.__adminProducts||[],window.__adminTemplates||new Map())}},true);d.addEventListener('click',function(e){var option=e.target.closest('.admin-filter-menu [data-filter-value]');if(option){e.preventDefault();var menu=option.closest('details'),label=menu&&menu.querySelector('summary');if(!label)return;var type=label.dataset.menuLabel;if(type==='Kategori')filter.category=option.dataset.filterValue;else if(type==='Fiyat')filter.price=option.dataset.filterValue;else filter.sort=option.dataset.filterValue;label.firstChild.nodeValue=option.textContent.trim()+' ';menu.open=false;renderCatalog(d,window.__adminProducts||[],window.__adminTemplates||new Map());return}
    var arrow=e.target.closest('[data-featured-step]');if(arrow){e.preventDefault();e.stopImmediatePropagation();var track=d.querySelector('.fw .ftt'),cards=track&&track.querySelectorAll('.card');if(track&&cards&&cards.length){var copies=Math.max(1,Number(track.dataset.loopCopies)||1),count=Math.max(1,Math.floor(cards.length/copies));window.__adminSlide=((window.__adminSlide||0)+(Number(arrow.dataset.featuredStep)>0?1:-1)+count)%count;var root=track.closest('.fw');if(root)root.classList.add('is-manual');track.style.setProperty('animation','none','important');track.style.transition='transform .65s ease';track.style.transform='translateX(-'+(window.__adminSlide*(cards[0].getBoundingClientRect().width+24))+'px)';if(root.__featuredAutoResume)clearTimeout(root.__featuredAutoResume);root.__featuredAutoResume=setTimeout(function(){root.classList.remove('is-manual');track.style.transform='';var vp=track.parentElement;track.style.setProperty('--featured-distance','-'+Math.max(0,track.scrollWidth-(vp?vp.clientWidth:window.innerWidth))+'px');track.style.setProperty('animation','admin-featured-drift 48s ease-in-out infinite alternate','important')},7000)}}var tile=e.target.closest('.collection-tile[data-category]');if(tile){filter.category=tile.dataset.category;renderCatalog(d,window.__adminProducts||[],window.__adminTemplates||new Map());d.querySelector('#admin-live-catalog').scrollIntoView({behavior:'smooth',block:'start'})}},true);
    }
    function cardTemplate(d,p){var all=Array.from(d.querySelectorAll('.card')),found=all.find(function(x){var chip=x.querySelector('.chip');return chip&&chip.textContent.trim()===p.code});return found||d.__galleryCardTemplates&&d.__galleryCardTemplates.get(p.code)||d.__galleryBaseTemplate||all[0]}
    function paint(d,card,p,cfg){card.hidden=false;card.style.flex='0 0 240px';card.style.display='flex';card.style.flexDirection='column';card.dataset.productCode=p.code;var chip=card.querySelector('.chip');if(chip)chip.textContent=p.code;var title=card.querySelector('.ct .sf');if(title)title.textContent=p.title;var ct=card.querySelector('.ct');if(ct){ct.style.display='flex';ct.style.flexDirection='column';ct.style.flex='1 1 auto';var size=ct.querySelector('span:not(.pr)');if(size)size.textContent=p.size+(p.category?' · '+p.category:'');var price=ct.querySelector('.pr');if(price){price.replaceChildren();if(p.sale_price&&Number(p.sale_price)<Number(p.price)){var old=d.createElement('del');old.textContent=fmt(p.price);price.appendChild(old);price.appendChild(d.createTextNode(' '))}var current=d.createElement('b');current.textContent=fmt(p.sale_price&&Number(p.sale_price)<Number(p.price)?p.sale_price:p.price);price.appendChild(current)}var desc=ct.querySelector('.catalog-description');if(!desc){desc=d.createElement('span');desc.className='catalog-description';desc.style.cssText='display:block;margin:8px auto 12px;max-width:96%;color:#827783;font-size:11px;line-height:1.45;text-align:center;min-height:1.45em';var actions=ct.querySelector('.card-actions');ct.insertBefore(desc,actions||null)}desc.textContent=p.description||'';var actions=ct.querySelector('.card-actions');if(actions){actions.replaceChildren();actions.style.marginTop='auto';if(p.sold){var sold=d.createElement('span');sold.className='btn g sold-tag';sold.textContent='Satıldı';actions.appendChild(sold)}else{var buy=d.createElement('a');buy.className='btn g';buy.href=p.whatsapp_url||cfg.whatsapp_url||'#iletisim';buy.textContent='Satın Al';if(buy.href.indexOf('http')===0){buy.target='_blank';buy.rel='noopener'}actions.appendChild(buy)}var inspect=d.createElement('button');inspect.type='button';inspect.className='btn inspect-btn';inspect.textContent='İncele';actions.appendChild(inspect)}}var art=card.querySelector('.art');if(art){if(p.image){var img=art.querySelector('img');if(!img){art.replaceChildren();img=d.createElement('img');img.style.cssText='position:absolute;inset:0;width:100%;height:100%;object-fit:contain;background:#f2eee9;border-radius:inherit';art.appendChild(img)}img.src='/'+p.image;img.alt=p.title;art.classList.add('has-art-backdrop');art.style.setProperty('--art-backdrop','url("'+img.src.replace(/"/g,'%22')+'")')}else if(art.querySelector('img')){art.querySelector('img').remove();art.classList.remove('has-art-backdrop');art.style.removeProperty('--art-backdrop')}}ensureLikeRow(d,card,p.code);var likeRow=ct&&ct.querySelector('.like-row');if(likeRow)likeRow.style.marginTop='5px'}
    function fmt(n){return '₺'+Number(n||0).toLocaleString('tr-TR')}
    function renderCatalog(d,products,templates){var active=products.filter(function(p){return !p.archived&&p.published!==false}),grid=d.querySelector('#admin-live-catalog .admin-catalog-grid');if(!grid)return;var rows=active.filter(function(p){if(filter.category&&p.category!==filter.category)return false;var amount=Number(p.sale_price&&Number(p.sale_price)<Number(p.price)?p.sale_price:p.price);if(filter.price==='under')return amount<3000;if(filter.price==='middle')return amount>=3000&&amount<4000;if(filter.price==='high')return amount>=4000;return true});rows.sort(function(a,b){if(filter.sort==='low')return Number(a.sale_price||a.price)-Number(b.sale_price||b.price);if(filter.sort==='high')return Number(b.sale_price||b.price)-Number(a.sale_price||a.price);if(filter.sort==='name')return a.title.localeCompare(b.title,'tr');return b.id-a.id});var base=templates.values().next().value||d.querySelector('.card');if(base)grid.replaceChildren.apply(grid,rows.map(function(p){var clone=(templates.get(p.code)||base).cloneNode(true);paint(d,clone,p,window.__adminSettings||{});return clone}))}
    function sync(){try{var d=frame.contentDocument;if(!d||busy)return;install(d);busy=true;fetch('/api/products',{cache:'no-store'}).then(function(r){if(!r.ok)throw Error('catalog');return r.json()}).then(function(data){var products=data.products||[],cfg=data.settings||{},active=products.filter(function(p){return !p.archived&&!p.sold&&p.published!==false}),featured=Array.from(new Map(active.filter(function(p){return !!p.featured}).map(function(p){return[p.code,p]})).values()).sort(function(a,b){return b.id-a.id}),soldItems=products.filter(function(p){return !p.archived&&!!p.sold&&p.published!==false}).sort(function(a,b){return b.id-a.id}),templates=d.__galleryCardTemplates||new Map();if(!templates.size&&d.__galleryBaseTemplate)templates.set('default',d.__galleryBaseTemplate);window.__adminProducts=products;window.__adminTemplates=templates;window.__adminSettings=cfg;
    var ft=d.querySelector('.fw .ftt'),fallback=d.__galleryBaseTemplate||d.querySelector('.card');if(ft&&fallback){var viewport=ft.parentElement,cardWidth=Math.max(240,(templates.get(featured[0]&&featured[0].code)||fallback).getBoundingClientRect().width||260),gap=24,needsLoop=featured.length>0&&featured.length*(cardWidth+gap)-gap>(viewport?viewport.clientWidth:window.innerWidth),cycle=featured.slice();var featuredSignature=featured.map(function(p){return p.code}).join('|')+'|'+(needsLoop?'loop':'static');ft.dataset.loopCopies='1';var featuredRoot=ft.closest('.fw');if(featuredRoot){featuredRoot.classList.toggle('is-static',!needsLoop);featuredRoot.hidden=!featured.length;}if(ft.dataset.featuredSignature!==featuredSignature){ft.dataset.featuredSignature=featuredSignature;ft.replaceChildren.apply(ft,cycle.map(function(p){var card=(templates.get(p.code)||fallback).cloneNode(true);paint(d,card,p,cfg);return card}));ft.style.setProperty('--featured-distance','-'+Math.max(0,ft.scrollWidth-(viewport?viewport.clientWidth:window.innerWidth))+'px');ft.style.setProperty('animation',needsLoop&&window.innerWidth>640?'admin-featured-drift 48s ease-in-out infinite alternate':'none','important');ft.style.transform='';if(!featured.length)ft.innerHTML='<p style="padding:24px;color:#827783">Yönetim panelinden öne çıkarılan eserler burada görünür.</p>'}
    var arrivals=d.querySelector('#yeni-gelenler .editorial-grid');if(arrivals){var fresh=active.filter(function(p){return !!p.show_new}).sort(function(a,b){return b.id-a.id});arrivals.replaceChildren.apply(arrivals,fresh.map(function(p){var c=(templates.get(p.code)||fallback).cloneNode(true);paint(d,c,p,cfg);return c}));arrivals.parentElement.hidden=!fresh.length}
    var collectionTiles=d.querySelector('#koleksiyonlar .collection-grid'),collectionGrid=d.querySelector('#koleksiyonlar .collection-art-grid');if(collectionTiles&&!collectionGrid){collectionGrid=d.createElement('div');collectionGrid.className='editorial-grid collection-art-grid';collectionGrid.setAttribute('aria-label','Koleksiyon eserleri');collectionTiles.insertAdjacentElement('afterend',collectionGrid)}var collectionWorks=active.filter(function(p){return !!p.show_collections}).sort(function(a,b){return b.id-a.id});if(collectionGrid){collectionGrid.replaceChildren.apply(collectionGrid,collectionWorks.map(function(p){var c=(templates.get(p.code)||fallback).cloneNode(true);paint(d,c,p,cfg);return c}));collectionGrid.hidden=!collectionWorks.length}
    var curated=d.querySelector('#sanatcinin-secimi .curated-grid');if(curated){var picks=active.filter(function(p){return !!p.show_curated}).sort(function(a,b){return b.id-a.id});curated.replaceChildren.apply(curated,picks.map(function(p){var c=(templates.get(p.code)||fallback).cloneNode(true);paint(d,c,p,cfg);return c}));curated.parentElement.hidden=!picks.length}
    var soldGrid=d.querySelector('#sold-works-grid');if(soldGrid){soldGrid.classList.add('sold-works-grid');soldGrid.replaceChildren.apply(soldGrid,soldItems.map(function(p){var c=(templates.get(p.code)||fallback).cloneNode(true);paint(d,c,p,cfg);return c}));soldGrid.parentElement.hidden=!soldItems.length}
    var cats=Array.from(new Set((cfg.categories||'').split(',').map(function(x){return x.trim()}).filter(Boolean).concat(products.map(function(p){return(p.category||'').trim()}).filter(Boolean))));var allCategory=d.querySelector('#all-works-category');if(allCategory){var previous=filter.category;allCategory.replaceChildren.apply(allCategory,[new Option('Tüm kategoriler','')].concat(cats.map(function(x){return new Option(x,x)})));allCategory.value=cats.indexOf(previous)>=0?previous:'';filter.category=allCategory.value}var categoryMenu=Array.from(d.querySelectorAll('.admin-filter-menu details')).find(function(x){return x.querySelector('summary')&&x.querySelector('summary').dataset.menuLabel==='Kategori'});if(categoryMenu){var list=categoryMenu.querySelector('[data-menu]');list.replaceChildren();[['','Tümü']].concat(cats.map(function(x){return[x,x]})).forEach(function(entry){var b=d.createElement('button');b.type='button';b.dataset.filterValue=entry[0];b.textContent=entry[1];list.appendChild(b)})}Array.from(d.querySelectorAll('#koleksiyonlar .collection-tile')).forEach(function(tile,i){var category=cats[i];if(!category){tile.hidden=true;return}tile.hidden=false;tile.dataset.category=category;tile.href='#admin-live-catalog';var label=tile.querySelector('span'),heading=tile.querySelector('h3'),copy=tile.querySelector('p');if(label)label.textContent=('0'+(i+1)).slice(-2)+' · '+category.toLocaleUpperCase('tr');if(heading)heading.textContent=category;if(copy)copy.textContent='Bu kategorideki '+active.filter(function(p){return p.category===category}).length+' eseri koleksiyonda görüntüleyin.'});
    var menus=Array.from(d.querySelectorAll('.admin-filter-menu details'));menus.forEach(function(menu){var s=menu.querySelector('summary'),list=menu.querySelector('[data-menu]');if(!s||!list||s.dataset.menuLabel==='Kategori')return;var opts=s.dataset.menuLabel==='Fiyat'?[['','Tüm fiyatlar'],['under','₺3.000 altı'],['middle','₺3.000–₺4.000'],['high','₺4.000 üzeri']]:[['new','En yeni'],['low','Fiyat: düşükten yükseğe'],['high','Fiyat: yüksekten düşüğe'],['name','Ada göre']];list.replaceChildren.apply(list,opts.map(function(entry){var b=d.createElement('button');b.type='button';b.dataset.filterValue=entry[0];b.textContent=entry[1];return b}))});
    var brand=d.querySelector('.brand small');if(brand)brand.textContent='EL YAPIMI TABLOLAR · '+(cfg.site_name||'Perihan Baktaş');var name=d.querySelector('#hakkimda .sc[style*="font-size:40px"]');if(name)name.textContent=cfg.site_name||'Perihan Baktaş';d.title=(cfg.site_name||'Perihan Baktaş')+' | Sanat Atölyesi';[['Instagram','instagram_url'],['TikTok','tiktok_url'],['Telegram','telegram_url'],['WhatsApp','whatsapp_url']].forEach(function(pair){var url=cfg[pair[1]];if(!url)return;Array.from(d.querySelectorAll('a')).filter(function(a){return a.textContent.trim()===pair[0]}).forEach(function(a){a.href=url;a.target='_blank';a.rel='noopener'})});renderCatalog(d,products,templates);d.documentElement.style.setProperty('--gallery-viewport-width',(d.documentElement.clientWidth||d.defaultView.innerWidth)+'px');
    var sig=JSON.stringify([products.map(function(p){return[p.id,p.code,p.title,p.size,p.price,p.sale_price,p.category,p.description,p.image,p.whatsapp_url,p.featured,p.sold,p.archived,p.show_new,p.show_collections,p.show_curated]}),cfg]);if(sig!==lastSignature){lastSignature=sig;window.__adminSlide=0;if(ft){ft.style.transform='';ft.style.animation='';}}}}).catch(function(){}).finally(function(){busy=false})}catch(e){busy=false}}
    frame.addEventListener('load',function(){revealPage();sync();setInterval(sync,2500);try{frame.contentWindow.addEventListener('resize',function(){lastSignature='';sync()})}catch(e){}});if(frame.contentDocument&&frame.contentDocument.readyState==='complete'){revealPage();sync();setInterval(sync,2500)}})();
    </script></body></html>"""


def input_field(label, name, value="", kind="text", required=False, extra=""):
    req = " required" if required else ""
    if kind == "textarea":
        control = f"<textarea name='{name}' {req} {extra}>{esc(value)}</textarea>"
    else:
        control = f"<input name='{name}' type='{kind}' value='{esc(value)}' {req} {extra}>"
    return f"<label>{label}{control}</label>"


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
        return bool(self.get_admin() and hmac.compare_digest(str(fields.get("csrf", "")), settings().get("csrf_token", "")))

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path == "/legacy-homepage.html":
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
                for item in items:
                    item["published"] = not item.get("publish_at") or item["publish_at"] <= datetime.now().strftime("%Y-%m-%dT%H:%M")
            cfg = settings()
            public_settings = {k: cfg.get(k, "") for k in ("site_name", "whatsapp_url", "instagram_url", "tiktok_url", "telegram_url", "categories")}
            payload = json.dumps({"products": items, "settings": public_settings}, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if path == "/api/comments":
            code = query.get("code", [""])[0].strip()[:64]
            now = datetime.now().strftime("%Y-%m-%dT%H:%M")
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
            return self.send_html(render_legacy_home())
        if path == "/new-home":
            category = query.get("kategori", [""])[0]
            sort = query.get("sirala", [""])[0]
            with connect() as c:
                sql = "SELECT * FROM products WHERE archived=0 AND sold=0 AND (publish_at='' OR publish_at<=?)"
                args = [datetime.now().strftime("%Y-%m-%dT%H:%M")]
                if category:
                    sql += " AND category=?"; args.append(category)
                order = "created_at DESC"
                if sort == "fiyat-artan": order = "COALESCE(sale_price,price) ASC"
                elif sort == "fiyat-azalan": order = "COALESCE(sale_price,price) DESC"
                rows = c.execute(sql + " ORDER BY featured DESC," + order, args).fetchall()
                featured = c.execute("SELECT * FROM products WHERE archived=0 AND sold=0 AND featured=1 AND (publish_at='' OR publish_at<=?) ORDER BY id DESC LIMIT 8", (datetime.now().strftime("%Y-%m-%dT%H:%M"),)).fetchall()
                sold = c.execute("SELECT * FROM products WHERE archived=0 AND sold=1 AND (publish_at='' OR publish_at<=?) ORDER BY id DESC", (datetime.now().strftime("%Y-%m-%dT%H:%M"),)).fetchall()
            cats = [x.strip() for x in settings().get("categories", "").split(",") if x.strip()]
            select = "".join(f"<option {'selected' if category == x else ''} value='{esc(x)}'>{esc(x)}</option>" for x in cats)
            hero = "<section class='hero'><div class='hero-copy'><span class='eyebrow'>EL YAPIMI · ÖZGÜN ESERLER</span><h1>Sanatla Dolu<br><em>Huzurlu Bir Bahar</em></h1><p>İlkbaharın sakinliği, fırçanın dokunuşuyla duvarınıza gelsin. Her eser kendine özgü bir renk ve hikâye taşır.</p><a class='button' href='#eserler'>Eserleri Keşfet</a></div><div class='hero-art'><div class='hero-canvas'><span>✿</span><span>✿</span><span>✿</span><span>✿</span></div><small>Perihan Baktaş · Atölyeden</small></div></section>"
            content = hero
            if featured:
                content += f"<section class='section'><div class='section-heading'><span class='eyebrow'>ATÖLYEDEN SEÇKİ</span><h2>Öne Çıkan Eserler</h2><p>Sanatın en özel parçalarını keşfedin.</p></div><div class='carousel'><button class='carousel-arrow' type='button' data-carousel='prev' aria-label='Önceki eserler'>‹</button><div class='product-grid carousel-track'>{product_cards(featured)}</div><button class='carousel-arrow' type='button' data-carousel='next' aria-label='Sonraki eserler'>›</button></div></section>"
            content += f"<section class='section' id='eserler'><div class='section-heading'><span class='eyebrow'>ÖZGÜN ÇALIŞMALAR</span><h2>Eser Koleksiyonu</h2><p>Size yakın renkleri ve manzaraları seçin.</p></div><form class='filters' method='get'><label>Kategori<select name='kategori'><option value=''>Tüm kategoriler</option>{select}</select></label><label>Sırala<select name='sirala'><option value=''>Öne çıkanlar</option><option value='fiyat-artan' {'selected' if sort=='fiyat-artan' else ''}>Fiyat: düşükten yükseğe</option><option value='fiyat-azalan' {'selected' if sort=='fiyat-azalan' else ''}>Fiyat: yüksekten düşüğe</option></select></label><button class='button small'>Uygula</button></form><div class='product-grid'>{product_cards(rows)}</div></section>"
            if sold:
                content += f"<section class='section sold-section'><div class='section-heading'><span class='eyebrow'>YENİ SAHİPLERİNE ULAŞTILAR</span><h2>Satılan Eserler</h2><p>Sahiplerine ulaşmış güzel parçalar.</p></div><div class='product-grid'>{product_cards(sold)}</div></section>"
            content += "<section id='hakkimda' class='about'><span class='eyebrow'>ATÖLYEDEN BİR NOT</span><h2>Her Eserde Bir Bahar Hikâyesi</h2><p>Perihan Baktaş’ın el yapımı eserleri; çiçeklerin, doğanın ve mevsimlerin renklerinden ilham alır.</p></section>"
            return self.send_html(render("Ana Sayfa", content))
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
            listing = "".join(admin_product_row(p, csrf, likes.get(p["id"], 0)) for p in rows)
            archived_listing = "".join(admin_product_row(p, csrf, likes.get(p["id"], 0), archived=True) for p in archived_rows)
            if not listing:
                listing = "<tr><td colspan='9' class='empty'>Yayındaki eser yok.</td></tr>"
            if not archived_listing:
                archived_listing = "<tr><td colspan='9' class='empty'>Arşivde henüz eser yok.</td></tr>"
            copy_script = "<script>document.querySelectorAll('.copy-code').forEach(function(b){b.addEventListener('click',function(){navigator.clipboard.writeText(b.dataset.copy).then(function(){var old=b.textContent;b.textContent='Kopyalandı';setTimeout(function(){b.textContent=old},1200)})})})</script>"
            table_head = "<thead><tr><th>Kod</th><th>Eser</th><th>Ölçü</th><th>Kategori</th><th>Fiyat</th><th>Beğeni</th><th>Ana sayfa bölümleri</th><th>Durum / yayın tarihi</th><th>İşlem</th></tr></thead>"
            content = f"<section class='admin-top'><div><span class='eyebrow'>KATALOG</span><h1>Tablolar</h1><p>Fiyat, ölçü, kategori, açıklama ve öne çıkarma ayarları.</p></div>{admin_nav('products')}</section><div class='admin-actions' style='box-sizing:border-box;width:100%;max-width:1280px;margin:0 auto 15px;padding:0 24px;display:flex;justify-content:flex-start;align-items:center'><a class='button small' href='/atolye-yonetim-8f31/products/new'>+ Yeni Tablo Ekle</a></div><div class='table-wrap'><table>{table_head}<tbody>{listing}</tbody></table></div><h2>Arşiv</h2><div class='table-wrap'><table>{table_head}<tbody>{archived_listing}</tbody></table></div><p class='center'><a href='/arsiv'>Arşiv sayfasını görüntüle</a></p>{copy_script}"
            return self.send_html(render("Yönetim · Tablolar", content))
        if path == "/atolye-yonetim-8f31/products/new" or re.fullmatch(r"/atolye-yonetim-8f31/products/\d+", path):
            product = None
            if path != "/atolye-yonetim-8f31/products/new":
                with connect() as c: product = c.execute("SELECT * FROM products WHERE id=?", (int(path.rsplit('/',1)[-1]),)).fetchone()
                if not product: return self.send_error(404)
            val = lambda key, default="": product[key] if product else default
            size_match = re.match(r"\s*(\d+)\s*[x×]\s*(\d+)\s*(.*)", str(val("size", "")), re.I)
            width_val, height_val, unit_val = (size_match.group(1), size_match.group(2), size_match.group(3).strip() or "cm") if size_match else ("", "", "cm")
            cats = [x.strip() for x in settings().get("categories", "").split(",") if x.strip()]
            if product and product["category"] and product["category"] not in cats: cats.append(product["category"])
            if not product:
                with connect() as c:
                    while True:
                        code = "PB-" + str(secrets.randbelow(900) + 100)
                        if not c.execute("SELECT 1 FROM products WHERE code=?", (code,)).fetchone(): break
            else:
                code = product["code"]
            code_field = f"<label>Eser kodu<div class='code-input-row'><input name='code' value='{esc(code)}' required><button type='button' class='copy-code' data-copy='{esc(code)}'>Kopyala</button></div></label>"
            category_checks = "".join(f"<label><input type='checkbox' name='category_choice' value='{esc(x)}' {'checked' if product and product['category']==x else ''}>{esc(x)}</label>" for x in cats)
            featured = "checked" if product and product["featured"] else ""
            sold = "checked" if product and product["sold"] else ""
            show_new = "checked" if product and product["show_new"] else ""
            show_collections = "checked" if product and product["show_collections"] else ""
            show_curated = "checked" if product and product["show_curated"] else ""
            section_choices = f"<fieldset class='section-choice span-2'><legend>Ana sayfada hangi bölümlerde görünsün?</legend><p>En az bir bölüm seçin; aynı tabloyu birden fazla bölümde gösterebilirsiniz.</p><div class='section-checks'><label><input type='checkbox' name='show_new' value='1' {show_new}> Yeni Gelenler</label><label><input type='checkbox' name='show_collections' value='1' {show_collections}> Koleksiyonlar</label><label><input type='checkbox' name='show_curated' value='1' {show_curated}> Sanatçının Seçkisi</label></div></fieldset>"
            size_fields = f"<fieldset class='span-2 size-choice'><legend>Tablo ölçüsü</legend><label>Genişlik<input type='number' name='width' min='1' max='500' value='{esc(width_val)}' required></label><span class='size-x'>×</span><label>Yükseklik<input type='number' name='height' min='1' max='500' value='{esc(height_val)}' required></label><label>Birim<select name='size_unit'><option {'selected' if unit_val=='cm' else ''}>cm</option><option {'selected' if unit_val=='mm' else ''}>mm</option><option {'selected' if unit_val=='inç' else ''}>inç</option></select></label></fieldset>"
            category_choices = f"<details class='span-2 category-picker'><summary><span>Kategori <small>(isteğe bağlı)</small></span><span class='category-chevron' aria-hidden='true'>⌄</span></summary><div class='category-options'>{category_checks or '<small>Henüz kategori eklenmemiş.</small>'}</div></details>"
            publish_at = val("publish_at", "")
            if publish_at and len(publish_at) == 10: publish_at += "T00:00"
            content = f"<section class='admin-top'><div><span class='eyebrow'>KATALOG</span><h1>{'Tabloyu Düzenle' if product else 'Yeni Tablo Ekle'}</h1></div>{admin_nav('products')}</section><section class='form-card admin-form'><form method='post' enctype='multipart/form-data' action='/atolye-yonetim-8f31/products/save'><input type='hidden' name='csrf' value='{csrf}'><input type='hidden' name='id' value='{esc(val('id'))}'><div class='form-grid'>{code_field}{input_field('Eser adı', 'title', val('title'), required=True)}{size_fields}{category_choices}{input_field('Liste fiyatı (₺)', 'price', val('price'), 'number', True, "min='0'")}{input_field('İndirimli fiyat (₺, isteğe bağlı)', 'sale_price', val('sale_price') or '', 'number', False, "min='0'")}{input_field('Yayın zamanı (boş bırakılırsa hemen yayınlanır)', 'publish_at', publish_at, 'datetime-local')}{input_field('WhatsApp bağlantısı (isteğe bağlı)', 'whatsapp_url', val('whatsapp_url'), 'url', False, "placeholder='https://wa.me/...' class='span-2'")}{input_field('Açıklama', 'description', val('description'), 'textarea', False, "rows='4' class='span-2'")}{input_field('İncele başlığı (isteğe bağlı)', 'inspect_title', val('inspect_title'), 'text', False, "maxlength='160' class='span-2'")}{input_field('Makale / eser hikâyesi (isteğe bağlı)', 'article', val('article'), 'textarea', False, "rows='8' maxlength='12000' class='span-2'")}<label class='span-2'>Eser görseli<input type='file' name='image' accept='.jpg,.jpeg,.jfif,.png,.webp'><small>JPG, PNG veya WEBP · en fazla 8 MB{(' · Mevcut görsel: '+esc(val('image'))) if product and val('image') else ''}</small></label></div><div class='check-row'><label><input type='checkbox' name='featured' value='1' {featured}> Öne Çıkan Eserler şeridinde göster</label><label><input type='checkbox' name='sold' value='1' {sold}> Satıldı olarak göster</label></div>{section_choices}<button class='button'>Kaydet</button> <a class='button ghost' href='/atolye-yonetim-8f31/products'>İptal</a></form></section><script src='/static/admin-product-form.js' defer></script>"
            return self.send_html(render("Yönetim · Tablo", content))
        if path == "/atolye-yonetim-8f31/settings":
            cfg = settings()
            category_rows = "".join(f"<div class='category-setting-row'><input class='category-setting-input' value='{esc(x)}' maxlength='80' aria-label='Kategori adı'><button type='button' class='button ghost category-remove'>Sil</button></div>" for x in cfg.get("categories", "").split(",") if x.strip())
            content = f"<section class='admin-top'><div><span class='eyebrow'>SİTE AYARLARI</span><h1>Bağlantılar ve Kategoriler</h1><p>WhatsApp ve sosyal medya bağlantılarını, kategori listesini yönetin.</p></div>{admin_nav('settings')}</section><section class='narrow form-card'><form id='settings-form' method='post' action='/atolye-yonetim-8f31/settings'><input type='hidden' name='csrf' value='{csrf}'>{input_field('Atölye adı', 'site_name', cfg.get('site_name'), required=True)}{input_field('WhatsApp bağlantısı', 'whatsapp_url', cfg.get('whatsapp_url'), 'url', False, "placeholder='https://wa.me/905...' ")}{input_field('Instagram URL', 'instagram_url', cfg.get('instagram_url'), 'url')}{input_field('TikTok URL', 'tiktok_url', cfg.get('tiktok_url'), 'url')}{input_field('Telegram URL', 'telegram_url', cfg.get('telegram_url'), 'url')}<fieldset class='category-manager'><legend>Kategoriler</legend><div id='category-setting-list'>{category_rows}</div><button type='button' class='button ghost' id='category-add'>+ Kategori Ekle</button><input type='hidden' name='categories' id='categories-value'></fieldset><button class='button wide'>Ayarları Kaydet</button></form></section><script src='/static/category-manager.js' defer></script>"
            return self.send_html(render("Yönetim · Ayarlar", content))
        return self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path
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
                now = datetime.now().strftime("%Y-%m-%dT%H:%M")
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
                        with connect() as c: c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('csrf_token',?)", (csrf,))
                        payload = base64.urlsafe_b64encode(json.dumps({"id":1,"csrf":csrf,"exp":time.time()+86400*7}).encode()).decode().rstrip("=")
                        sig = hmac.new(settings()["session_secret"].encode(), payload.encode(), hashlib.sha256).hexdigest()
                        return self.redirect("/atolye-yonetim-8f31/products", [("Set-Cookie", f"gallery_admin={payload}.{sig}; HttpOnly; SameSite=Lax; Path=/; Max-Age=604800")])
                except Exception: pass
            return self.send_html(render("Giriş Hatası", "<section class='narrow form-card'><h1>Parola hatalı</h1><p>Yönetici parolasını kontrol edip yeniden deneyin.</p><a href='/atolye-yonetim-8f31/login'>Geri dön</a></section>"), 401)
        if path.startswith("/atolye-yonetim-8f31/"):
            admin = self.get_admin()
            if not admin: return self.redirect("/atolye-yonetim-8f31/login")
            if not self.csrf_ok(fields): return self.send_error(403, "İstek doğrulanamadı. Sayfayı yenileyip tekrar deneyin.")
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
                code = form_value("code").upper()[:30]
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
                category = form_value("category_choice", "category_choice[]", "category", "category_name")[:80]
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
                missing = []
                if not code: missing.append("eser kodu")
                if not title: missing.append("eser adı")
                if not size: missing.append("geçerli ölçü (genişlik × yükseklik)")
                if price < 0: missing.append("geçerli liste fiyatı")
                if missing: raise ValueError("Eksik veya geçersiz alan: " + ", ".join(missing) + ".")
                image = self.upload_file(files.get("image"), "works", "work-")
                featured, sold = int(fields.get("featured") == "1"), int(fields.get("sold") == "1")
                show_new = int(fields.get("show_new") == "1")
                show_collections = int(fields.get("show_collections") == "1")
                show_curated = int(fields.get("show_curated") == "1")
                if not (show_new or show_collections or show_curated): raise ValueError("Tablonun görüneceği en az bir ana sayfa bölümü seçin.")
                with connect() as c:
                    if pid:
                        old = c.execute("SELECT image FROM products WHERE id=?", (pid,)).fetchone()
                        if not old: return self.send_error(404)
                        image = image or old["image"]
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
            allowed = ("site_name", "whatsapp_url", "instagram_url", "tiktok_url", "telegram_url")
            with connect() as c:
                for key in allowed:
                    val = fields.get(key, "").strip()
                    if key.endswith("_url"): val = safe_url(val)
                    c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key,val[:500]))
                categories = ", ".join(dict.fromkeys(x.strip()[:80] for x in fields.get("categories", "").split(",") if x.strip()))
                c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('categories',?)", (categories,))
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

