#!/usr/bin/env python3
"""
Generates one static HTML file per approved SabiBiz business at
  /biz/<slug>/index.html

Why this exists: sabibiz.com.ng is a single-page app, so when someone
shares their business profile link on WhatsApp/Facebook/etc, the link
preview crawler can't see the per-business content (it doesn't run
JavaScript) and just shows the generic SabiBiz card for every business.

Each generated page here is static, so crawlers see the correct business
name/description/photo immediately. Real visitors are redirected straight
into the live app (the existing #/biz/<slug> route) within a fraction of
a second, so the experience is unchanged for humans.

Run manually with:  python3 generate_biz_pages.py
Or let the GitHub Action (.github/workflows/generate-biz-pages.yml) run
it automatically on a schedule.
"""
import csv
import io
import os
import re
import sys
import urllib.request

# Same published CSV used by the live site (DIR_SHEET_CSV_URL in index.html)
CSV_URL = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vSE8OY5THzmy7vP_-Oy40jSuK2GzbFCtnIqaL6ljltuFZdL7tkE3fCP0l7BvoFW8gJzn_ulx0yhH0Fr/pub?gid=1432562113&single=true&output=csv'

SITE_URL = 'https://sabibiz.com.ng'
DEFAULT_IMAGE = SITE_URL + '/og-image.png'
OUTPUT_DIR = 'biz'  # creates biz/<slug>/index.html next to index.html


def norm_key(header):
    """Mirrors dirNormKey() in index.html: lowercase, strip non-alphanumerics."""
    return re.sub(r'[^a-z0-9]', '', header.strip().lower())


def slugify(name):
    """Mirrors dirSlug() in index.html exactly, so URLs always match."""
    s = (name or '').strip().lower()
    s = re.sub(r'[^a-z0-9]+', '-', s)
    return s.strip('-')


def escape_html(s):
    return (
        (s or '')
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
    )


def fetch_rows():
    with urllib.request.urlopen(CSV_URL, timeout=30) as resp:
        raw = resp.read().decode('utf-8')
    reader = csv.reader(io.StringIO(raw))
    rows = list(reader)
    if not rows:
        return []
    headers = [norm_key(h) for h in rows[0]]
    out = []
    for r in rows[1:]:
        row = {headers[i]: (r[i] if i < len(r) else '') for i in range(len(headers))}
        out.append(row)
    return out


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="{description}">

<meta property="og:type" content="business.business">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:image" content="{image}">
<meta property="og:url" content="{url}">
<meta property="og:site_name" content="SabiBiz">

<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{description}">
<meta name="twitter:image" content="{image}">

<link rel="canonical" href="{url}">
<meta http-equiv="refresh" content="0;url={redirect_url}">
<script>window.location.replace({redirect_url_js});</script>
<style>body{{font-family:sans-serif;background:#0d0d0d;color:#fff;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}}</style>
</head>
<body>
<p>Redirecting to <a href="{redirect_url}" style="color:#FF6B00;">{business_name}</a> on SabiBiz…</p>
</body>
</html>
"""


def build_page(row):
    name = (row.get('businessname') or '').strip()
    if not name:
        return None
    slug = slugify(name)
    desc = (row.get('description') or '').strip()
    desc = (desc[:155] + '…') if len(desc) > 155 else desc
    if not desc:
        desc = f"Find {name} on SabiBiz — Nigeria's free business directory."
    photo = (row.get('photourl') or '').strip()
    image = photo if photo.startswith('http') else DEFAULT_IMAGE
    page_url = f"{SITE_URL}/biz/{slug}/"
    redirect_url = f"{SITE_URL}/#/biz/{slug}"

    html = PAGE_TEMPLATE.format(
        title=escape_html(f"{name} — SabiBiz Business Directory"),
        description=escape_html(desc),
        image=escape_html(image),
        url=escape_html(page_url),
        redirect_url=escape_html(redirect_url),
        redirect_url_js=repr(redirect_url),
        business_name=escape_html(name),
    )
    return slug, html


def main():
    try:
        rows = fetch_rows()
    except Exception as e:
        print(f"Could not fetch the directory CSV: {e}", file=sys.stderr)
        sys.exit(1)

    approved = [r for r in rows if (r.get('status') or '').strip().lower() == 'approved']
    print(f"Found {len(approved)} approved businesses.")

    written = 0
    for row in approved:
        result = build_page(row)
        if not result:
            continue
        slug, html = result
        folder = os.path.join(OUTPUT_DIR, slug)
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, 'index.html')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html)
        written += 1

    print(f"Wrote {written} pages into ./{OUTPUT_DIR}/")


if __name__ == '__main__':
    main()
