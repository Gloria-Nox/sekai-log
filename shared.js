(() => {
  const menuButton = document.querySelector('.menu-button');
  const navigation = document.getElementById('site-nav');

  if (menuButton && navigation) {
    menuButton.addEventListener('click', () => {
      const open = navigation.classList.toggle('is-open');
      menuButton.setAttribute('aria-expanded', String(open));
      menuButton.textContent = open ? 'CLOSE' : 'MENU';
    });
  }

  const input = document.getElementById('article-filter');
  const cards = Array.from(document.querySelectorAll('#article-list .story-card'));
  const status = document.getElementById('filter-status');
  const empty = document.getElementById('empty-state');

  if (input && cards.length) {
    const normalize = (value) => String(value || '').normalize('NFKC').toLowerCase().trim();
    const filter = () => {
      const query = normalize(input.value);
      let visible = 0;
      cards.forEach((card) => {
        const matched = !query || normalize(card.dataset.search).includes(query);
        card.hidden = !matched;
        if (matched) visible += 1;
      });
      if (status) status.textContent = `${visible}件の記事`;
      if (empty) empty.hidden = visible !== 0;
    };
    input.addEventListener('input', filter);
  }
})();
