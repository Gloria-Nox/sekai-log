#!/usr/bin/env python3
"""Manage SEKAI LOG's canonical SQLite anime catalog."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import unicodedata
from pathlib import Path
from urllib.parse import quote_plus


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "anime.sqlite3"
ASSOCIATE_TAG = "sekailog-22"

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS catalog_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS anime (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  reading TEXT NOT NULL DEFAULT '',
  year INTEGER NOT NULL CHECK (year BETWEEN 1910 AND 2100),
  episodes INTEGER NOT NULL CHECK (episodes > 0),
  minutes INTEGER NOT NULL CHECK (minutes > 0),
  format TEXT NOT NULL,
  accent TEXT NOT NULL DEFAULT '#8bd3c7',
  glyph TEXT NOT NULL DEFAULT '',
  summary TEXT NOT NULL DEFAULT '',
  hint TEXT NOT NULL DEFAULT '',
  image_url TEXT NOT NULL DEFAULT '',
  image_thumb TEXT NOT NULL DEFAULT '',
  image_credit TEXT NOT NULL DEFAULT '',
  image_source_url TEXT NOT NULL DEFAULT '',
  curation_level TEXT NOT NULL DEFAULT 'basic' CHECK (curation_level IN ('full', 'basic')),
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
  sort_order INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS anime_genre (
  anime_id TEXT NOT NULL REFERENCES anime(id) ON DELETE CASCADE,
  position INTEGER NOT NULL,
  name TEXT NOT NULL,
  PRIMARY KEY (anime_id, position)
);
CREATE TABLE IF NOT EXISTS anime_mood (
  anime_id TEXT NOT NULL REFERENCES anime(id) ON DELETE CASCADE,
  position INTEGER NOT NULL,
  name TEXT NOT NULL,
  PRIMARY KEY (anime_id, position)
);
CREATE TABLE IF NOT EXISTS anime_character (
  anime_id TEXT NOT NULL REFERENCES anime(id) ON DELETE CASCADE,
  position INTEGER NOT NULL,
  name TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT '',
  PRIMARY KEY (anime_id, position)
);
CREATE TABLE IF NOT EXISTS anime_link (
  anime_id TEXT NOT NULL REFERENCES anime(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,
  provider TEXT NOT NULL,
  label TEXT NOT NULL,
  url TEXT NOT NULL,
  is_affiliate INTEGER NOT NULL DEFAULT 0 CHECK (is_affiliate IN (0, 1)),
  position INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (anime_id, kind, provider)
);
CREATE INDEX IF NOT EXISTS idx_anime_enabled_sort ON anime(enabled, sort_order);
CREATE INDEX IF NOT EXISTS idx_anime_genre_name ON anime_genre(name);
CREATE INDEX IF NOT EXISTS idx_anime_mood_name ON anime_mood(name);
"""

TAG_TO_GENRE = {
    "action": "アクション", "adventure": "冒険", "comedy": "コメディ",
    "drama": "ドラマ", "fantasy": "ファンタジー", "romance": "恋愛",
    "science fiction": "SF", "sci fi": "SF", "cyberpunk": "SF",
    "mystery": "ミステリー", "horror": "ホラー", "thriller": "サスペンス",
    "sports": "スポーツ", "music": "音楽", "band": "音楽",
    "slice of life": "日常", "iyashikei": "日常", "historical": "歴史",
    "mecha": "ロボット", "military": "ミリタリー", "supernatural": "伝奇",
    "school": "学園", "coming of age": "青春", "family": "家族",
}

GENRE_TO_MOOD = {
    "コメディ": "笑いたい", "日常": "癒やされたい", "恋愛": "ときめきたい",
    "アクション": "熱くなりたい", "スポーツ": "熱くなりたい", "ホラー": "怖がりたい",
    "サスペンス": "ハラハラしたい", "ミステリー": "考えたい", "SF": "考えたい",
    "ドラマ": "泣きたい", "音楽": "元気になりたい", "冒険": "ワクワクしたい",
}

