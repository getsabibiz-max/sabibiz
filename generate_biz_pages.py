#!/usr/bin/env python3
"""
Generates static, crawlable HTML pages for every APPROVED SabiBiz directory
listing, a /biz/ hub page, and a refreshed sitemap.xml.

Run by .github/workflows/generate-biz-pages.yml on a schedule. Safe to run
repeatedly — it always rebuilds from the live published CSV, so output never
drifts from what's actually approved in the Sheet (removed/unapproved rows
simply stop being regenerated; existing files for them are left in place by
design — delete manually if a listing should be taken down).
"""
import csv
import io
import os
import re
import shutil
import sys
import urllib.request
from datetime import datetime, timezone
from urllib.parse import quote

try:
    from dateutil import parser as dateparser
except ImportError:
    dateparser = None

CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSE8OY5THzmy7vP_-Oy40jSuK2GzbFCtnIqaL6ljltuFZdL7tkE3fCP0l7BvoFW8gJzn_ulx0yhH0Fr/pub?gid=1432562113&single=true&output=csv"
BASE = "https://sabibiz.com.ng"
REPO_ROOT = os.environ.get("REPO_ROOT", ".")
OUT_DIR = os.path.join(REPO_ROOT, "biz")
SITEMAP_PATH = os.path.join(REPO_ROOT, "sitemap.xml")

# Fixed, hand-written pages that also belong in the sitemap (kept in sync
# with the Learning Centre stub built separately).
STATIC_URLS = [
    (f"{BASE}/", "1.0", "weekly"),
    (f"{BASE}/learn/", "0.9", "weekly"),
    (f"{BASE}/learn/why-selling-every-day-still-broke.html", "0.8", "monthly"),
    (f"{BASE}/learn/price-products-without-selling-at-a-loss.html", "0.8", "monthly"),
    (f"{BASE}/learn/five-minute-daily-business-habit.html", "0.8", "monthly"),
    (f"{BASE}/biz/", "0.8", "daily"),
]


def norm_key(h):
    return re.sub(r"[^a-z0-9]", "", h.strip().lower())


