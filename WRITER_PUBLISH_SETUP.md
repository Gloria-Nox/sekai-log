# 投稿ツールから直接GitHubへ投稿する設定

## 1) Cloudflare Worker を作成

```bash
cd worker
cp wrangler.toml.example wrangler.toml
```

`wrangler.toml` の `GITHUB_OWNER / GITHUB_REPO / WRITER_ALLOWED_ORIGIN` を実運用値に合わせる。

## 2) シークレット設定

```bash
wrangler secret put GITHUB_TOKEN
wrangler secret put WRITER_PASSWORD
```

- `GITHUB_TOKEN`: repo の contents:write 権限がある PAT
- `WRITER_PASSWORD`: writer.html のログインパスワード（例: 1998）

## 3) デプロイ

```bash
wrangler deploy
```

デプロイ後に `https://xxxxx.workers.dev` が発行される。

## 4) writer.html で API URL を入力

投稿ツールの `投稿API URL（Cloudflare Worker）` に、Worker URL（例: `https://xxxxx.workers.dev`）を入力。

そのまま `GitHubへ投稿` を押すと `_posts/<category>/<date>-<slug>.md` にコミットされる。

## 5) サイト反映

- `_posts/**` 更新で GitHub Actions が `build.py` を実行し、
  `articles.json / sitemap.xml / robots.txt` を同期。
- Cloudflare Pages が再デプロイ。