EXCLUDED_TAGS = {
    "adult audience only", "hentai", "ecchi", "kids", "kodomo", "advertisement",
    "promotional", "music video", "shorts", "chinese animation", "korean animation",
    "anime influenced",
}

SEQUEL_PATTERN = re.compile(
    r"(?:season|part|cour|chapter|arc|movie|film|ova|special|recap|compilation|"
    r"\b[2-9](?:nd|rd|th)?\b|\bii+\b|\biii+\b|第[2-9]|続編|総集編|劇場版)", re.I
)
SEQUEL_DISPLAY_PATTERN = re.compile(
    r"(?:第[2-9]|[2-9]期|[2-9]クール|続編|総集編|外伝|完結|新シリーズ|新たなる翼|"
    r"(?:編|篇)(?:\s|$)|第二幕|二学期|夏の大会編|女子高編|神覚者候補選抜試験編|"
    r"the final|after story|new challenger|to the top|stone wars|new world|"
    r"fourth stage|fifth stage|second stage|final stage|re:re|prelude|refrain|revenge|"
    r"second beat|gran de road|last evolution|dead apple|memorial edition)", re.I
)


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db


def amazon_product_url(item: dict) -> str:
    if item.get("amazon_asin"):
        return f"https://www.amazon.co.jp/dp/{quote_plus(item['amazon_asin'])}?tag={ASSOCIATE_TAG}"
    query = item.get("amazon_query") or f"{item['title']} 原作 1"
    return f"https://www.amazon.co.jp/s?k={quote_plus(query)}&tag={ASSOCIATE_TAG}"


def prime_video_url(title: str) -> str:
    return f"https://www.amazon.co.jp/s?k={quote_plus(title)}&i=instant-video&tag={ASSOCIATE_TAG}"


def justwatch_url(title: str) -> str:
    return f"https://www.justwatch.com/jp/検索?q={quote_plus(title)}"


def upsert_record(db: sqlite3.Connection, item: dict, order: int, level: str) -> None:
    db.execute(
        """INSERT INTO anime (
          id,title,reading,year,episodes,minutes,format,accent,glyph,summary,hint,
          image_url,image_thumb,image_credit,image_source_url,curation_level,sort_order
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET
          title=excluded.title, reading=excluded.reading, year=excluded.year,
          episodes=excluded.episodes, minutes=excluded.minutes, format=excluded.format,
          accent=excluded.accent, glyph=excluded.glyph, summary=excluded.summary,
          hint=excluded.hint, image_url=excluded.image_url, image_thumb=excluded.image_thumb,
          image_credit=excluded.image_credit, image_source_url=excluded.image_source_url,
          curation_level=excluded.curation_level, sort_order=excluded.sort_order""",
        (
            item["id"], item["title"], item.get("reading", ""), int(item["year"]),
            max(1, int(item["episodes"])), max(1, int(item["minutes"])), item.get("format", "TVシリーズ"),
            item.get("accent", "#8bd3c7"), item.get("glyph", ""), item.get("summary", ""),
            item.get("hint", ""), item.get("image_url", ""), item.get("image_thumb", ""),
            item.get("image_credit", ""), item.get("image_source_url", ""), level, order,
        ),
    )
    for table in ("anime_genre", "anime_mood", "anime_character", "anime_link"):
        db.execute(f"DELETE FROM {table} WHERE anime_id=?", (item["id"],))
    for position, genre in enumerate(item.get("genres", [])):
        db.execute("INSERT INTO anime_genre VALUES (?,?,?)", (item["id"], position, genre))
    for position, mood in enumerate(item.get("moods", [])):
        db.execute("INSERT INTO anime_mood VALUES (?,?,?)", (item["id"], position, mood))
    for position, person in enumerate(item.get("characters", [])):
        db.execute(
            "INSERT INTO anime_character VALUES (?,?,?,?)",
            (item["id"], position, person.get("name", ""), person.get("role", "")),
        )
    links = []
    if item.get("official_url"):
        links.append(("official", "official", "公式サイト", item["official_url"], 0, 0))
    source_url = item.get("source_record_url") or item.get("image_source_url")
    if source_url:
        links.append(("source", item.get("image_credit", "database"), "作品データ", source_url, 0, 1))
    links.extend([
        ("watch", "JustWatch", "配信先を調べる", justwatch_url(item["title"]), 0, 0),
        ("watch", "Amazon Prime Video", "Prime Videoで探す", prime_video_url(item["title"]), 1, 1),
        ("commerce", "Amazon", "原作・関連商品", amazon_product_url(item), 1, 0),
    ])
    db.executemany(
        "INSERT INTO anime_link (anime_id,kind,provider,label,url,is_affiliate,position) VALUES (?,?,?,?,?,?,?)",
        [(item["id"], *link) for link in links],
    )


