#!/usr/bin/env python3
# build.py v9 - articles.json + sitemap.xml 自動生成

import os, re, json
from datetime import datetime

posts_dir = '_posts'
categories = ['anime', 'novel', 'sf', 'subculture', 'review']
SITE_URL = 'https://sekai-log.netlify.app'

def parse_frontmatter(text):
    match = re.match(r'^---\n([\s\S]*?)\n---\n?([\s\S]*)$', text)
    if not match:
        return {}, text
    data = {}
    for line in match.group(1).split('\n'):
        idx = line.find(':')
        if idx == -1: continue
        key = line[:idx].strip()
        val = line[idx+1:].strip().strip('"\'')
        if key: data[key] = val
    return data, match.group(2)

# articles.json 生成
all_articles = []
for cat in categories:
    cat_dir = os.path.join(posts_dir, cat)
    if not os.path.exists(cat_dir): continue
    for fname in sorted(os.listdir(cat_dir), reverse=True):
        if not fname.endswith('.md'): continue
        with open(os.path.join(cat_dir, fname), encoding='utf-8') as f:
            text = f.read()
        data, content = parse_frontmatter(text)
        chars = len(re.sub(r'[#\-\*`>\[\]!\s]', '', content))
        readtime = data.get('readtime', f'{max(1, round(chars/400))}分')
        all_articles.append({
            'title': data.get('title', ''),
            'date': data.get('date', ''),
            'decade': data.get('decade', ''),
            'excerpt': data.get('excerpt', ''),
            'readtime': readtime,
            'thumbnail': data.get('thumbnail', ''),
            'category': cat,
            'slug': fname.replace('.md', ''),
            'content': content.strip()
        })

all_articles.sort(key=lambda x: x['date'], reverse=True)
with open('articles.json', 'w', encoding='utf-8') as f:
    json.dump(all_articles, f, ensure_ascii=False, indent=2)
print(f'articles.json: {len(all_articles)} articles')

# sitemap.xml 生成
today = datetime.now().strftime('%Y-%m-%d')
static_pages = [
    ('', '1.0', 'daily'),
    ('all.html', '0.9', 'daily'),
    ('anime.html', '0.8', 'weekly'),
    ('novel.html', '0.8', 'weekly'),
    ('sf.html', '0.8', 'weekly'),
    ('subculture.html', '0.8', 'weekly'),
    ('review.html', '0.8', 'weekly'),
    ('about.html', '0.5', 'monthly'),
    ('search.html', '0.5', 'monthly'),
    ('privacy.html', '0.3', 'monthly'),
]

lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
for page, priority, freq in static_pages:
    loc = SITE_URL + '/' + page
    lines.append(f'  <url><loc>{loc}</loc><lastmod>{today}</lastmod><changefreq>{freq}</changefreq><priority>{priority}</priority></url>')
for a in all_articles:
    loc = f'{SITE_URL}/article.html?category={a["category"]}&amp;slug={a["slug"]}'
    date = a.get('date', today)
    lines.append(f'  <url><loc>{loc}</loc><lastmod>{date}</lastmod><changefreq>monthly</changefreq><priority>0.7</priority></url>')
lines.append('</urlset>')

with open('sitemap.xml', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print(f'sitemap.xml: {len(lines)-2} URLs')

# robots.txt 生成
robots = f'User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n'
with open('robots.txt', 'w') as f:
    f.write(robots)
print('robots.txt: generated')
