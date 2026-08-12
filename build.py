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


def nav(current: str = "") -> str:
    links = [("index", "ホーム", "index.html"), ("all", "記事一覧", "all.html")]
    links += [(key, value[0], f"{key}.html") for key, value in CATEGORIES.items()]
    items = "".join(
        f'<a href="/{url}" class="{("is-active" if current == key else "")}">{label}</a>'
        for key, label, url in links
    )
    return f"""
<a class="skip-link" href="#main">本文へ移動</a>
<header class="site-header">
  <a class="brand" href="/index.html" aria-label="SEKAI LOG ホーム">
    <span class="brand-mark" aria-hidden="true">SL</span>
    <span><strong>SEKAI LOG</strong><small>FICTION &amp; CULTURE REVIEW</small></span>
  </a>
  <button class="menu-button" type="button" aria-expanded="false" aria-controls="site-nav">MENU</button>
  <nav class="site-nav" id="site-nav" aria-label="メインナビゲーション">{items}</nav>
</header>"""


def footer() -> str:
    return f"""
<footer class="site-footer">
  <div>
    <p class="footer-brand">SEKAI LOG</p>
    <p>アニメ・小説・SFを、見終えた後からもう一度考える個人批評誌。</p>
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
) -> str:
    canonical_url = canonical or SITE_URL + "/"
    schema = ""
    if structured_data:
        schema = '<script type="application/ld+json">' + json.dumps(
            structured_data, ensure_ascii=False, separators=(",", ":")
        ).replace("</", "<\\/") + "</script>"
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
  <meta name="theme-color" content="#f5f1e8">
  <link rel="stylesheet" href="/shared.css">
{schema}
{analytics()}
</head>
<body>
{nav(current)}
  <main id="main">{body}</main>
{footer()}
  <script src="/shared.js" defer></script>
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


def render_home(articles: list[dict]) -> str:
    feature = articles[0]
    rest = "".join(card(item) for item in articles[1:5])
    counts = "".join(
        f'<a href="/{key}.html"><strong>{label[0]}</strong><span>{sum(a["category"] == key for a in articles):02d}</span></a>'
        for key, label in CATEGORIES.items()
    )
    body = f"""
<section class="home-hero">
  <div class="hero-kicker">PERSONAL REVIEW JOURNAL / KANSAI</div>
  <div class="hero-grid">
    <div>
      <p class="hero-index">ISSUE 001 — 2026</p>
      <h1>好きだった作品を、<br><em>考えた言葉</em>で残す。</h1>
      <p class="hero-lead">アニメ、SF、小説、サブカルチャー。あらすじではなく、見終えたあとに残る問いを記録する個人批評誌です。</p>
      <a class="text-link" href="/all.html">すべての記事を読む <span>→</span></a>
    </div>
    <aside class="hero-note"><span>EDITOR'S NOTE</span><p>結論を急がず、作品のどこに心が止まったのかを言葉にする。SEKAI LOGを、そのための静かな読書室に作り直しました。</p></aside>
  </div>
</section>
<section class="home-section">
  <header class="section-heading"><div><p>FEATURED</p><h2>まず読んでほしい一本</h2></div><span>01</span></header>
  {card(feature, featured=True)}
</section>
<section class="home-section">
  <header class="section-heading"><div><p>LATEST STORIES</p><h2>新着の記事</h2></div><a href="/all.html">一覧を見る →</a></header>
  <div class="story-grid">{rest}</div>
</section>
<section class="category-strip" aria-label="カテゴリ一覧">{counts}</section>
<section class="home-section manifesto">
  <p class="eyebrow"><span>OUR APPROACH</span></p>
  <h2>作品紹介で終わらず、<br>「なぜ残ったか」まで書く。</h2>
  <div><p>公式情報と個人の解釈を分け、事実に根拠のない断定は避けます。ネタバレは明示し、関連商品を紹介する場合は広告であることを表示します。</p><a class="text-link" href="/about.html">編集方針を読む <span>→</span></a></div>