def import_json(db: sqlite3.Connection, path: Path) -> None:
    records = json.loads(path.read_text(encoding="utf-8"))
    for order, item in enumerate(records):
        upsert_record(db, item, order, "full")
    db.execute("INSERT OR REPLACE INTO catalog_meta VALUES ('original_catalog', ?)", (str(path.name),))
    db.execute("INSERT OR REPLACE INTO catalog_meta VALUES ('associate_tag', ?)", (ASSOCIATE_TAG,))
    db.commit()


def normal(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).lower()
    return re.sub(r"[^a-z0-9ぁ-んァ-ヶ一-龠]", "", value)


def preferred_title(record: dict) -> str:
    kana = re.compile(r"[ぁ-んァ-ヶ]")
    kanji = re.compile(r"[一-龠]")
    katakana = re.compile(r"[ァ-ヶ]")
    choices = [s.strip() for s in record.get("synonyms", []) if kana.search(s) and 2 <= len(s.strip()) <= 38]
    if choices:
        non_abbreviated = [s for s in choices if len(s) >= 5]
        choices = non_abbreviated or choices
        def title_score(value: str) -> tuple[int, int, str]:
            score = min(len(value), 28)
            score += 18 if kanji.search(value) else 0
            score += 6 if katakana.search(value) else 0
            score -= 20 if re.fullmatch(r"[ぁ-んー・\s]+", value) else 0
            score -= 30 if SEQUEL_DISPLAY_PATTERN.search(value) else 0
            score -= max(0, len(value) - 32) * 2
            return score, -len(value), value
        return unicodedata.normalize("NFC", max(choices, key=title_score))
    return unicodedata.normalize("NFC", record.get("title", "").strip())


def slug_for(record: dict) -> str:
    for source in record.get("sources", []):
        match = re.search(r"myanimelist\.net/anime/(\d+)", source)
        if match:
            return f"mal-{match.group(1)}"
    raw = normal(record.get("title", ""))[:48]
    return f"catalog-{raw or abs(hash(record.get('title', 'anime')))}"


def map_genres(tags: list[str]) -> list[str]:
    genres = []
    for tag in tags:
        genre = TAG_TO_GENRE.get(tag.lower())
        if genre and genre not in genres:
            genres.append(genre)
    return genres[:3] or ["ドラマ"]


def map_moods(genres: list[str]) -> list[str]:
    moods = []
    for genre in genres:
        mood = GENRE_TO_MOOD.get(genre)
        if mood and mood not in moods:
            moods.append(mood)
    return moods[:3] or ["考えたい"]


def source_url(record: dict) -> str:
    for provider in ("myanimelist.net", "anilist.co", "anime-planet.com", "animenewsnetwork.com"):
        for source in record.get("sources", []):
            if provider in source:
                return source
    return (record.get("sources") or [""])[0]


