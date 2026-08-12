# SEKAI LOG 編集ガイド

公開記事の正本は `_posts/<category>/` 内のMarkdownです。HTMLや`articles.json`を直接編集せず、原稿を編集してから `python build.py` を実行します。

## 毎日の公開手順

1. 既存原稿を複製し、`_posts/anime/2026-08-04-example-title.md` のような名前で保存する。
2. Frontmatterの `title`、`date`、`excerpt`、`slug` を更新する。
3. 下書き中は `status: draft` を付ける。公開時に削除するか `status: published` にする。
4. 事実、固有名詞、公開年、引用元を確認する。確認できない数字や因果関係は断定しない。
5. 作品の核心に触れる場合は `spoilers: true` を付ける。
6. `python build.py` を実行し、生成ページをブラウザで確認する。
7. 変更をGitHubへ反映する。mainへ入るとGitHub Actionsも生成結果を検証する。

## Frontmatter例

```yaml
---
title: "記事タイトル"
date: 2026-08-04T20:00:00+09:00
slug: example-title
excerpt: "一覧と検索結果に表示する、記事固有の説明。"
decade: "2020"
spoilers: true
status: draft
---
```

`slug` は半角小文字・数字・ハイフンだけを使います。公開後はURL維持のため変更しません。

## Amazon商品リンク

Amazonアソシエイトで発行し、トラッキングIDを確認したURLだけを使います。価格は変動するため本文へ固定表示しません。

```yaml
amazon_url: "https://www.amazon.co.jp/...&tag=YOUR-ID-22"
amazon_label: "原作小説をAmazonで見る"
amazon_note: "この記事で扱った原作小説"
```

複数の商品を紹介する場合は、2件目以降へ `_2`〜`_5` を付けます。

```yaml
amazon_url_2: "https://link.amazon/..."
amazon_label_2: "関連書籍をAmazonで見る"
amazon_note_2: "本文と直接関係する関連書籍"
```

商品カードには自動で「広告」と `rel="nofollow sponsored"` が付きます。作品と直接関係のない商品や、推薦理由を書けない商品は載せません。

## 公開前チェック

- タイトルだけで記事の問いが分かる
- 冒頭で記事の対象と結論の方向が分かる
- 公式情報と筆者の解釈が混ざっていない
- 出典なしの統計・人数・売上・社会的影響を断定していない
- 引用が必要最小限で、出典が明記されている
- ネタバレ表示が適切
- 商品リンクが広告だと分かる
- 誤字、リンク切れ、スマートフォン表示を確認した
