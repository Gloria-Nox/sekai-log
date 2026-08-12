"""SEKAI LOG static site generator.

The Markdown files in _posts are the single source of truth. Running this file
builds every public HTML page, the JSON search index, RSS, sitemap and robots.
No third-party Python packages are required.
"""

from __future__ import annotations

import html
import json
import math
import re
import shutil
from datetime import datetime
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).parent
POSTS_DIR = ROOT / "_posts"
ARTICLE_DIR = ROOT / "articles"
ANIME_DATA = ROOT / "data" / "anime.json"
SITE_URL = "https://sekai-log.com"
SITE_NAME = "SEKAI LOG"
AUTHOR = "藤乃宮遊"
GA_ID = "G-2EKFMMWGGZ"

CATEGORIES = {
    "anime": ("アニメ", "ANIME", "演出、物語、キャラクターから作品の問いを読む。"),
    "novel": ("小説", "NOVEL", "小説とライトノベルを、時代やジャンルの境界から読む。"),
    "sf": ("SF", "SCIENCE FICTION", "思考実験が映し出す、人間と社会の輪郭を追う。"),
    "subculture": ("サブカルチャー", "SUBCULTURE", "創作と受容の現場から、文化の変化を記録する。"),
    "review": ("評論", "CRITICISM", "複数の作品や時代を横断し、共通する問いを考える。"),
}


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    marker = text.find("\n---\n", 4)
    if marker < 0:
        return {}, text
    data: dict[str, str] = {}
    for line in text[4:marker].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        data[key.strip()] = value
    return data, text[marker + 5 :].strip()


def parse_date(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return datetime(1970, 1, 1)


def date_label(value: str) -> str:
    date = parse_date(value)
    return f"{date.year}.{date.month:02d}.{date.day:02d}"


def safe_url(url: str) -> str:
    url = url.strip()
    if url.startswith(("https://", "http://", "/", "#", "mailto:")):
        return html.escape(url, quote=True)
    return "#"


def inline_md(value: str) -> str:
    value = html.escape(value, quote=False)
    value = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: f'<a href="{safe_url(html.unescape(m.group(2)))}">{m.group(1)}</a>',
        value,
    )
    value = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", value)
    value = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", value)
    value = re.sub(r"`([^`]+)`", r"<code>\1</code>", value)
    return value


def markdown_to_html(markdown: str) -> tuple[str, list[tuple[str, str]]]:
    """Render the small Markdown subset used by the site, escaping raw HTML."""
    lines = markdown.splitlines()
    out: list[str] = []
    toc: list[tuple[str, str]] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    list_kind = "ul"

    def flush_paragraph() -> None:
        if paragraph:
            out.append("<p>" + " ".join(inline_md(x.strip()) for x in paragraph) + "</p>")
            paragraph.clear()

    def flush_list() -> None:
        nonlocal list_kind
        if list_items:
            out.append(f"<{list_kind}>" + "".join(list_items) + f"</{list_kind}>")
            list_items.clear()

    for raw in lines + [""]:
        line = raw.rstrip()
        if not line.strip():
            flush_paragraph()
            flush_list()
            continue
        heading = re.match(r"^(#{2,3})\s+(.+)$", line)
        if heading:
            flush_paragraph()
            flush_list()
            level = len(heading.group(1))
            title = heading.group(2).strip()
            section_id = f"section-{len(toc) + 1}"
            toc.append((section_id, re.sub(r"[*`]", "", title)))
            out.append(f'<h{level} id="{section_id}">{inline_md(title)}</h{level}>')
            continue
        if re.match(r"^[-*_]{3,}$", line.strip()):
            flush_paragraph()
            flush_list()
            out.append("<hr>")
            continue
        if line.startswith("> "):
            flush_paragraph()
            flush_list()
            out.append(f"<blockquote><p>{inline_md(line[2:])}</p></blockquote>")
            continue
        bullet = re.match(r"^[-*]\s+(.+)$", line)
        ordered = re.match(r"^\d+\.\s+(.+)$", line)
        if bullet or ordered:
            flush_paragraph()
            wanted = "ol" if ordered else "ul"
            if list_items and list_kind != wanted:
                flush_list()
            list_kind = wanted
            text = (ordered or bullet).group(1)
            list_items.append(f"<li>{inline_md(text)}</li>")
            continue
        paragraph.append(line)
    return "\n".join(out), toc


