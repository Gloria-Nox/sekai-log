// ═══════════════════════════════════════
// SEKAI LOG — CMS v3（JSONファイル読み込み）
// GitHub APIを使わないので制限なし！
// ═══════════════════════════════════════

let _articlesCache = null;

// 全記事をarticles.jsonから取得（1回だけ読み込んでキャッシュ）
async function loadAllArticles() {
  if (_articlesCache) return _articlesCache;
  try {
    const res = await fetch('/articles.json?v=' + Date.now());
    if (!res.ok) throw new Error('articles.json not found');
    _articlesCache = await res.json();
    return _articlesCache;
  } catch (e) {
    console.error('記事の読み込みに失敗:', e);
    return [];
  }
}

// カテゴリの記事一覧を取得
async function fetchArticles(category) {
  const all = await loadAllArticles();
  return all.filter(a => a.category === category);
}

// 単一記事を取得
async function fetchArticle(category, slug) {
  const all = await loadAllArticles();
  return all.find(a => a.category === category && a.slug === slug) || null;
}

// 全カテゴリから最新記事を取得
async function fetchAllLatest(limit = 100) {
  const all = await loadAllArticles();
  return all.slice(0, limit);
}

// キーワード検索
async function searchArticles(query) {
  if (!query || !query.trim()) return [];
  const q = query.trim().toLowerCase();
  const all = await loadAllArticles();
  return all.filter(a =>
    (a.title || '').toLowerCase().includes(q) ||
    (a.excerpt || '').toLowerCase().includes(q) ||
    (CAT_LABELS[a.category] || '').includes(q)
  );
}

// 日付フォーマット
function formatDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  if (isNaN(d)) return '';
  return `${d.getFullYear()}.${String(d.getMonth()+1).padStart(2,'0')}.${String(d.getDate()).padStart(2,'0')}`;
}

// カテゴリ日本語名
const CAT_LABELS = {
  anime: 'アニメ', novel: '小説', sf: 'SF',
  subculture: 'サブカル', review: '評論'
};

// 年代ラベル
const DECADE_LABELS = {
  '2020': '2020年代', '2010': '2010年代',
  '2000': '2000年代', 'pre2000': '2000年以前'
};

// 記事カードHTML
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

// ローディング表示
function showLoading(container) {
  container.innerHTML = `
    <div style="grid-column:1/-1;text-align:center;padding:4rem;color:var(--muted);
    font-family:'Space Mono',monospace;font-size:0.7rem;letter-spacing:0.2em;">
      LOADING...
    </div>`;
}

// 記事なし表示
function showEmpty(container, msg) {
  container.innerHTML = `
    <div style="grid-column:1/-1;text-align:center;padding:4rem;color:var(--muted);
    font-family:'Space Mono',monospace;font-size:0.7rem;letter-spacing:0.2em;">
      ${msg || 'まだ記事がありません'}
    </div>`;
}
