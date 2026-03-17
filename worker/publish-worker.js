export default {
  async fetch(request, env) {
    const origin = request.headers.get('Origin') || '';
    const allowOrigin = env.WRITER_ALLOWED_ORIGIN || '*';

    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders(allowOrigin, origin) });
    }

    if (request.method !== 'POST') {
      return json({ error: 'Method not allowed' }, 405, corsHeaders(allowOrigin, origin));
    }

    let payload;
    try {
      payload = await request.json();
    } catch {
      return json({ error: 'Invalid JSON' }, 400, corsHeaders(allowOrigin, origin));
    }

    if (!env.WRITER_PASSWORD || payload.password !== env.WRITER_PASSWORD) {
      return json({ error: 'Unauthorized' }, 401, corsHeaders(allowOrigin, origin));
    }

    const required = ['category', 'slug', 'title', 'date', 'excerpt', 'body'];
    for (const key of required) {
      if (!String(payload[key] || '').trim()) {
        return json({ error: `Missing field: ${key}` }, 400, corsHeaders(allowOrigin, origin));
      }
    }

    const safeSlug = String(payload.slug).trim();
    if (!/^[-_a-zA-Z0-9]+$/.test(safeSlug)) {
      return json({ error: 'Invalid slug format' }, 400, corsHeaders(allowOrigin, origin));
    }

    const category = String(payload.category).trim();
    const dateOnly = String(payload.date).slice(0, 10);
    const fileName = `${dateOnly}-${safeSlug}.md`;
    const path = `_posts/${category}/${fileName}`;

    const markdown = buildMarkdown(payload);

    const owner = env.GITHUB_OWNER;
    const repo = env.GITHUB_REPO;
    const branch = env.GITHUB_BRANCH || 'main';
    const token = env.GITHUB_TOKEN;

    if (!owner || !repo || !token) {
      return json({ error: 'Worker secrets are not configured' }, 500, corsHeaders(allowOrigin, origin));
    }

    const apiBase = `https://api.github.com/repos/${owner}/${repo}/contents/${encodeURIComponent(path)}`;
    const headers = {
      Authorization: `Bearer ${token}`,
      Accept: 'application/vnd.github+json',
      'Content-Type': 'application/json',
      'User-Agent': 'sekai-log-writer-worker'
    };

    let existingSha;
    const getRes = await fetch(`${apiBase}?ref=${encodeURIComponent(branch)}`, { headers });
    if (getRes.ok) {
      const existing = await getRes.json();
      existingSha = existing.sha;
    }

    const body = {
      message: `docs: add article ${path}`,
      content: toBase64(markdown),
      branch
    };
    if (existingSha) body.sha = existingSha;

    const putRes = await fetch(apiBase, {
      method: 'PUT',
      headers,
      body: JSON.stringify(body)
    });

    if (!putRes.ok) {
      const errText = await putRes.text();
      return json({ error: `GitHub API error: ${putRes.status}`, detail: errText }, 502, corsHeaders(allowOrigin, origin));
    }

    return json({ ok: true, path, branch }, 200, corsHeaders(allowOrigin, origin));
  }
};

function buildMarkdown(data) {
  const lines = [
    '---',
    `title: ${String(data.title).trim()}`,
    `date: ${String(data.date).trim()}`
  ];

  if (String(data.decade || '').trim()) lines.push(`decade: "${String(data.decade).trim()}"`);
  lines.push(`excerpt: ${String(data.excerpt).trim()}`);
  if (String(data.readtime || '').trim()) lines.push(`readtime: "${String(data.readtime).trim()}"`);
  if (String(data.thumbnail || '').trim()) lines.push(`thumbnail: "${String(data.thumbnail).trim()}"`);
  lines.push('---', '', String(data.body || ''));

  return lines.join('\n');
}

function toBase64(str) {
  return btoa(unescape(encodeURIComponent(str)));
}

function json(data, status = 200, headers = {}) {
  return new Response(JSON.stringify(data, null, 2), {
    status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      ...headers
    }
  });
}

function corsHeaders(allowOrigin, requestOrigin) {
  const origin = allowOrigin === '*' ? '*' : (requestOrigin && requestOrigin === allowOrigin ? requestOrigin : allowOrigin);
  return {
    'Access-Control-Allow-Origin': origin,
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type'
  };
}