def load_articles() -> tuple[list[dict], list[str]]:
    articles: list[dict] = []
    notes: list[str] = []
    for path in sorted(POSTS_DIR.glob("*/*.md")):
        data, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        rel = path.relative_to(ROOT).as_posix()
        missing = [key for key in ("title", "date", "excerpt") if not data.get(key)]
        if missing:
            raise SystemExit(f"{rel}: missing frontmatter: {', '.join(missing)}")
        if data.get("status", "published").lower() != "published":
            notes.append(f"DRAFT {rel}")
            continue
        category = path.parent.name
        if category not in CATEGORIES:
            raise SystemExit(f"{rel}: unknown category {category}")
        slug = data.get("slug") or path.stem
        if not re.fullmatch(r"[a-z0-9-]+", slug):
            raise SystemExit(f"{rel}: published article requires an ASCII slug")
        plain_chars = len(re.sub(r"[#*`>\[\]()_-]", "", body).replace("\n", ""))
        read_minutes = max(1, math.ceil(plain_chars / 450))
        amazon_items = []
        for index in range(1, 6):
            suffix = "" if index == 1 else f"_{index}"
            amazon_url = data.get(f"amazon_url{suffix}", "")
            if amazon_url:
                amazon_items.append({
                    "url": amazon_url,
                    "label": data.get(f"amazon_label{suffix}", "Amazonで見る"),
                    "note": data.get(f"amazon_note{suffix}", ""),
                })
        article = {
            "title": data["title"],
            "date": data["date"],
            "excerpt": data["excerpt"],
            "category": category,
            "slug": slug,
            "legacy_slug": path.stem,
            "url": f"articles/{slug}.html",
            "decade": data.get("decade", ""),
            "readtime": f"{read_minutes}分",
            "spoilers": data.get("spoilers", "false").lower() == "true",
            "amazon_url": data.get("amazon_url", ""),
            "amazon_label": data.get("amazon_label", "Amazonで見る"),
            "amazon_note": data.get("amazon_note", ""),
            "amazon_items": amazon_items,
            "content": body,
            "source": rel,
        }
        articles.append(article)
    articles.sort(key=lambda item: parse_date(item["date"]), reverse=True)
    return articles, notes


def load_anime() -> list[dict]:
    anime = json.loads(ANIME_DATA.read_text(encoding="utf-8"))
    required = {"id", "title", "year", "genres", "moods", "episodes", "minutes", "summary", "characters", "official_url"}
    ids: set[str] = set()
    for item in anime:
        missing = sorted(required - item.keys())
        if missing:
            raise SystemExit(f"anime {item.get('id', '?')}: missing {', '.join(missing)}")
        if item["id"] in ids:
            raise SystemExit(f"anime: duplicate id {item['id']}")
        ids.add(item["id"])
    return anime


def nav(current: str = "") -> str:
    links = [
        ("index", "ルーレット", "index.html#roulette"),
        ("catalog", "アニメ一覧", "index.html#catalog"),
        ("game", "3ヒント", "index.html#daily-game"),
        ("all", "読みもの", "all.html"),
    ]
    items = "".join(
        f'<a href="/{url}" class="{("is-active" if current == key else "")}">{label}</a>'
        for key, label, url in links
    )
    return f"""
<a class="skip-link" href="#main">本文へ移動</a>
<header class="site-header">
  <a class="brand" href="/index.html" aria-label="SEKAI LOG ホーム">
    <span class="brand-mark" aria-hidden="true">SL</span>
    <span><strong>SEKAI LOG</strong><small>きょう観るアニメ、ここで決めよ。</small></span>
  </a>
  <button class="menu-button" type="button" aria-expanded="false" aria-controls="site-nav">MENU</button>
  <nav class="site-nav" id="site-nav" aria-label="メインナビゲーション">{items}</nav>
</header>"""