</section>"""
    return page(
        "SEKAI LOG — アニメ・SF・小説の個人批評誌",
        "アニメ、SF、小説、サブカルチャーを、作品に残る問いから読み解く個人批評サイト。",
        body,
        current="index",
        canonical=SITE_URL + "/",
        structured_data={"@context": "https://schema.org", "@type": "WebSite", "name": SITE_NAME, "url": SITE_URL},
    )


def render_archive(articles: list[dict], category: str | None = None) -> str:
    selected = [a for a in articles if not category or a["category"] == category]
    if category:
        label, english, description = CATEGORIES[category]
        title = f"{label}の記事 — SEKAI LOG"
        current = category
    else:
        label, english, description = "記事一覧", "ALL STORIES", "公開中の記事を新しい順に掲載しています。"
        title = "記事一覧 — SEKAI LOG"
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
<section class="page-title"><p>ABOUT</p><h1>このサイトについて</h1><div><span>PERSONAL REVIEW JOURNAL</span><p>記憶を、考えた言葉として残す。</p></div></section>
<div class="prose-page">
  <section><p class="eyebrow"><span>PROFILE</span></p><h2>藤乃宮 遊</h2><p>関西在住。2011年ごろからアニメやライトノベルを追い、SF・ファンタジーを中心に作品を見てきました。設定の整理だけではなく、作品が人間や社会をどう捉えているかを考えるのが好きです。</p></section>
  <section><p class="eyebrow"><span>WHY SEKAI LOG</span></p><h2>好きだった理由を、忘れないために。</h2><p>見た作品の数が増えるほど、強く心を動かされた瞬間まで輪郭を失っていきます。SEKAI LOGは、感想を消費して次へ進むのではなく、「なぜ残ったのか」を立ち止まって書くための場所です。</p></section>
  <section><p class="eyebrow"><span>EDITORIAL POLICY</span></p><h2>事実と解釈を分けて書く。</h2><ul><li>公式情報や確認できる記録と、筆者個人の解釈を区別します。</li><li>作品の核心に触れる記事には、ネタバレ表示を付けます。</li><li>誤りが分かった場合は、内容を確認して修正します。</li><li>商品リンクには広告であることを明示し、作品と関係のない商品は勧めません。</li></ul></section>
  <section><p class="eyebrow"><span>FAVORITES</span></p><h2>よく読む・見る領域</h2><div class="tag-cloud"><span>SF</span><span>ファンタジー</span><span>ライトノベル</span><span>アニメーション</span><span>作品構造</span><span>メディア史</span></div></section>
</div>"""
    return page("このサイトについて — SEKAI LOG", "SEKAI LOGと運営者・藤乃宮遊のプロフィール、編集方針。", body, current="about", canonical=SITE_URL + "/about.html")


def render_privacy() -> str:
    body = """
<section class="page-title"><p>PRIVACY &amp; ADVERTISING</p><h1>プライバシー・広告</h1><div><span>UPDATED 2026.08.04</span><p>アクセス解析、広告、著作権に関する方針です。</p></div></section>
<div class="prose-page legal">
  <section><h2>アクセス解析</h2><p>当サイトは、閲覧状況を把握し改善するためGoogle Analyticsを利用しています。Google AnalyticsはCookie等を用いて閲覧情報を収集します。収集される情報や利用方法については、Googleのプライバシーポリシーをご確認ください。ブラウザの設定やGoogleのオプトアウト機能により収集を制限できます。</p></section>
  <section><h2>Amazonアソシエイト</h2><p>Amazonのアソシエイトとして、SEKAI LOGは適格販売により収入を得ています。商品リンクには「広告」または同等の表示を付けます。リンク先の商品価格・在庫・販売条件は変更される場合があり、購入時にはAmazon.co.jpの表示が適用されます。</p></section>
  <section><h2>個人情報</h2><p>お問い合わせのために利用者がメールで送信した氏名、メールアドレス、本文は、返信と必要な連絡のためにのみ利用します。法令に基づく場合を除き、本人の同意なく第三者へ提供しません。</p></section>
  <section><h2>免責事項</h2><p>正確な情報を掲載するよう努めますが、内容の完全性や最新性を保証するものではありません。当サイトまたはリンク先の利用によって生じた損害について、運営者は責任を負いかねます。</p></section>
  <section><h2>著作権・引用</h2><p>記事本文の著作権は運営者に帰属します。作品名、企業名などの権利は各権利者に帰属します。批評に必要な引用を行う場合は、引用部分と本文を区別し、出典を示します。権利上の問題がある場合はお問い合わせください。</p></section>
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
    return f"""<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>SEKAI LOG</title><link>{SITE_URL}</link><description>アニメ・SF・小説の個人批評誌</description><language>ja</language>{''.join(items)}</channel></rss>"""


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
    if not articles:
        raise SystemExit("No published articles")
    if ARTICLE_DIR.exists():
        shutil.rmtree(ARTICLE_DIR)
    ARTICLE_DIR.mkdir()

    write(ROOT / "index.html", render_home(articles))
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
    print(f"\nPublished: {len(articles)} / Drafts: {len(notes)}")
    for note in notes:
        print(note)


if __name__ == "__main__":
    main()
