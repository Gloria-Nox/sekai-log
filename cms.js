// ═══════════════════════════════════════
// SEKAI LOG — CMS記事取得ユーティリティ
// GitHub APIから記事を取得して表示する
// ═══════════════════════════════════════

const GITHUB_REPO = 'Gloria-Nox/sekai-log';
const API_BASE = `https://api.github.com/repos/${GITHUB_REPO}/contents`;

// フロントマターをパース
function parseFrontmatter(text) {
  const match = text.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
  if (!match) return { data: {}, content: text };
  const data = {};
  match[1].split('\n').forEach(line => {
    const [key, ...vals] = line.split(':');
    if (key && vals.length) {
      data[key.trim()] = vals.join(':').trim().replace(/^["']|["']$/g, '');
    }
  });
  return { data, content: match[2] };
}

// Base64デコード（日本語対応）
function decodeBase64(str) {
  return decodeURIComponent(
    atob(str.replace(/\s/g, '')).split('').map(c =>
      '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2)
    ).join('')
  );
}

// カテゴリの記事一覧を取得
async function fetchArticles(category) {
  try {
    const res = await fetch(`${API_BASE}/_posts/${category}`);
    if (!res.ok) return [];
    const files = await res.json();
    const mdFiles = files.filter(f => f.name.endsWith('.md'));

    const articles = await Promise.all(mdFiles.map(async file => {
      const r = await fetch(file.url);
      const d = await r.json();
      const text = decodeBase64(d.content);
      const { data } = parseFrontmatter(text);
      return {
        ...data,
        slug: file.name.replace('.md', ''),
        category,
        filename: file.name
      };
    }));

    // 日付でソート（新しい順）
    return articles.sort((a, b) => new Date(b.date) - new Date(a.date));
  } catch (e) {
    console.error('記事取得エラー:', e);
    return [];
  }
}

// 単一記事を取得
async function fetchArticle(category, slug) {
  try {
    const files = await fetch(`${API_BASE}/_posts/${category}`).then(r => r.json());
    const file = files.find(f => f.name.includes(slug) || f.name === slug + '.md');
    if (!file) return null;
    const d = await fetch(file.url).then(r => r.json());
    const text = decodeBase64(d.content);
    const { data, content } = parseFrontmatter(text);
    return { ...data, content, category, slug };
  } catch (e) {
    return null;
  }
}

// 全カテゴリから最新記事を取得
async function fetchAllLatest(limit = 5) {
  const categories = ['anime', 'novel', 'sf', 'subculture', 'review'];
  const all = await Promise.all(categories.map(c => fetchArticles(c)));
  return all.flat().sort((a, b) => new Date(b.date) - new Date(a.date)).slice(0, limit);
}

// 日付フォーマット
function formatDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
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

// 記事カードHTMLを生成
function articleCardHTML(article, index) {
  const tag = `${DECADE_LABELS[article.decade] || ''} / ${CAT_LABELS[article.category] || ''}`;
  const date = formatDate(article.date);
  const url = `article.html?category=${article.category}&slug=${article.slug}`;
  return `
    <a href="${url}" class="article-card" data-decade="${article.decade || 'all'}">
      <p class="article-tag">${tag}</p>
      <h3 class="article-title">${article.title || '無題'}</h3>
      <p class="article-excerpt">${article.excerpt || ''}</p>
      <div class="article-meta">
        <span>${date}</span>
        <span>${article.readtime || ''}</span>
      </div>
    </a>`;
}

// ローディング表示
function showLoading(container) {
  container.innerHTML = `
    <div style="grid-column:1/-1;text-align:center;padding:4rem;color:var(--muted);font-family:'Space Mono',monospace;font-size:0.7rem;letter-spacing:0.2em;">
      LOADING...
    </div>`;
}

// 記事なし表示
function showEmpty(container) {
  container.innerHTML = `
    <div style="grid-column:1/-1;text-align:center;padding:4rem;color:var(--muted);font-family:'Space Mono',monospace;font-size:0.7rem;letter-spacing:0.2em;">
      まだ記事がありません
    </div>`;
}