def footer() -> str:
    return f"""
<footer class="site-footer">
  <div>
    <p class="footer-brand">SEKAI LOG</p>
    <p>観たいのに、決まらない。そんな夜のためのアニメくじ。</p>
  </div>
  <nav aria-label="フッターナビゲーション">
    <a href="/about.html">このサイトについて</a>
    <a href="/privacy.html">プライバシー・広告</a>
    <a href="/contact.html">お問い合わせ</a>
    <a href="/feed.xml">RSS</a>
  </nav>
  <p class="affiliate-disclosure">Amazonのアソシエイトとして、SEKAI LOGは適格販売により収入を得ています。</p>
  <p class="copyright">© 2026 {SITE_NAME} / {AUTHOR}</p>
</footer>"""


def analytics() -> str:
    return f"""<script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag('js',new Date());gtag('config','{GA_ID}',{{'anonymize_ip':true}});</script>"""


def page(
    title: str,
    description: str,
    body: str,
    *,
    current: str = "",
    canonical: str = "",
    page_type: str = "website",
    structured_data: dict | list | None = None,
    asset_version: str = "",
) -> str:
    canonical_url = canonical or SITE_URL + "/"
    schema = ""
    if structured_data:
        schema = '<script type="application/ld+json">' + json.dumps(
            structured_data, ensure_ascii=False, separators=(",", ":")
        ).replace("</", "<\\/") + "</script>"
    asset_suffix = f"?v={asset_version}" if asset_version else ""
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <meta name="description" content="{html.escape(description, quote=True)}">
  <link rel="canonical" href="{html.escape(canonical_url, quote=True)}">
  <link rel="alternate" type="application/rss+xml" title="SEKAI LOG RSS" href="{SITE_URL}/feed.xml">
  <meta property="og:site_name" content="SEKAI LOG">
  <meta property="og:type" content="{page_type}">
  <meta property="og:locale" content="ja_JP">
  <meta property="og:title" content="{html.escape(title, quote=True)}">
  <meta property="og:description" content="{html.escape(description, quote=True)}">
  <meta property="og:url" content="{html.escape(canonical_url, quote=True)}">
  <meta name="twitter:card" content="summary">
  <meta name="theme-color" content="#5b4bff">
  <link rel="stylesheet" href="/shared.css{asset_suffix}">
{schema}
{analytics()}
</head>
<body>
{nav(current)}
  <main id="main">{body}</main>
{footer()}
  <script src="/shared.js{asset_suffix}" defer></script>
</body>
</html>
"""


def card(article: dict, *, featured: bool = False) -> str:
    category = CATEGORIES[article["category"]][0]
    search_text = " ".join(
        (article["title"], article["excerpt"], category, article["content"])
    ).lower()
    classes = "story-card story-card--featured" if featured else "story-card"
    return f"""<article class="{classes}" data-search="{html.escape(search_text, quote=True)}">
  <a class="story-art art--{article['category']}" href="/{article['url']}" aria-label="{html.escape(article['title'], quote=True)}を読む">
    <span>{CATEGORIES[article['category']][1]}</span>
  </a>
  <div class="story-copy">
    <p class="eyebrow"><span>{category}</span><time datetime="{html.escape(article['date'], quote=True)}">{date_label(article['date'])}</time></p>
    <h2><a href="/{article['url']}">{html.escape(article['title'])}</a></h2>
    <p>{html.escape(article['excerpt'])}</p>
    <div class="story-meta"><span>読了 {article['readtime']}</span>{'<span>ネタバレあり</span>' if article['spoilers'] else ''}</div>
  </div>
</article>"""


def render_home(articles: list[dict], anime: list[dict]) -> str:
    anime_json = json.dumps(anime, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    latest = "".join(card(item) for item in articles[:3])
    body = f"""