def fetch_csv(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return parse_csv_text(raw)


def parse_csv_text(raw):
    reader = csv.reader(io.StringIO(raw))
    rows = list(reader)
    if not rows:
        return []
    headers = [norm_key(h) for h in rows[0]]
    out = []
    for r in rows[1:]:
        if not any(c.strip() for c in r):
            continue
        row = {headers[i]: (r[i] if i < len(r) else "") for i in range(len(headers))}
        out.append(row)
    return out


def slugify(name):
    s = (name or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def esc(s):
    s = s or ""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def parse_timestamp(raw):
    if not raw:
        return None
    if dateparser:
        try:
            return dateparser.parse(raw)
        except Exception:
            return None
    for fmt in ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except Exception:
            continue
    return None


def whatsapp_link(num, name):
    digits = re.sub(r"\D", "", num or "")
    full = digits if digits.startswith("234") else "234" + re.sub(r"^0", "", digits)
    text = f"Hi {name}, I found you on the SabiBiz Directory!"
    return f"https://wa.me/{full}?text={quote(text)}"


def parse_social_links(raw):
    raw = (raw or "").strip()
    if not raw:
        return []
    labels = {"IG": ("📸", "Instagram"), "FB": ("📘", "Facebook"), "TT": ("🎵", "TikTok"), "X": ("🐦", "X")}
    out = []
    for seg in raw.split("|"):
        seg = seg.strip()
        m = re.match(r"^(IG|FB|TT|X):\s*(.+)$", seg, re.I)
        if not m:
            continue
        link = m.group(2).strip()
        if not link:
            continue
        if not re.match(r"^https?://", link, re.I):
            link = "https://" + link
        icon, label = labels.get(m.group(1).upper(), ("🔗", "Link"))
        out.append((icon, label, link))
    if out:
        return out
    link = raw
    if not re.match(r"^https?://", link, re.I):
        link = "https://" + link
    return [("📸", "See Photos & Social Page", link)]


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="{meta_description}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{url}">
<meta property="og:type" content="business.business">
<meta property="og:site_name" content="SabiBiz">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{meta_description}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{base}/og-image.png">
<meta property="og:locale" content="en_NG">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{meta_description}">
<meta name="twitter:image" content="{base}/og-image.png">
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700;800&family=DM+Sans:wght@400;500&display=swap" rel="stylesheet">
<script type="application/ld+json">
{jsonld}
</script>
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
:root{{--o:#E84800;--op:#FFF5F0;--g:#0F6E56;--dk:#0F0F0F;--md:#555;--mt:#888;--lt:#F7F4F0;--wh:#fff;--br:#E5DDD5;}}
body{{font-family:'DM Sans',sans-serif;background:var(--wh);color:var(--dk);line-height:1.7;}}
h1,h2{{font-family:'Sora',sans-serif;letter-spacing:-.3px;}}
.wrap{{max-width:640px;margin:0 auto;padding:0 22px;}}
header{{padding:22px 0;border-bottom:1px solid var(--br);}}
.header-inner{{max-width:640px;margin:0 auto;padding:0 22px;display:flex;align-items:center;justify-content:space-between;}}
.logo{{font-family:'Sora',sans-serif;font-weight:800;font-size:1.3rem;color:var(--dk);text-decoration:none;}}
.logo span{{color:var(--o);}}
.back-link{{font-family:'Sora',sans-serif;font-size:.78rem;font-weight:700;color:var(--o);text-decoration:none;}}
main{{padding:0 0 60px;}}
.hero{{background:var(--dk);color:#fff;text-align:center;padding:40px 22px;}}
.avatar{{width:64px;height:64px;border-radius:50%;background:var(--o);color:#fff;display:flex;align-items:center;justify-content:center;font-family:'Sora',sans-serif;font-weight:800;font-size:1.6rem;margin:0 auto 14px;}}
.hero h1{{font-size:1.5rem;font-weight:800;margin-bottom:8px;}}
.badge{{display:inline-block;font-family:'Sora',sans-serif;font-size:.68rem;font-weight:700;padding:4px 10px;border-radius:20px;background:linear-gradient(135deg,#FFD700,#FFA500);color:#3a2a00;margin:4px 3px;}}
.loc{{font-size:.85rem;color:rgba(255,255,255,.65);margin-bottom:8px;}}
.cat{{display:inline-block;font-family:'Sora',sans-serif;font-size:.7rem;font-weight:700;background:rgba(255,255,255,.12);padding:4px 11px;border-radius:20px;}}
.card{{max-width:640px;margin:-24px auto 0;background:var(--wh);border:1.5px solid var(--br);border-radius:16px;padding:26px 24px;position:relative;}}
.desc{{font-size:.96rem;color:var(--md);margin-bottom:18px;}}
.actions{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px;}}
.btn{{font-family:'Sora',sans-serif;font-weight:700;font-size:.84rem;padding:12px;border-radius:9px;border:none;cursor:pointer;text-align:center;text-decoration:none;display:block;}}
.btn-wa{{background:#25D366;color:#fff;}}
.btn-ghost{{background:var(--lt);color:var(--dk);border:1.5px solid var(--br);}}
.tags{{display:flex;gap:7px;flex-wrap:wrap;margin-top:14px;}}
.tag{{font-family:'Sora',sans-serif;font-size:.72rem;font-weight:700;background:var(--lt);border:1px solid var(--br);padding:6px 11px;border-radius:20px;color:var(--md);}}
.map-wrap{{border-radius:12px;overflow:hidden;border:1.5px solid var(--br);margin:14px 0;}}
.social-row{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px;}}
.social-row a{{flex:1;min-width:90px;}}
footer{{border-top:1px solid var(--br);padding:26px 0;text-align:center;}}
footer p{{font-size:.78rem;color:var(--mt);}}
footer a{{color:var(--o);text-decoration:none;font-weight:700;}}
</style>
</head>
<body>
<header>
  <div class="header-inner">
    <a class="logo" href="{base}/">Sabi<span>Biz</span></a>
    <a class="back-link" href="{base}/biz/">← All Businesses</a>
  </div>
</header>
<main>
  <div class="hero">
    <div class="avatar">{initial}</div>
    <h1>{name} {verified}</h1>
    {founder_badge}
    <div class="loc">📍 {location}</div>
    <span class="cat">{category}</span>
  </div>
  <div class="card">
    <p class="desc">{description}</p>
    <div class="actions">
      <a class="btn btn-wa" href="{wa_link}" target="_blank">💬 WhatsApp</a>
      {call_btn}
    </div>
    <a class="btn btn-ghost" href="{maps_link}" target="_blank" style="margin-bottom:12px;">📍 Get Directions</a>
    <div class="map-wrap"><iframe src="{maps_embed}" width="100%" height="170" style="border:0;display:block;" loading="lazy" title="Map"></iframe></div>
    {social_html}
    <div class="tags">
      {age_tag}
      <span class="tag">✅ Verified by SabiBiz</span>
      {founder_tag}
    </div>
  </div>
</main>
<footer>
  <p>Want to be discovered like this? <a href="{base}/directory.html">List your business free on SabiBiz →</a></p>
  <p style="margin-top:8px;">© 2026 SabiBiz Tech Systems · Lagos, Nigeria</p>
</footer>
</body>
</html>
"""

HUB_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Business Directory — Find Verified Nigerian Businesses | SabiBiz</title>
<meta name="description" content="Browse verified Nigerian small businesses listed on SabiBiz. Find vendors, services, and shops by category and location.">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{base}/biz/">
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700;800&family=DM+Sans:wght@400;500&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
:root{{--o:#E84800;--dk:#0F0F0F;--md:#555;--mt:#888;--lt:#F7F4F0;--wh:#fff;--br:#E5DDD5;}}
body{{font-family:'DM Sans',sans-serif;background:var(--wh);color:var(--dk);line-height:1.7;}}
h1,h2{{font-family:'Sora',sans-serif;letter-spacing:-.3px;}}
.wrap{{max-width:760px;margin:0 auto;padding:0 22px;}}
header{{padding:22px 0;border-bottom:1px solid var(--br);}}
.header-inner{{max-width:760px;margin:0 auto;padding:0 22px;display:flex;align-items:center;justify-content:space-between;}}
.logo{{font-family:'Sora',sans-serif;font-weight:800;font-size:1.3rem;color:var(--dk);text-decoration:none;}}
.logo span{{color:var(--o);}}
.back-link{{font-family:'Sora',sans-serif;font-size:.78rem;font-weight:700;color:var(--o);text-decoration:none;}}
main{{padding:46px 0 70px;background:var(--lt);}}
h1.hub-h1{{font-size:clamp(1.7rem,5vw,2.2rem);font-weight:800;margin-bottom:10px;}}
main>.wrap>p.lede{{color:var(--md);margin-bottom:30px;max-width:520px;}}
.biz-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:14px;}}
.biz-item{{display:block;background:var(--wh);border:1.5px solid var(--br);border-radius:12px;padding:16px 18px;text-decoration:none;transition:border-color .15s;}}
.biz-item:hover{{border-color:var(--o);}}
.biz-item h2{{font-size:.92rem;font-weight:700;color:var(--dk);margin-bottom:5px;}}
.biz-item .loc{{font-size:.78rem;color:var(--mt);}}
.biz-item .cat{{display:inline-block;font-family:'Sora',sans-serif;font-size:.62rem;font-weight:700;color:var(--o);text-transform:uppercase;letter-spacing:.4px;margin-top:6px;}}
footer{{border-top:1px solid var(--br);padding:26px 0;text-align:center;}}
footer p{{font-size:.78rem;color:var(--mt);}}
footer a{{color:var(--o);text-decoration:none;font-weight:700;}}
</style>
</head>
<body>
<header>
  <div class="header-inner">
    <a class="logo" href="{base}/">Sabi<span>Biz</span></a>
    <a class="back-link" href="{base}/">← sabibiz.com.ng</a>
  </div>
</header>
<main>
  <div class="wrap">
    <h1 class="hub-h1">Business Directory</h1>
    <p class="lede">{count} verified Nigerian businesses, listed free on SabiBiz.</p>
    <div class="biz-grid">
      {items}
    </div>
  </div>
</main>
<footer>
  <p>© 2026 SabiBiz Tech Systems · Lagos, Nigeria · <a href="{base}/">sabibiz.com.ng</a></p>
</footer>
</body>
</html>
"""


def build_business_page(biz, idx, all_count):
    name = biz.get("businessname", "").strip()
    slug = slugify(name)
    location = biz.get("location", "").strip()
    category = biz.get("category", "").strip() or "Business"
    description = biz.get("description", "").strip()
    wa_raw = biz.get("whatsappnumber", "").strip()
    age = biz.get("howlongthebusinesshasexisted", "").strip()
    social_raw = biz.get("socialmedialinkinstagramtiktokfacebook", "").strip()

    url = f"{BASE}/biz/{slug}/"
    title = f"{name} — SabiBiz Business Directory"
    description_meta = (description[:155] + " | Find on SabiBiz") if description else f"{name} on SabiBiz — {category} in {location}."

    is_founder = idx < 50
    founder_badge = (
        '<div style="margin:6px 0;"><span class="badge">🏆 Founding Member</span></div>' if is_founder else ""
    )
    founder_tag = '<span class="tag">🏆 Founding Member — First 50</span>' if is_founder else ""
    age_tag = f'<span class="tag">🕐 {esc(age)}</span>' if age else ""

    wa_link = whatsapp_link(wa_raw, name)
    call_btn = (
        f'<a class="btn btn-ghost" href="tel:{esc(wa_raw)}">📞 Call</a>' if wa_raw else "<span></span>"
    )
    maps_query = quote(f"{name}, {location}, Nigeria")
    maps_link = f"https://www.google.com/maps/search/?api=1&query={maps_query}"
    maps_embed = f"https://www.google.com/maps?q={maps_query}&output=embed"

    socials = parse_social_links(social_raw)
    social_html = ""
    if socials:
        items = "".join(
            f'<a class="btn btn-ghost" href="{link}" target="_blank">{icon} {label}</a>'
            for icon, label, link in socials
        )
        social_html = f'<div class="social-row">{items}</div>'

    jsonld = f"""{{
  "@context": "https://schema.org",
  "@type": "LocalBusiness",
  "name": "{esc(name)}",
  "description": "{esc(description_meta)}",
  "address": {{"@type": "PostalAddress", "addressLocality": "{esc(location)}", "addressCountry": "NG"}},
  "url": "{url}"
}}"""

    page = PAGE_TEMPLATE.format(
        title=esc(title),
        meta_description=esc(description_meta),
        url=url,
        base=BASE,
        jsonld=jsonld,
        initial=esc(name[:1].upper() if name else "?"),
        name=esc(name),
        verified="✅",
        founder_badge=founder_badge,
        location=esc(location),
        category=esc(category),
        description=esc(description),
        wa_link=wa_link,
        call_btn=call_btn,
        maps_link=maps_link,
        maps_embed=maps_embed,
        social_html=social_html,
        age_tag=age_tag,
        founder_tag=founder_tag,
    )
    return slug, page, name, location, category, is_founder


def main():
    try:
        rows = fetch_csv(CSV_URL)
    except Exception as e:
        print(f"ERROR: could not fetch directory CSV: {e}", file=sys.stderr)
        sys.exit(1)

    approved = [r for r in rows if (r.get("status", "") or "").strip().lower() == "approved"]
    print(f"Fetched {len(rows)} rows, {len(approved)} approved.")

    os.makedirs(OUT_DIR, exist_ok=True)
    hub_items = []
    sitemap_urls = list(STATIC_URLS)

    for idx, biz in enumerate(approved):
        name = (biz.get("businessname") or "").strip()
        if not name:
            continue
        slug, page_html, name, location, category, is_founder = build_business_page(biz, idx, len(approved))
        biz_dir = os.path.join(OUT_DIR, slug)
        os.makedirs(biz_dir, exist_ok=True)
        with open(os.path.join(biz_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(page_html)
        sitemap_urls.append((f"{BASE}/biz/{slug}/", "0.7", "weekly"))
        badge = " 🏆" if is_founder else ""
        hub_items.append(
            f'<a class="biz-item" href="{BASE}/biz/{slug}/">'
            f"<h2>{esc(name)}{badge}</h2>"
            f'<div class="loc">📍 {esc(location)}</div>'
            f'<span class="cat">{esc(category or "Business")}</span>'
            f"</a>"
        )

    hub_html = HUB_TEMPLATE.format(base=BASE, count=len(hub_items), items="\n      ".join(hub_items))
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(hub_html)

    sitemap_xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url, priority, freq in sitemap_urls:
        sitemap_xml.append(f"  <url><loc>{url}</loc><changefreq>{freq}</changefreq><priority>{priority}</priority></url>")
    sitemap_xml.append("</urlset>")
    with open(SITEMAP_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(sitemap_xml) + "\n")

    print(f"Generated {len(hub_items)} business pages + hub + sitemap.xml ({len(sitemap_urls)} URLs).")


if __name__ == "__main__":
    main()