def minutes_for(record: dict) -> int:
    duration = record.get("duration") or {}
    value = int(duration.get("value") or 0)
    unit = duration.get("unit")
    if unit == "SECONDS":
        return max(1, round(value / 60))
    if unit == "MINUTES":
        return max(1, value)
    return 24 if record.get("type") in {"TV", "ONA"} else 100


def expansion_candidate(record: dict, existing: set[str]) -> bool:
    year = (record.get("animeSeason") or {}).get("year")
    score = (record.get("score") or {}).get("arithmeticGeometricMean") or 0
    tags = {tag.lower() for tag in record.get("tags", [])}
    sources = record.get("sources", [])
    title = record.get("title", "")
    if not year or year < 1970 or year > 2026 or score < 7.45:
        return False
    if record.get("type") not in {"TV", "MOVIE", "ONA"}:
        return False
    if not record.get("episodes") or record["episodes"] > 250:
        return False
    if not any("myanimelist.net/anime/" in url for url in sources):
        return False
    display = preferred_title(record)
    if tags & EXCLUDED_TAGS or SEQUEL_PATTERN.search(title) or SEQUEL_DISPLAY_PATTERN.search(display):
        return False
    if not display or normal(display) in existing or normal(title) in existing:
        return False
    return True


def expand_offline(db: sqlite3.Connection, path: Path, target: int) -> None:
    root = json.loads(path.read_text(encoding="utf-8"))
    records = root.get("data", root)
    rows = db.execute("SELECT id,title,reading,sort_order FROM anime ORDER BY sort_order").fetchall()
    existing = {normal(row["title"]) for row in rows} | {normal(row["reading"]) for row in rows}
    source_index = {source: record for record in records for source in record.get("sources", [])}
    selected_sources: set[str] = set()
    selected_network: set[str] = set()
    existing_source_urls = [row[0] for row in db.execute("SELECT url FROM anime_link WHERE kind='source'")]
    for source in existing_source_urls:
        record = source_index.get(source)
        if not record:
            continue
        selected_sources.update(record.get("sources", []))
        selected_network.update(record.get("sources", []))
        selected_network.update(record.get("relatedAnime", []))
    current = len(rows)
    scored = []
    for record in records:
        if expansion_candidate(record, existing):
            score = (record.get("score") or {}).get("arithmeticGeometricMean") or 0
            scored.append((score, record))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    palette = ["#8bd3c7", "#ff85b3", "#62b8ff", "#f4b860", "#b89cff", "#84d66b"]
    added = 0
    for _, record in scored:
        if current + added >= target:
            break
        title = preferred_title(record)
        key = normal(title)
        if key in existing:
            continue
        record_sources = set(record.get("sources", []))
        record_related = set(record.get("relatedAnime", []))
        if record_sources & selected_network or record_related & selected_sources:
            continue
        year = int((record.get("animeSeason") or {}).get("year"))
        episodes = int(record.get("episodes") or 1)
        genres = map_genres(record.get("tags", []))
        item = {
            "id": slug_for(record), "title": title, "reading": record.get("title", ""),
            "year": year, "episodes": episodes, "minutes": minutes_for(record),
            "format": "映画" if record.get("type") == "MOVIE" else "TVシリーズ",
            "accent": palette[(current + added) % len(palette)], "glyph": "",
            "genres": genres, "moods": map_moods(genres),
            "summary": f"{year}年に放送・公開された{genres[0]}作品。全{episodes}話。",
            "characters": [], "hint": f"{year}年の{genres[0]}作品。",
            "official_url": "", "amazon_query": f"{title} 原作 1",
            "image_url": record.get("picture", ""), "image_thumb": record.get("thumbnail", ""),
            "image_credit": "MyAnimeList", "image_source_url": source_url(record),
            "source_record_url": source_url(record),
        }
        upsert_record(db, item, current + added, "basic")
        existing.add(key)
        existing.add(normal(record.get("title", "")))
        selected_sources.update(record_sources)
        selected_network.update(record_sources)
        selected_network.update(record_related)
        added += 1
    db.execute("INSERT OR REPLACE INTO catalog_meta VALUES ('source_dataset', ?)", (root.get("repository", ""),))
    db.execute("INSERT OR REPLACE INTO catalog_meta VALUES ('source_last_update', ?)", (root.get("lastUpdate", ""),))
    db.commit()
    if current + added < target:
        raise SystemExit(f"target {target} not reached: {current + added}")
    print(f"catalog: {current} -> {current + added}")