<section class="pop-hero" id="discover">
  <div class="pop-hero-copy">
    <p class="pop-kicker"><span>NEW</span> アニメ選びに、くじ引きを。</p>
    <h1>今夜なに観る？<br><em>回して決めよ。</em></h1>
    <p>候補は{len(anime)}作品。条件を選んでも、ぜんぶ運任せでもOK。決まったら、観られる場所や公式サイトへすぐ飛べます。</p>
    <a class="jump-roulette" href="#roulette">さっそく回す <span>↓</span></a>
  </div>
  <div class="pop-hero-art" aria-hidden="true">
    <img src="/assets/sekai-log-hero.webp" alt="">
    <span class="hero-sticker hero-sticker--one">どれにする？</span>
    <span class="hero-sticker hero-sticker--two">{len(anime)}作品</span>
  </div>
</section>

<section class="roulette-playground" id="roulette">
  <header class="pop-section-heading"><div><span>01</span><h2>アニメルーレット</h2></div><p>迷ったら、押す。それだけ。</p></header>
  <div class="filter-bar" aria-label="ルーレットの条件">
    <label><span>ジャンル</span><select id="genre-filter"><option value="all">なんでも</option><option>ファンタジー</option><option>SF</option><option>青春</option><option>アクション</option><option>ミステリー</option><option>日常</option><option>スポーツ</option></select></label>
    <label><span>いまの気分</span><select id="mood-filter"><option value="all">おまかせ</option><option>熱くなりたい</option><option>笑いたい</option><option>泣きたい</option><option>考えたい</option><option>癒やされたい</option><option>ハラハラしたい</option></select></label>
    <label><span>使える時間</span><select id="time-filter"><option value="all">気にしない</option><option value="short">3時間まで</option><option value="medium">1日で見切る</option><option value="long">じっくり観る</option></select></label>
    <button class="clear-filters" id="clear-filters" type="button">条件をリセット</button>
  </div>
  <div class="roulette-layout">
    <div class="wheel-machine">
      <div class="wheel-pointer" aria-hidden="true"></div>
      <div class="roulette-wheel" id="roulette-wheel" aria-hidden="true"><div class="wheel-labels" id="wheel-labels"></div></div>
      <button class="spin-button" id="spin-button" type="button"><span>タップ！</span><strong>まわす</strong></button>
      <p class="selector-note" id="selector-note" aria-live="polite">いまは全作品が入っています。</p>
    </div>
    <article class="anime-result is-empty" id="anime-result" aria-live="polite">
      <div class="empty-result"><span>?</span><h3>ここに結果が出ます</h3><p>ホイール中央の「まわす」を押してください。</p></div>
    </article>
  </div>
</section>

<section class="catalog-section" id="catalog">
  <header class="pop-section-heading"><div><span>02</span><h2>自分で選ぶ</h2></div><p>くじじゃなく、ちゃんと探したい日はこちら。</p></header>
  <div class="catalog-tools">
    <label class="catalog-search"><span>検索</span><input id="anime-search" type="search" placeholder="作品名・キャラ名を入力" autocomplete="off"></label>
    <div class="catalog-chips" id="catalog-chips" aria-label="ジャンルで絞り込む"><button class="is-active" data-genre="all" type="button">すべて</button><button data-genre="ファンタジー" type="button">ファンタジー</button><button data-genre="SF" type="button">SF</button><button data-genre="青春" type="button">青春</button><button data-genre="アクション" type="button">アクション</button><button data-genre="ミステリー" type="button">ミステリー</button></div>
  </div>
  <div class="anime-grid" id="anime-grid"></div>
  <div class="catalog-end"><p id="catalog-status" aria-live="polite"></p><button id="show-more" class="outline-button" type="button">もっと見る ＋</button></div>
</section>

