// ═══════════════════════════
// SEKAI LOG — 共通JS
// ═══════════════════════════

document.addEventListener('DOMContentLoaded', () => {
  // スクロールフェードイン
  const reveals = document.querySelectorAll('.reveal');
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry, i) => {
      if (entry.isIntersecting) {
        setTimeout(() => entry.target.classList.add('visible'), i * 80);
      }
    });
  }, { threshold: 0.1 });
  reveals.forEach(el => observer.observe(el));

  // ハンバーガーメニュー
  const toggle = document.getElementById('nav-toggle');
  const nav = document.getElementById('main-nav');
  if (toggle && nav) {
    toggle.addEventListener('click', () => {
      toggle.classList.toggle('open');
      nav.classList.toggle('open');
      document.body.style.overflow = nav.classList.contains('open') ? 'hidden' : '';
    });

    // モバイル：カテゴリ名タップでドロップダウン開閉
    nav.querySelectorAll('.nav-item > a').forEach(a => {
      a.addEventListener('click', (e) => {
        const dropdown = a.nextElementSibling;
        if (dropdown && dropdown.classList.contains('dropdown') && window.innerWidth <= 768) {
          e.preventDefault();
          dropdown.classList.toggle('open');
        }
      });
    });

    // ドロップダウン内のリンクでメニューを閉じる
    nav.querySelectorAll('.dropdown a').forEach(a => {
      a.addEventListener('click', () => {
        toggle.classList.remove('open');
        nav.classList.remove('open');
        document.body.style.overflow = '';
      });
    });
  }

  // カテゴリナビのアクティブ状態
  const catNavLinks = document.querySelectorAll('.cat-nav a');
  const currentPage = location.pathname.split('/').pop() || 'index.html';
  catNavLinks.forEach(a => {
    const href = a.getAttribute('href').split('?')[0];
    if (href === currentPage) a.classList.add('active');
  });
});