def export_records(db: sqlite3.Connection) -> list[dict]:
    records = []
    rows = db.execute("SELECT * FROM anime WHERE enabled=1 ORDER BY sort_order,id").fetchall()
    for row in rows:
        item = dict(row)
        item["genres"] = [r[0] for r in db.execute("SELECT name FROM anime_genre WHERE anime_id=? ORDER BY position", (row["id"],))]
        item["moods"] = [r[0] for r in db.execute("SELECT name FROM anime_mood WHERE anime_id=? ORDER BY position", (row["id"],))]
        item["characters"] = [dict(r) for r in db.execute("SELECT name,role FROM anime_character WHERE anime_id=? ORDER BY position", (row["id"],))]
        links = [dict(r) for r in db.execute("SELECT kind,provider,label,url,is_affiliate,position FROM anime_link WHERE anime_id=? ORDER BY kind,position", (row["id"],))]
        item["links"] = links
        for link in links:
            if link["kind"] == "official": item["official_url"] = link["url"]
            if link["kind"] == "source": item["source_record_url"] = link["url"]
            if link["kind"] == "commerce" and link["provider"] == "Amazon": item["amazon_url"] = link["url"]
            if link["kind"] == "watch" and link["provider"] == "Amazon Prime Video": item["prime_video_url"] = link["url"]
            if link["kind"] == "watch" and link["provider"] == "JustWatch": item["watch_url"] = link["url"]
        records.append(item)
    return records


def validate(db: sqlite3.Connection) -> None:
    records = export_records(db)
    errors = []
    for item in records:
        if not item["genres"]: errors.append(f"{item['id']}: no genre")
        if not item["moods"]: errors.append(f"{item['id']}: no mood")
        if ASSOCIATE_TAG not in item.get("amazon_url", ""): errors.append(f"{item['id']}: Amazon tag missing")
        if ASSOCIATE_TAG not in item.get("prime_video_url", ""): errors.append(f"{item['id']}: Prime Video tag missing")
        if not item.get("image_url"): errors.append(f"{item['id']}: image missing")
    if errors:
        raise SystemExit("\n".join(errors))
    full = sum(item["curation_level"] == "full" for item in records)
    print(f"OK: {len(records)} records ({full} full / {len(records)-full} basic), affiliate links validated")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--json", type=Path, required=True)
    expand = sub.add_parser("expand")
    expand.add_argument("--offline", type=Path, required=True)
    expand.add_argument("--target", type=int, default=300)
    export = sub.add_parser("export")
    export.add_argument("--output", type=Path, required=True)
    sub.add_parser("validate")
    sub.add_parser("stats")
    args = parser.parse_args()
    if args.command == "init" and args.db.exists():
        args.db.unlink()
    db = connect(args.db)
    if args.command == "init": import_json(db, args.json)
    elif args.command == "expand": expand_offline(db, args.offline, args.target)
    elif args.command == "export": args.output.write_text(json.dumps(export_records(db), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    elif args.command == "validate": validate(db)
    elif args.command == "stats":
        rows = db.execute("SELECT curation_level,COUNT(*) n FROM anime WHERE enabled=1 GROUP BY curation_level").fetchall()
        print(" ".join(f"{row['curation_level']}={row['n']}" for row in rows))


if __name__ == "__main__":
    main()