<section class="daily-game" id="daily-game">
  <div class="game-copy"><p class="game-label">毎日1問</p><h2>3ヒント<br>アニメ当て</h2><p>分かった時点で答えてOK。問題は毎日0時に入れ替わります。</p><div class="streak"><span>連続正解</span><b id="game-streak">0</b><small>日</small></div></div>
  <div class="game-board">
    <div class="hint-list" id="hint-list"></div>
    <div class="game-choices" id="game-choices"></div>
    <p class="game-message" id="game-message" aria-live="polite">どの作品でしょう？</p>
  </div>
</section>

<section class="reading-section">
  <header class="pop-section-heading"><div><span>03</span><h2>読みもの</h2></div><a href="/all.html">記事を全部見る →</a></header>
  <div class="story-grid story-grid--archive">{latest}</div>
</section>

<dialog class="anime-dialog" id="anime-dialog" aria-label="作品の詳細"><button class="dialog-close" id="dialog-close" type="button" aria-label="閉じる">×</button><div id="dialog-content"></div></dialog>
<noscript><p class="noscript-note">ルーレットと作品検索を使うにはJavaScriptを有効にしてください。<a href="/all.html">読みものはこちら</a></p></noscript>
<script id="anime-data" type="application/json">{anime_json}</script>"""
    schema = [
        {"@context": "https://schema.org", "@type": "WebSite", "name": SITE_NAME, "url": SITE_URL,
         "description": "気分と時間で絞って回せる、アニメルーレット。"},
        {"@context": "https://schema.org", "@type": "ItemList", "name": "SEKAI LOG アニメ作品図鑑",
         "numberOfItems": len(anime), "itemListElement": [
             {"@type": "ListItem", "position": index + 1, "name": item["title"], "url": item["official_url"]}
             for index, item in enumerate(anime)
         ]},
    ]
    return page(
        "SEKAI LOG — 今夜のアニメをルーレットで決めよう",
        "観るアニメが決まらない夜に。ジャンル・気分・時間で絞って回せる、無料のアニメルーレット。",
        body, current="index", canonical=SITE_URL + "/", structured_data=schema,
        asset_version="20260812-covers100",
    )


def render_archive(articles: list[dict], category: str | None = None) -> str:
    selected = [a for a in articles if not category or a["category"] == category]
    if category:
        label, english, description = CATEGORIES[category]
        title = f"{label}の記事 — SEKAI LOG"
        current = category
    else:
        label, english, description = "読みもの", "READING LOG", "見終わったあとに考えたい作品の評論を、新しい順に掲載しています。"
        title = "読みもの — SEKAI LOG"
        current = "all"
    cards = "".join(card(item) for item in selected)
    body = f"""
<section class="page-title">
  <p>{english}</p><h1>{label}</h1><div><span>{len(selected):02d} STORIES</span><p>{description}</p></div>
</section>
<section class="archive-wrap">
  <label class="filter-box"><span>記事を絞り込む</span><input id="article-filter" type="search" placeholder="作品名・キーワード" autocomplete="off"></label>
  <p class="filter-status" id="filter-status" aria-live="polite">{len(selected)}件の記事</p>
  <div class="story-grid story-grid--archive" id="article-list">{cards}</div>
  <p class="empty-state" id="empty-state" hidden>該当する記事はありません。</p>
</section>"""
    return page(title, description, body, current=current, canonical=f"{SITE_URL}/{'all' if not category else category}.html")


def render_article(article: dict, all_articles: list[dict]) -> str:
    body_html, toc = markdown_to_html(article["content"])
    category_label = CATEGORIES[article["category"]][0]
    canonical = f"{SITE_URL}/{article['url']}"
    toc_html = ""
    if len(toc) >= 2:
        toc_html = '<nav class="toc" aria-label="目次"><p>この記事の内容</p><ol>' + "".join(
            f'<li><a href="#{section}">{html.escape(label)}</a></li>' for section, label in toc
        ) + "</ol></nav>"
    affiliate = "\n".join(
        f"""<aside class="product-card">
  <p>RELATED ITEM / 広告</p><h2>{html.escape(item['note'] or article['title'])}</h2>
  <a href="{safe_url(item['url'])}" rel="nofollow sponsored noopener" target="_blank">{html.escape(item['label'])} →</a>
