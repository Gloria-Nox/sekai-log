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


def parse_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except ValueError:
        return None


def normalize_readtime(raw, chars):
    if raw is None or str(raw).strip() == '':
        return str(max(1, round(chars / 400))) + '分'
    txt = str(raw).strip()
    if txt.isdigit():
        return txt + '分'
    return txt


def validate_article(data, content, cat, fname):
    errors = []
    warnings = []
    required = ['title', 'date', 'excerpt']
    for key in required:
        if not str(data.get(key, '')).strip():
            errors.append('missing required frontmatter: ' + key)

    if data.get('date') and parse_date(data.get('date')) is None:
        errors.append('invalid date format: ' + str(data.get('date')))

    if cat in ['anime', 'novel', 'sf'] and not str(data.get('decade', '')).strip():
        warnings.append('recommended field missing: decade')

    if not content.strip():
        warnings.append('empty article body')

    return errors, warnings

all_articles = []
issues = []
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
        errors, warnings = validate_article(data, content, cat, fname)
        if errors or warnings:
            issues.append({
                'category': cat,
                'file': fname,
                'errors': errors,
                'warnings': warnings
            })

        chars = len(content)
        readtime = normalize_readtime(data.get('readtime'), chars)
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

error_count = 0
warning_count = 0
for issue in issues:
    head = '[' + issue['category'] + '/' + issue['file'] + ']'
    for msg in issue['errors']:
        error_count += 1
        print('ERROR ' + head + ' ' + msg)
    for msg in issue['warnings']:
        warning_count += 1
        print('WARN  ' + head + ' ' + msg)

if error_count > 0:
    raise SystemExit('build aborted: ' + str(error_count) + ' validation error(s)')

with open('articles.json', 'w', encoding='utf-8') as f:
    json.dump(all_articles, f, ensure_ascii=False, indent=2)
print('articles.json: ' + str(len(all_articles)) + ' articles')
if warning_count:
    print('validation warnings: ' + str(warning_count))

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
