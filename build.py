#!/usr/bin/env python3
# build.py - Netlifyデプロイ時に自動実行してarticles.jsonを生成

import os, re, json

posts_dir = '_posts'
categories = ['anime', 'novel', 'sf', 'subculture', 'review']

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

print(f'✅ articles.json generated: {len(all_articles)} articles')