</aside>"""
        for item in article["amazon_items"]
    )
    related = [
        a for a in all_articles
        if a["slug"] != article["slug"] and a["category"] == article["category"]
    ][:3]
    if len(related) < 3:
        related += [a for a in all_articles if a["slug"] != article["slug"] and a not in related][: 3 - len(related)]
    related_html = "".join(card(item) for item in related)
    spoiler = '<span class="spoiler-badge">ネタバレあり</span>' if article["spoilers"] else ""
    body = f"""
<article class="article-page">
  <header class="article-header">
    <nav class="breadcrumb" aria-label="パンくず"><a href="/index.html">ホーム</a><span>/</span><a href="/{article['category']}.html">{category_label}</a></nav>
    <p class="eyebrow"><span>{category_label}</span><time datetime="{html.escape(article['date'], quote=True)}">{date_label(article['date'])}</time></p>
    <h1>{html.escape(article['title'])}</h1>
    <p class="article-deck">{html.escape(article['excerpt'])}</p>
    <div class="article-byline"><span>TEXT BY {AUTHOR}</span><span>読了 {article['readtime']}</span>{spoiler}</div>
  </header>
  <div class="article-art art--{article['category']}" aria-hidden="true"><span>{CATEGORIES[article['category']][1]}</span><b>SEKAI<br>LOG</b></div>
  <div class="article-layout">
    <aside class="article-side"><span>ESSAY / {date_label(article['date'])}</span><p>この記事は作品全体の内容に触れています。</p></aside>
    <div class="article-content">{toc_html}{body_html}{affiliate}
      <div class="article-end"><span>END</span><p>最後までお読みいただき、ありがとうございます。</p></div>
    </div>
  </div>
</article>
<section class="related-wrap"><header class="section-heading"><div><p>KEEP READING</p><h2>次に読む記事</h2></div></header><div class="story-grid">{related_html}</div></section>"""
    published = parse_date(article["date"]).date().isoformat()
    schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": article["title"],
        "description": article["excerpt"],
        "datePublished": published,
        "dateModified": published,
        "inLanguage": "ja",
        "mainEntityOfPage": canonical,
        "author": {"@type": "Person", "name": AUTHOR},
        "publisher": {"@type": "Organization", "name": SITE_NAME},
    }
    return page(
        f"{article['title']} — SEKAI LOG",
        article["excerpt"], body, current=article["category"], canonical=canonical,
        page_type="article", structured_data=schema,
    )


def render_about() -> str:
    body = """
<section class="page-title"><p>ABOUT</p><h1>このサイトについて</h1><div><span>ANIME DISCOVERY PLAYGROUND</span><p>次に見る一本を、迷う時間ごと楽しくする。</p></div></section>
<div class="prose-page">
  <section><p class="eyebrow"><span>PROFILE</span></p><h2>藤乃宮 遊</h2><p>関西在住。2011年ごろからアニメやライトノベルを追い、SF・ファンタジーを中心に作品を見てきました。設定の整理だけではなく、作品が人間や社会をどう捉えているかを考えるのが好きです。</p></section>
  <section><p class="eyebrow"><span>WHY SEKAI LOG</span></p><h2>選べない夜を、遊べる時間に。</h2><p>配信サービスを開いても、候補を眺めるだけで時間が過ぎる。SEKAI LOGは、気分・ジャンル・使える時間から候補を絞り、ルーレットで最後の一押しをする場所です。決まったあとは公式情報、視聴先、原作へすぐ進めます。</p></section>
  <section><p class="eyebrow"><span>DATA POLICY</span></p><h2>短く、確かに、行動できる情報を。</h2><ul><li>あらすじと人物紹介は核心のネタバレを避け、独自の文章で要約します。</li><li>作品情報は公式サイトを優先し、配信状況は外部サービスの最新表示で確認できる導線を設けます。</li><li>作品ビジュアルは識別と紹介のために縮小表示し、画像ごとに出典ページへリンクします。画像は外部配信元から表示し、当サイトでは複製・加工しません。</li><li>商品リンクには広告であることを明示し、Amazonアソシエイトの規約に沿って掲載します。</li></ul><p>基本情報と画像URLの照合には、<a href="https://github.com/manami-project/anime-offline-database" target="_blank" rel="noopener">manami-project「anime-offline-database」</a>（ODbL 1.0 / DbCL 1.0）を利用しています。各画像の権利はそれぞれの権利者に帰属します。</p></section>
  <section><p class="eyebrow"><span>WHAT REMAINS</span></p><h2>評論記事は「見たあと」の場所へ。</h2><p>これまで公開した評論は削除せず、読みものとして残しています。作品を選ぶ場所と、見終わった作品を考える場所。その両方を一つのサイトでつなぎます。</p></section>
