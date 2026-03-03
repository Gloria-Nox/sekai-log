// ═══════════════════════════════════════
// SEKAI LOG — CMS記事取得ユーティリティ v2
// ═══════════════════════════════════════

const GITHUB_REPO = 'Gloria-Nox/sekai-log';
const API_BASE = `https://api.github.com/repos/${GITHUB_REPO}/contents`;
const CACHE_KEY = 'sekai-log-cache';
const CACHE_TTL = 10 * 60 * 1000; // 10分キャッシュ

// ── キャッシュ ──
function getCached(key) {
  try {
    const item = sessionStorage.getItem(key);
    if (!item) return null;
    const { data, ts } = JSON.parse(item);
    if (Date.now() - ts > CACHE_TTL) { sessionStorage.removeItem(key); return null; }
    return data;
  } catch { return null; }
}
function setCache(key, data) {
  try { sessionStorage.setItem(key, JSON.stringify({ data, ts: Date.now() })); } catch {}
}

// ── フロントマターパース ──
function parseFrontmatter(text) {
  const match = text.match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/);
  if (!match) return { data: {}, content: text };
  const data = {};
  match[1].split('\n').forEach(line => {
    const idx = line.indexOf(':');
    if (idx === -1) return;
    const key = line.slice(0, idx).trim();
    const val = line.slice(idx + 1).trim().replace(/^["']|["']$/g, '');
    if (key) data[key] = val;
  });
  return { data, content: match[2] };
}

// ── Base64デコード（日本語対応）──
function decodeBase64(str) {
  try {
    return decodeURIComponent(
      atob(str.replace(/\s/g, '')).split('').map(c =>
        '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2)
      ).join('')
    );
  } catch { return ''; }
}

// ── 読了時間を自動計算（文字数から）──
function calcReadTime(content) {
  const chars = content.replace(/[#\-\*`>\[\]!]/g, '').replace(/\s/g, '').length;
  const minutes = Math.max(1, Math.ceil(chars / 400));
  return `${minutes}分`;
}

// ── カテゴリの記事一覧を取得 ──
async function fetchArticles(category) {
  const cacheKey = `${CACHE_KEY}-${category}`;
  const cached = getCached(cacheKey);
  if (cached) return cached;

  try {
    const res = await fetch(`${API_BASE}/_posts/${category}`);
    if (!res.ok) return [];
    const files = await res.json();
    if (!Array.isArray(files)) return [];
    const mdFiles = files.filter(f => f.name.endsWith('.md'));

    const articles = await Promise.all(mdFiles.map(async file => {
      const r = await fetch(file.url);
      if (!r.ok) return null;
      const d = await r.json();
      const text = decodeBase64(d.content);
      const { data, content } = parseFrontmatter(text);
      const readtime = data.readtime || calcReadTime(content);
      return {
        ...data,
        readtime,
        slug: file.name.replace(/\.md$/, ''),
        category,
        filename: file.name
      };
    }));

    const result = articles
      .filter(Boolean)
      .sort((a, b) => new Date(b.date) - new Date(a.date));

    setCache(cacheKey, result);
    return result;
  } catch (e) {
    console.error('記事取得エラー:', category, e);
    return [];
  }
}

// ── 単一記事を取得 ──
async function fetchArticle(category, slug) {
  try {
    const articles = await fetchArticles(category);
    const found = articles.find(a => a.slug === slug || a.slug.includes(slug));
    if (!found) return null;

    const files = await fetch(`${API_BASE}/_posts/${category}`).then(r => r.json());
    const file = files.find(f => f.name === found.filename || f.name.includes(slug));
    if (!file) return null;

    const d = await fetch(file.url).then(r => r.json());
    const text = decodeBase64(d.content);
    const { data, content } = parseFrontmatter(text);
    const readtime = data.readtime || calcReadTime(content);
    return { ...data, readtime, content, category, slug };
  } catch { return null; }
}

// ── 全カテゴリから最新記事を取得 ──
async function fetchAllLatest(limit = 100) {
  const categories = ['anime', 'novel', 'sf', 'subculture', 'review'];
  const all = await Promise.all(categories.map(c => fetchArticles(c)));
  return all.flat().sort((a, b) => new Date(b.date) - new Date(a.date)).slice(0, limit);
}

// ── 全記事からキーワード検索 ──
async function searchArticles(query) {
  if (!query || query.trim().length < 1) return [];
  const q = query.trim().toLowerCase();
  const all = await fetchAllLatest(200);
  return all.filter(a =>
    (a.title || '').toLowerCase().includes(q) ||
    (a.excerpt || '').toLowerCase().includes(q) ||
    (CAT_LABELS[a.category] || '').includes(q)
  );
}

// ── 日付フォーマット ──
function formatDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  if (isNaN(d)) return '';
  return `${d.getFullYear()}.${String(d.getMonth()+1).padStart(2,'0')}.${String(d.getDate()).padStart(2,'0')}`;
}

// ── カテゴリ日本語名 ──
const CAT_LABELS = {
  anime: 'アニメ', novel: '小説', sf: 'SF',
  subculture: 'サブカル', review: '評論'
};

// ── 年代ラベル ──
const DECADE_LABELS = {
  '2020': '2020年代', '2010': '2010年代',
  '2000': '2000年代', 'pre2000': '2000年以前'
};

// ── 記事カードHTML ──
function articleCardHTML(article) {
  const catLabel = CAT_LABELS[article.category] || '';
  const decadeLabel = DECADE_LABELS[article.decade] || '';
  const tag = [decadeLabel, catLabel].filter(Boolean).join(' / ');
  const date = formatDate(article.date);
  const url = `article.html?category=${article.category}&slug=${article.slug}`;
  return `
    <a href="${url}" class="article-card" data-decade="${article.decade || ''}">
      <p class="article-tag">${tag}</p>
      <h3 class="article-title">${article.title || '無題'}</h3>
      <p class="article-excerpt">${article.excerpt || ''}</p>
      <div class="article-meta">
        <span>${date}</span>
        <span>読了 ${article.readtime || ''}</span>
      </div>
    </a>`;
}

// ── ローディング表示 ──
function showLoading(container) {
  container.innerHTML = `
    <div style="grid-column:1/-1;text-align:center;padding:4rem;color:var(--muted);
    font-family:'Space Mono',monospace;font-size:0.7rem;letter-spacing:0.2em;">
      LOADING...
    </div>`;
}

// ── 記事なし表示 ──
function showEmpty(container, msg) {
  container.innerHTML = `
    <div style="grid-column:1/-1;text-align:center;padding:4rem;color:var(--muted);
    font-family:'Space Mono',monospace;font-size:0.7rem;letter-spacing:0.2em;">
      ${msg || 'まだ記事がありません'}
    </div>`;
}
