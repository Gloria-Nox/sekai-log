// ═══════════════════════════
// SEKAI LOG v9 — 共通JS
// ═══════════════════════════

// ── サイト横断ナビを自動注入（全ページ共通） ──
(function() {
  // すでにある場合は注入しない
  if (document.querySelector('.site-network-nav')) return;
  const nav = document.createElement('div');
  nav.className = 'site-network-nav';
  nav.innerHTML = `
    <div class="site-network-inner">
      <span class="network-label">SEKAI LOG NETWORK</span>
      <span class="network-sep">|</span>
      <a href="https://sekai-log.com" class="network-link network-link--active">📰 SEKAI LOG</a>
      <a href="https://arknights.sekai-log.com" class="network-link network-link--game">🎮 アークナイツ</a>
      <span class="network-link network-link--soon">⚔️ ギルティギア <em>(準備中)</em></span>
    </div>`;
  document.body.insertBefore(nav, document.body.firstChild);
})();

document.addEventListener('DOMContentLoaded', () => {

  // スクロールフェードイン
  const reveals = document.querySelectorAll('.reveal');
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry, i) => {
      if (entry.isIntersecting) {
        setTimeout(() => entry.target.classList.add('visible'), i * 80);
      }
    });
  }, { threshold: 0.08 });
  reveals.forEach(el => observer.observe(el));

  // ハンバーガーメニュー
  const toggle = document.getElementById('nav-toggle');
  const nav = document.getElementById('main-nav');
  if (toggle && nav) {
    toggle.addEventListener('click', () => {
      const isOpen = nav.classList.toggle('open');
      toggle.classList.toggle('open', isOpen);
      document.body.style.overflow = isOpen ? 'hidden' : '';
    });

    nav.querySelectorAll('.nav-item > a').forEach(a => {
      a.addEventListener('click', (e) => {
        const dropdown = a.nextElementSibling;
        if (dropdown && dropdown.classList.contains('dropdown') && window.innerWidth <= 768) {
          e.preventDefault();
          dropdown.classList.toggle('open');
        }
      });
    });

    nav.querySelectorAll('.dropdown a').forEach(a => {
      a.addEventListener('click', () => {
        toggle.classList.remove('open');
        nav.classList.remove('open');
        document.body.style.overflow = '';
      });
    });
  }

  // カテゴリナビのアクティブ状態
  const currentPage = location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.cat-nav a').forEach(a => {
    const href = a.getAttribute('href').split('?')[0];
    if (href === currentPage) a.classList.add('active');
  });

});
