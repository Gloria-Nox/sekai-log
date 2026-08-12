(() => {
  'use strict';

  const menuButton = document.querySelector('.menu-button');
  const navigation = document.getElementById('site-nav');
  if (menuButton && navigation) {
    menuButton.addEventListener('click', () => {
      const open = navigation.classList.toggle('is-open');
      menuButton.setAttribute('aria-expanded', String(open));
      menuButton.textContent = open ? '閉じる' : 'MENU';
    });
  }

  const normalize = (value) => String(value || '').normalize('NFKC').toLowerCase().trim();
  const articleInput = document.getElementById('article-filter');
  const articleCards = Array.from(document.querySelectorAll('#article-list .story-card'));
  if (articleInput && articleCards.length) {
    const filterArticles = () => {
      const query = normalize(articleInput.value);
      let visible = 0;
      articleCards.forEach((card) => {
        const matched = !query || normalize(card.dataset.search).includes(query);
        card.hidden = !matched;
        if (matched) visible += 1;
      });
      const status = document.getElementById('filter-status');
      const empty = document.getElementById('empty-state');
      if (status) status.textContent = `${visible}件の記事`;
      if (empty) empty.hidden = visible !== 0;
    };
    articleInput.addEventListener('input', filterArticles);
  }

  const dataNode = document.getElementById('anime-data');
  if (!dataNode) return;

  let anime = [];
  try { anime = JSON.parse(dataNode.textContent); } catch (error) { console.error(error); return; }
  if (!anime.length) return;

  const $ = (selector) => document.querySelector(selector);
  const result = $('#anime-result');
  const genreFilter = $('#genre-filter');
  const moodFilter = $('#mood-filter');
  const timeFilter = $('#time-filter');
  const selectorNote = $('#selector-note');
  const spinButton = $('#spin-button');
  const wheel = $('#roulette-wheel');
  const wheelLabels = $('#wheel-labels');
  const grid = $('#anime-grid');
  const search = $('#anime-search');
  const catalogStatus = $('#catalog-status');
  const showMore = $('#show-more');
  const chips = Array.from(document.querySelectorAll('#catalog-chips button'));
  const dialog = $('#anime-dialog');
  const dialogContent = $('#dialog-content');
  const dialogClose = $('#dialog-close');
  const tag = 'sekailog-22';
  const wheelSize = 8;
  let activeGenre = 'all';
  let displayLimit = 12;
  let currentRotation = 0;
  let spinning = false;

  const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const track = (name, params = {}) => {
    if (typeof window.gtag === 'function') window.gtag('event', name, params);
  };
  const totalMinutes = (item) => item.episodes * item.minutes;
  const totalLabel = (item) => {
    const total = totalMinutes(item);
    const hours = Math.floor(total / 60);
    const mins = total % 60;
    return `約${hours}時間${mins ? `${mins}分` : ''}`;
  };
  const timeMatch = (item, value) => {
    const total = totalMinutes(item);
    if (value === 'short') return total <= 240;
    if (value === 'medium') return total > 240 && total <= 600;
    if (value === 'long') return total > 600;
    return true;
  };
  const amazonUrl = (item) => item.amazon_asin
    ? `https://www.amazon.co.jp/dp/${encodeURIComponent(item.amazon_asin)}?tag=${tag}`
    : `https://www.amazon.co.jp/s?k=${encodeURIComponent(item.amazon_query || `${item.title} 1`)}&tag=${tag}`;
  const watchUrl = (item) => `https://www.justwatch.com/jp/検索?q=${encodeURIComponent(item.title)}`;
  const initials = (item) => item.glyph || item.title.slice(0, 2);

  document.addEventListener('error', (event) => {
    const image = event.target;
    if (!(image instanceof HTMLImageElement) || !image.matches('.anime-poster img')) return;
    image.closest('.anime-poster')?.classList.add('is-fallback');
    image.remove();
  }, true);

  const candidates = () => anime.filter((item) =>
    (genreFilter.value === 'all' || item.genres.includes(genreFilter.value)) &&
    (moodFilter.value === 'all' || item.moods.includes(moodFilter.value)) &&
    timeMatch(item, timeFilter.value)
  );

  const wheelItems = (pool) => Array.from({length: wheelSize}, (_, index) => pool[index % pool.length]);

  const paintWheel = () => {
    const pool = candidates();
    if (!pool.length) {
      wheelLabels.innerHTML = '';
      spinButton.disabled = true;
      selectorNote.textContent = 'その組み合わせは0作品。条件をひとつ戻してみて。';
      selectorNote.classList.add('is-error');
      return [];
    }
    spinButton.disabled = false;
    selectorNote.classList.remove('is-error');
    selectorNote.textContent = pool.length === anime.length
      ? `全${anime.length}作品が入っています。`
      : `${pool.length}作品まで絞りました。`;
    const visible = wheelItems(pool);
    wheelLabels.innerHTML = visible.map((item, index) => {
      const angle = index * (360 / wheelSize) + (180 / wheelSize);
      return `<span style="--angle:${angle}deg"><b>${escapeHtml(initials(item))}</b><small>${escapeHtml(item.title)}</small></span>`;
    }).join('');
    return visible;
  };

  const actionLinks = (item, includeShare = false) => `
    <a class="action-primary" href="${escapeHtml(item.official_url)}" target="_blank" rel="noopener" data-action="official" data-title="${escapeHtml(item.title)}">公式サイトへ <span>↗</span></a>
    <a href="${escapeHtml(watchUrl(item))}" target="_blank" rel="noopener" data-action="watch" data-title="${escapeHtml(item.title)}">どこで観られる？ <span>↗</span></a>
    <a href="${escapeHtml(amazonUrl(item))}" target="_blank" rel="nofollow sponsored noopener" data-action="amazon" data-title="${escapeHtml(item.title)}">原作を見る <small>Amazon広告</small><span>↗</span></a>
    ${includeShare ? '<button type="button" id="share-result">友だちに送る <span>↗</span></button>' : ''}`;

  const characterMarkup = (item) => item.characters.map((person) => `
    <li><b>${escapeHtml(person.name)}</b><span>${escapeHtml(person.role)}</span></li>`).join('');

  const poster = (item, size = '') => {
    const eager = size.includes('result') || size.includes('dialog');
    const source = item.image_source_url || item.official_url;
    const credit = item.image_credit || '画像出典';
    return `
      <figure class="anime-poster ${size}" style="--poster:${escapeHtml(item.accent)}">
        <div class="poster-fallback" aria-hidden="true"><span class="poster-spark">✦</span><b>${escapeHtml(initials(item))}</b><small>${escapeHtml(item.genres[0])}</small></div>
        ${item.image_url ? `<img src="${escapeHtml(size ? item.image_url : (item.image_thumb || item.image_url))}" alt="${escapeHtml(item.title)}の作品ビジュアル" loading="${eager ? 'eager' : 'lazy'}" decoding="async" referrerpolicy="no-referrer">` : ''}
        <figcaption><a href="${escapeHtml(source)}" target="_blank" rel="noopener" data-image-credit>画像：${escapeHtml(credit)} <span>↗</span></a></figcaption>
      </figure>`;
  };

  const renderResult = (item) => {
    result.classList.remove('is-empty');
    result.classList.add('is-revealing');
    result.innerHTML = `
      <div class="result-burst" aria-hidden="true">あたり！</div>
      ${poster(item, 'anime-poster--result')}
      <div class="result-copy">
        <p class="result-picked">今夜はこれ。</p>
        <h2>${escapeHtml(item.title)}</h2>
        <div class="result-meta"><span>${escapeHtml(item.format)}</span><span>${item.episodes}話</span><span>${totalLabel(item)}</span></div>
        <p class="result-summary">${escapeHtml(item.summary)}</p>
        <ul class="quick-characters">${characterMarkup(item)}</ul>
        <div class="result-actions">${actionLinks(item, true)}</div>
        <p class="affiliate-mini">Amazonリンクはアソシエイト広告です。</p>
      </div>`;
    window.setTimeout(() => result.classList.remove('is-revealing'), 600);
    const shareButton = $('#share-result');
    if (shareButton) shareButton.addEventListener('click', () => share(item));
  };

  const spin = () => {
    if (spinning) return;
    const visible = paintWheel();
    if (!visible.length) return;
    spinning = true;
    spinButton.disabled = true;
    spinButton.querySelector('strong').textContent = '回転中';
    const segment = Math.floor(Math.random() * wheelSize);
    const selected = visible[segment];
    const segmentCenter = segment * (360 / wheelSize) + (180 / wheelSize);
    const base = currentRotation + 1800;
    const correction = (360 - ((base + segmentCenter) % 360)) % 360;
    currentRotation = base + correction;
    wheel.classList.add('is-spinning');
    wheel.style.transform = `rotate(${currentRotation}deg)`;
    selectorNote.textContent = 'さて、どれになる…？';

    const finish = () => {
      wheel.classList.remove('is-spinning');
      spinButton.disabled = false;
      spinButton.querySelector('strong').textContent = 'もう一回';
      selectorNote.textContent = `「${selected.title}」に決まり。`;
      renderResult(selected);
      spinning = false;
      track('roulette_complete', {anime_title: selected.title, candidate_count: candidates().length});
      if (window.innerWidth < 880) result.scrollIntoView({behavior: 'smooth', block: 'start'});
    };
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    window.setTimeout(finish, reduced ? 120 : 2300);
    track('roulette_start', {genre: genreFilter.value, mood: moodFilter.value, time: timeFilter.value});
  };

  const cardMarkup = (item) => `
    <article class="anime-tile" data-id="${escapeHtml(item.id)}" tabindex="0" role="button" aria-label="${escapeHtml(item.title)}の詳細を見る">
      ${poster(item)}
      <div class="tile-copy"><div><span>${item.year}</span><span>${item.episodes}話</span></div><h3>${escapeHtml(item.title)}</h3><p>${item.genres.map(escapeHtml).join('・')}</p></div>
    </article>`;

  const filteredCatalog = () => {
    const query = normalize(search.value);
    return anime.filter((item) => {
      const genreMatch = activeGenre === 'all' || item.genres.includes(activeGenre);
      const haystack = normalize([item.title, item.reading, item.summary, ...item.genres, ...item.characters.map((person) => person.name)].join(' '));
      return genreMatch && (!query || haystack.includes(query));
    });
  };

  const renderCatalog = () => {
    const matches = filteredCatalog();
    grid.innerHTML = matches.slice(0, displayLimit).map(cardMarkup).join('');
    catalogStatus.textContent = `${Math.min(matches.length, displayLimit)} / ${matches.length}作品`;
    showMore.hidden = displayLimit >= matches.length;
  };

  const openDialog = (item) => {
    if (!dialog || !dialogContent || !item) return;
    dialogContent.innerHTML = `
      <div class="dialog-layout">${poster(item, 'anime-poster--dialog')}<div class="dialog-copy">
        <p class="dialog-index">${item.year} / ${escapeHtml(item.format)}</p><h2>${escapeHtml(item.title)}</h2>
        <div class="genre-row">${item.genres.map((genre) => `<span>${escapeHtml(genre)}</span>`).join('')}</div>
        <p class="result-summary">${escapeHtml(item.summary)}</p>
        <h3>主なキャラクター</h3><ul class="dialog-characters">${characterMarkup(item)}</ul>
        <div class="result-actions">${actionLinks(item)}</div>
      </div></div>`;
    if (typeof dialog.showModal === 'function') dialog.showModal(); else dialog.setAttribute('open', '');
    track('anime_detail_open', {anime_title: item.title});
  };

  const share = async (item) => {
    const text = `アニメルーレットの結果は「${item.title}」でした。`;
    const url = `${location.origin}${location.pathname}#roulette`;
    if (navigator.share) {
      try { await navigator.share({title: 'SEKAI LOG', text, url}); return; }
      catch (error) { if (error.name === 'AbortError') return; }
    }
    window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent(`${text}\n${url}`)}`, '_blank', 'noopener');
  };

  const initDailyGame = () => {
    const hintList = $('#hint-list');
    const choicesNode = $('#game-choices');
    if (!hintList || !choicesNode) return;
    const date = new Date();
    const key = `${date.getFullYear()}-${date.getMonth() + 1}-${date.getDate()}`;
    const yesterday = new Date(date); yesterday.setDate(date.getDate() - 1);
    const yesterdayKey = `${yesterday.getFullYear()}-${yesterday.getMonth() + 1}-${yesterday.getDate()}`;
    const seed = Number(key.replaceAll('-', ''));
    const answer = anime[seed % anime.length];
    const decoys = anime.filter((item) => item.id !== answer.id).sort((a, b) => ((seed * (anime.indexOf(a) + 3)) % 97) - ((seed * (anime.indexOf(b) + 3)) % 97)).slice(0, 3);
    const choices = [...decoys, answer].sort((a, b) => ((seed + anime.indexOf(a) * 13) % 31) - ((seed + anime.indexOf(b) * 13) % 31));
    const hints = [`${answer.year}年スタート`, `ジャンルは「${answer.genres.slice(0, 2).join('・')}」`, answer.hint];
    hintList.innerHTML = hints.map((hint, index) => `<div><span>ヒント${index + 1}</span><p>${escapeHtml(hint)}</p></div>`).join('');
    choicesNode.innerHTML = choices.map((item) => `<button type="button" data-answer="${escapeHtml(item.id)}">${escapeHtml(item.title)}</button>`).join('');
    const played = localStorage.getItem('sekai-log-daily') === key;
    const streak = Number(localStorage.getItem('sekai-log-streak') || 0);
    $('#game-streak').textContent = String(streak);
    if (played) $('#game-message').textContent = '今日は回答済み。また明日！';
    choicesNode.addEventListener('click', (event) => {
      const button = event.target.closest('[data-answer]');
      if (!button || localStorage.getItem('sekai-log-daily') === key) return;
      const correct = button.dataset.answer === answer.id;
      choicesNode.querySelectorAll('[data-answer]').forEach((choice) => {
        choice.disabled = true;
        if (choice.dataset.answer === answer.id) choice.classList.add('is-correct');
      });
      if (!correct) button.classList.add('is-wrong');
      $('#game-message').textContent = correct ? `正解！「${answer.title}」です。` : `残念。答えは「${answer.title}」でした。`;
      localStorage.setItem('sekai-log-daily', key);
      const lastPlayed = localStorage.getItem('sekai-log-last-daily');
      const nextStreak = correct ? (lastPlayed === yesterdayKey ? streak + 1 : 1) : 0;
      localStorage.setItem('sekai-log-streak', String(nextStreak));
      localStorage.setItem('sekai-log-last-daily', key);
      $('#game-streak').textContent = String(nextStreak);
      track('daily_game_answer', {correct, anime_title: answer.title});
    });
  };

  [genreFilter, moodFilter, timeFilter].forEach((filter) => filter.addEventListener('change', paintWheel));
  $('#clear-filters').addEventListener('click', () => {
    genreFilter.value = 'all'; moodFilter.value = 'all'; timeFilter.value = 'all'; paintWheel();
  });
  spinButton.addEventListener('click', spin);
  search.addEventListener('input', () => { displayLimit = 12; renderCatalog(); });
  chips.forEach((button) => button.addEventListener('click', () => {
    chips.forEach((chip) => chip.classList.remove('is-active'));
    button.classList.add('is-active');
    activeGenre = button.dataset.genre;
    displayLimit = 12;
    renderCatalog();
  }));
  showMore.addEventListener('click', () => { displayLimit += 12; renderCatalog(); });
  grid.addEventListener('click', (event) => {
    if (event.target.closest('[data-image-credit]')) return;
    const tile = event.target.closest('.anime-tile');
    if (tile) openDialog(anime.find((item) => item.id === tile.dataset.id));
  });
  grid.addEventListener('keydown', (event) => {
    if ((event.key === 'Enter' || event.key === ' ') && event.target.classList.contains('anime-tile')) {
      event.preventDefault(); event.target.click();
    }
  });
  document.addEventListener('click', (event) => {
    const link = event.target.closest('[data-action]');
    if (link) track('outbound_click', {destination: link.dataset.action, anime_title: link.dataset.title});
  });
  if (dialogClose) dialogClose.addEventListener('click', () => dialog.close());
  if (dialog) dialog.addEventListener('click', (event) => { if (event.target === dialog) dialog.close(); });

  paintWheel();
  renderCatalog();
  initDailyGame();
})();