</div>"""
    return page("このサイトについて — SEKAI LOG", "次に見るアニメを選ぶSEKAI LOGの使い方と、運営者・藤乃宮遊の情報方針。", body, current="about", canonical=SITE_URL + "/about.html")


def render_privacy() -> str:
    body = """
<section class="page-title"><p>PRIVACY &amp; ADVERTISING</p><h1>プライバシー・広告</h1><div><span>UPDATED 2026.08.12</span><p>アクセス解析、広告、著作権に関する方針です。</p></div></section>
<div class="prose-page legal">
  <section><h2>アクセス解析</h2><p>当サイトは、閲覧状況を把握し改善するためGoogle Analyticsを利用しています。Google AnalyticsはCookie等を用いて閲覧情報を収集します。収集される情報や利用方法については、Googleのプライバシーポリシーをご確認ください。ブラウザの設定やGoogleのオプトアウト機能により収集を制限できます。</p></section>
  <section><h2>Amazonアソシエイト</h2><p>Amazonのアソシエイトとして、SEKAI LOGは適格販売により収入を得ています。商品リンクには「広告」または同等の表示を付けます。リンク先の商品価格・在庫・販売条件は変更される場合があり、購入時にはAmazon.co.jpの表示が適用されます。</p></section>
  <section><h2>個人情報</h2><p>お問い合わせのために利用者がメールで送信した氏名、メールアドレス、本文は、返信と必要な連絡のためにのみ利用します。法令に基づく場合を除き、本人の同意なく第三者へ提供しません。</p></section>
  <section><h2>免責事項</h2><p>正確な情報を掲載するよう努めますが、内容の完全性や最新性を保証するものではありません。当サイトまたはリンク先の利用によって生じた損害について、運営者は責任を負いかねます。</p></section>
  <section><h2>著作権・画像出典</h2><p>記事本文の著作権は運営者に帰属します。作品名、画像、企業名などの権利は各権利者に帰属します。作品ビジュアルは作品の識別と紹介を目的に縮小表示し、各画像上の出典リンクから掲載元を確認できるようにしています。当サイトのサーバーでは画像を複製・加工していません。権利上の問題や削除・差し替えのご要望は、お問い合わせページからご連絡ください。</p><p>作品の基本情報と画像URLの照合には、<a href="https://github.com/manami-project/anime-offline-database" target="_blank" rel="noopener">manami-project「anime-offline-database」</a>（Open Database License 1.0 / Database Contents License 1.0）を利用しています。</p></section>
  <section><h2>方針の変更</h2><p>利用サービスや法令の変更に応じ、本ページを更新することがあります。重要な変更は本ページ上で告知します。</p></section>
</div>"""
    return page("プライバシー・広告 — SEKAI LOG", "SEKAI LOGのプライバシー、アクセス解析、Amazonアソシエイト、著作権に関する方針。", body, canonical=SITE_URL + "/privacy.html")


def render_contact() -> str:
    body = """
