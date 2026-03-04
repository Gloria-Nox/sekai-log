import os, json
from datetime import datetime

posts_dir = '_posts'
categories = ['anime', 'novel', 'sf', 'subculture', 'review']
SITE_URL = 'https://sekai-log.com'

def parse_frontmatter(text):
    lines = text.split('\n')
    if not lines or lines[0] != '---':
        return {}, text
    end = None
    for i, line in enumerate(lines[1:], 1):
        if line == '---':
            end = i
            break
    if end is None:
        return {}, text
    data = {}
    for line in lines[1:end]:
        idx = line.find(':')
        if idx == -1:
            continue
        key = line[:idx].strip()
        val = line[idx+1:].strip().strip('"\'')
        if key:
            data[key] = val
    return data, '\n'.join(lines[end+1:])

all_articles = []
for cat in categories:
    cat_dir = os.path.join(posts_dir, cat)
    if not os.path.exists(cat_dir):
        continue
    for fname in sorted(os.listdir(cat_dir), reverse=True):
        if not fname.endswith('.md'):
            continue
        with open(os.path.join(cat_dir, fname), encoding='utf-8') as f:
            text = f.read()
        data, content = parse_frontmatter(text)
        chars = len(content)
        readtime = data.get('readtime', str(max(1, round(chars/400))) + '分')
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
print('articles.json: ' + str(len(all_articles)) + ' articles')

today = datetime.now().strftime('%Y-%m-%d')
static = [
    ('index.html', '1.0', 'daily'),
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
lns = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
]
for p, pr, f in static:
    lns.append('  <url><loc>' + SITE_URL + '/' + p + '</loc><lastmod>' + today + '</lastmod><changefreq>' + f + '</changefreq><priority>' + pr + '</priority></url>')
for a in all_articles:
    lns.append('  <url><loc>' + SITE_URL + '/article.html?category=' + a['category'] + '&amp;slug=' + a['slug'] + '</loc><lastmod>' + a.get('date', today) + '</lastmod><changefreq>monthly</changefreq><priority>0.7</priority></url>')
lns.append('</urlset>')
open('sitemap.xml', 'w').write('\n'.join(lns))
print('sitemap.xml OK')
open('robots.txt', 'w').write('User-agent: *\nAllow: /\nSitemap: ' + SITE_URL + '/sitemap.xml\n')
print('robots.txt OK')
