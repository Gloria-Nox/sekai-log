#!/usr/bin/env python3
import os, re, json
from datetime import datetime

posts_dir = '_posts'
categories = ['anime', 'novel', 'sf', 'subculture', 'review']
SITE_URL = 'https://sekai-log.pages.dev'

def parse_frontmatter(text):
    match = re.match(r'^---
([\s\S]*?)
---
?([\s\S]*)$', text)
    if not match: return {}, text
    data = {}
    for line in match.group(1).split('
'):
        idx = line.find(':')
        if idx == -1: continue
        key = line[:idx].strip()
        val = line[idx+1:].strip().strip(chr(34)+chr(39))
        if key: data[key] = val
    return data, match.group(2)

all_articles = []
for cat in categories:
    cat_dir = os.path.join(posts_dir, cat)
    if not os.path.exists(cat_dir): continue
    for fname in sorted(os.listdir(cat_dir), reverse=True):
        if not fname.endswith('.md'): continue
        with open(os.path.join(cat_dir, fname), encoding='utf-8') as f: text = f.read()
        data, content = parse_frontmatter(text)
        chars = len(re.sub(r'[#\-\*`>\[\]!\s]', '', content))
        readtime = data.get('readtime', str(max(1, round(chars/400))) + chr(20998))
        all_articles.append({'title':data.get('title',''),'date':data.get('date',''),'decade':data.get('decade',''),'excerpt':data.get('excerpt',''),'readtime':readtime,'thumbnail':data.get('thumbnail',''),'category':cat,'slug':fname.replace('.md',''),'content':content.strip()})

all_articles.sort(key=lambda x: x['date'], reverse=True)
with open('articles.json','w',encoding='utf-8') as f: json.dump(all_articles, f, ensure_ascii=False, indent=2)
print('articles.json: ' + str(len(all_articles)) + ' articles')

today = datetime.now().strftime('%Y-%m-%d')
static = [('index.html','1.0','daily'),('all.html','0.9','daily'),('anime.html','0.8','weekly'),('novel.html','0.8','weekly'),('sf.html','0.8','weekly'),('subculture.html','0.8','weekly'),('review.html','0.8','weekly'),('about.html','0.5','monthly'),('search.html','0.5','monthly'),('privacy.html','0.3','monthly')]
lines = [chr(60)+'?xml version='+chr(34)+'1.0'+chr(34)+' encoding='+chr(34)+'UTF-8'+chr(34)+'?'+chr(62), '<urlset xmlns='+chr(34)+'http://www.sitemaps.org/schemas/sitemap/0.9'+chr(34)+'>']
for p,pr,f in static:
    lines.append('  <url><loc>'+SITE_URL+'/'+p+'</loc><lastmod>'+today+'</lastmod><changefreq>'+f+'</changefreq><priority>'+pr+'</priority></url>')
for a in all_articles:
    lines.append('  <url><loc>'+SITE_URL+'/article.html?category='+a['category']+'&amp;slug='+a['slug']+'</loc><lastmod>'+a.get('date',today)+'</lastmod><changefreq>monthly</changefreq><priority>0.7</priority></url>')
lines.append('</urlset>')
open('sitemap.xml','w').write('
'.join(lines))
print('sitemap.xml OK')
open('robots.txt','w').write('User-agent: *
Allow: /
Sitemap: '+SITE_URL+'/sitemap.xml
')
print('robots.txt OK')