<section class="page-title"><p>CONTACT</p><h1>お問い合わせ</h1><div><span>MAIL</span><p>記事の訂正、感想、執筆に関するご連絡はこちらから。</p></div></section>
<div class="contact-page"><p>メールソフトを開き、必要事項をご記入ください。営業目的の一斉送信には返信しない場合があります。</p><a class="primary-button" href="mailto:contact@sekai-log.com?subject=SEKAI%20LOG%E3%81%B8%E3%81%AE%E3%81%8A%E5%95%8F%E3%81%84%E5%90%88%E3%82%8F%E3%81%9B">contact@sekai-log.com</a></div>"""
    return page("お問い合わせ — SEKAI LOG", "SEKAI LOGへのお問い合わせ。記事の訂正、感想、執筆に関するご連絡はこちら。", body, canonical=SITE_URL + "/contact.html")


def render_legacy_article() -> str:
    return """<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex"><title>記事を移動しています — SEKAI LOG</title><link rel="stylesheet" href="/shared.css"></head><body><main class="redirect-page"><p>記事を移動しています。</p><a href="/all.html">記事一覧へ</a></main><script>
(async()=>{const p=new URLSearchParams(location.search),slug=p.get('slug');if(!slug)return;try{const all=await fetch('/articles.json').then(r=>r.json());const a=all.find(x=>x.slug===slug||x.legacy_slug===slug);if(a)location.replace('/'+a.url)}catch(e){console.error(e)}})();
</script></body></html>"""


def build_feed(articles: list[dict]) -> str:
    items = []
    for article in articles[:20]:
        url = f"{SITE_URL}/{article['url']}"
        published = format_datetime(parse_date(article["date"]))
        items.append(f"""<item><title>{html.escape(article['title'])}</title><link>{url}</link><guid>{url}</guid><pubDate>{published}</pubDate><description>{html.escape(article['excerpt'])}</description></item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>SEKAI LOG 読みもの</title><link>{SITE_URL}</link><description>アニメを見終わったあとに読む評論とコラム</description><language>ja</language>{''.join(items)}</channel></rss>"""


def build_sitemap(articles: list[dict]) -> str:
    paths = ["", "all.html", *[f"{key}.html" for key in CATEGORIES], "about.html", "privacy.html", "contact.html"]
    urls = [f"<url><loc>{SITE_URL}/{path}</loc></url>" for path in paths]
    urls += [f"<url><loc>{SITE_URL}/{a['url']}</loc><lastmod>{parse_date(a['date']).date().isoformat()}</lastmod></url>" for a in articles]
    return '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(urls) + "</urlset>"


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"WRITE {path.relative_to(ROOT)}")


def main() -> None:
    articles, notes = load_articles()
    anime = load_anime()
    if not articles:
        raise SystemExit("No published articles")
    if ARTICLE_DIR.exists():
        shutil.rmtree(ARTICLE_DIR)
    ARTICLE_DIR.mkdir()

    write(ROOT / "index.html", render_home(articles, anime))
    write(ROOT / "all.html", render_archive(articles))
    for category in CATEGORIES:
        write(ROOT / f"{category}.html", render_archive(articles, category))
    for article in articles:
        write(ROOT / article["url"], render_article(article, articles))
    write(ROOT / "about.html", render_about())
    write(ROOT / "privacy.html", render_privacy())
    write(ROOT / "contact.html", render_contact())
    write(ROOT / "search.html", render_archive(articles))
    write(ROOT / "article.html", render_legacy_article())
    public_index = [{key: value for key, value in a.items() if key not in {"source"}} for a in articles]
    write(ROOT / "articles.json", json.dumps(public_index, ensure_ascii=False, indent=2))
    write(ROOT / "feed.xml", build_feed(articles))
    write(ROOT / "sitemap.xml", build_sitemap(articles))
    write(ROOT / "robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")
    print(f"\nPublished: {len(articles)} articles / {len(anime)} anime / Drafts: {len(notes)}")
    for note in notes:
        print(note)


if __name__ == "__main__":
    main()
