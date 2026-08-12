(() => {
  'use strict';

  const menuButton = document.querySelector('.menu-button');
  const navigation = document.getElementById('site-nav');
  if (menuButton && navigation) {
    menuButton.addEventListener('click', () => {
      const open = navigation.classList.toggle('is-open');
      menuButton.setAttribute('aria-expanded', String(open));
      menuButton.textContent = open ? 'CLOSE' : 'MENU';
    });
  }

  const articleInput = document.getElementById('article-filter');
  const articleCards = Array.from(document.querySelectorAll('#article-list .story-card'));
  const articleStatus = document.getElementById('filter-status');
  const articleEmpty = document.getElementById('empty-state');
  const normalize = (value) => String(value || '').normalize('NFKC').toLowerCase().trim();
  if (articleInput && articleCards.length) {
    const filterArticles = () => {
      const query = normalize(articleInput.value);
      let visible = 0;
      articleCards.forEach((card) => {
        const matched = !query || normalize(card.dataset.search).includes(query);
        card.hidden = !matched;
        if (matched) visible += 1;
      });
      if (articleStatus) articleStatus.textContent = `${visible}件の記事`;
      if (articleEmpty) articleEmpty.hidden = visible !== 0;
    };
    articleInput.addEventListener('input', filterArticles);
  }

  const dataNode = document.getElementById('anime-data');
  if (!dataNode) return;

  let anime = [];
  try { anime = JSON.parse(dataNode.textContent); } catch (error) { console.error(error); return; }

  const $ = (selector) => document.querySelector(selector);
  const result = $('#anime-result');
  const genreFilter = $('#genre-filter');
  const moodFilter = $('#mood-filter');
  const timeFilter = $('#time-filter');
  const selectorNote = $('#selector-note');
  const spinButton = $('#spin-button');
  const orbit = $('#roulette-orbit');
  const grid = $('#anime-grid');
  const search = $('#anime-search');
  const catalogStatus = $('#catalog-status');
  const showMore = $('#show-more');
  const chips = Array.from(document.querySelectorAll('#catalog-chips button'));
  const dialog = $('#anime-dialog');
  const dialogContent = $('#dialog-content');
  const dialogClose = $('#dialog-close');
  const tag = 'sekailog-22';
  let current = anime[0];
  let activeGenre = 'all';
  let displayLimit = 12;
  let spinTimer = null;

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
  const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));

  const poster = (item, size = '') => `
    <div class="anime-poster ${size}" style="--poster:${escapeHtml(item.accent)}" aria-hidden="true">
      <span class="poster-grid"></span><b>${escapeHtml(initials(item))}</b><small>${escapeHtml(item.year)}</small><i>${escapeHtml(item.genres[0])}</i>
    </div>`;

  const characterMarkup = (item) => item.characters.map((person, index) => `
    <li><span>0${index + 1}</span><div><b>${escapeHtml(person.name)}</b><p>${escapeHtml(person.role)}</p></div></li>`).join('');

  const actionLinks = (item, location) => `
    <a class="action-primary" href="${escapeHtml(item.official_url)}" target="_blank" rel="noopener" data-action="official" data-title="${escapeHtml(item.title)}">公式サイト <span>↗</span></a>
    <a href="${escapeHtml(watchUrl(item))}" target="_blank" rel="noopener" data-action="watch" data-title="${escapeHtml(item.title)}">視聴先を探す <span>↗</span></a>
    <a href="${escapeHtml(amazonUrl(item))}" target="_blank" rel="nofollow sponsored noopener" data-action="amazon" data-title="${escapeHtml(item.title)}">原作をAmazonで見る <small>広告</small><span>↗</span></a>
    ${location === 'result' ? '<button type="button" id="share-result">結果を共有 <span>↗</span></button>' : ''}`;

  const renderResult = (item, animate = false) => {
    current = item;
    result.style.setProperty('--poster', item.accent);
    result.classList.toggle('is-revealing', animate);
    result.innerHTML = `
      <div class="result-poster-wrap">${poster(item, 'anime-poster--large')}<button class="save-button" type="button" data-save="${escapeHtml(item.id)}" aria-label="${escapeHtml(item.title)}を保存">＋ SAVE</button></div>
      <div class="result-copy">
        <div class="result-meta"><span>${escapeHtml(item.format)}</span><span>${item.year}</span><span>${item.episodes}話 / ${totalLabel(item)}</span></div>
        <p class="result-kicker">YOUR NEXT WORLD IS</p>
        <h2>${escapeHtml(item.title)}</h2>
        <div class="genre-row">${item.genres.map((genre) => `<span>${escapeHtml(genre)}</span>`).join('')}</div>
        <p class="result-summary">${escapeHtml(item.summary)}</p>
        <details class="character-details"><summary>主なキャラクター <span>＋</span></summary><ul>${characterMarkup(item)}</ul></details>
        <div class="result-actions">${actionLinks(item, 'result')}</div>
        <p class="affiliate-mini">Amazonリンクはアソシエイト広告です。価格・在庫はリンク先でご確認ください。</p>
      </div>`;
    const shareButton = $('#share-result');
    if (shareButton) shareButton.addEventListener('click', () => share(item));
    updateSavedButtons();
  };

  const candidates = () => {
    const genre = genreFilter.value;
    const mood = moodFilter.value;
    const time = timeFilter.value;
    return anime.filter((item) =>
      (genre === 'all' || item.genres.includes(genre)) &&
      (mood === 'all' || item.moods.includes(mood)) &&
      timeMatch(item, time)
    );
  };

  const spin = () => {
    if (spinTimer) return;
    const pool = candidates();
    if (!pool.length) {
      selectorNote.textContent = 'その組み合わせでは候補がありません。条件を一つゆるめてください。';
      selectorNote.classList.add('is-error');
      return;
    }
    selectorNote.classList.remove('is-error');
    spinButton.disabled = true;
    orbit.classList.add('is-spinning');
    result.classList.add('is-loading');
    let ticks = 0;
    spinTimer = window.setInterval(() => {
      const preview = pool[Math.floor(Math.random() * pool.length)];
      orbit.querySelector('span').textContent = initials(preview);
      ticks += 1;
      if (ticks >= 10) {
        window.clearInterval(spinTimer);
        spinTimer = null;
        const selected = pool[Math.floor(Math.random() * pool.length)];
        renderResult(selected, true);
        orbit.querySelector('span').textContent = '世界';
        orbit.classList.remove('is-spinning');
        result.classList.remove('is-loading');
        spinButton.disabled = false;
        selectorNote.textContent = `${pool.length}作品から「${selected.title}」を選びました。`;
        $('#result-count').textContent = `${String(anime.indexOf(selected) + 1).padStart(2, '0')} / ${String(anime.length).padStart(2, '0')}`;
        track('roulette_complete', { anime_title: selected.title, candidate_count: pool.length });
        result.scrollIntoView({behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'center'});
      }
    }, 75);
    track('roulette_start', { genre: genreFilter.value, mood: moodFilter.value, time: timeFilter.value });
  };

  const cardMarkup = (item) => `
    <article class="anime-tile" data-id="${escapeHtml(item.id)}" tabindex="0" role="button" aria-label="${escapeHtml(item.title)}の詳細を見る">
      ${poster(item)}
      <div class="tile-copy"><div><span>${item.year}</span><span>${item.episodes}話</span></div><h3>${escapeHtml(item.title)}</h3><p>${item.genres.map(escapeHtml).join(' / ')}</p></div>
      <button class="tile-save save-button" data-save="${escapeHtml(item.id)}" type="button" aria-label="${escapeHtml(item.title)}を保存">＋</button>
    </article>`;

  const filteredCatalog = () => {
    const query = normalize(search.value);
    return anime.filter((item) => {
      const genreMatch = activeGenre === 'all' || item.genres.includes(activeGenre);
      const haystack = normalize([item.title, item.reading, item.summary, ...item.genres, ...item.characters.map((p) => p.name)].join(' '));
      return genreMatch && (!query || haystack.includes(query));
    });
  };

  const renderCatalog = () => {
    const matches = filteredCatalog();
    grid.innerHTML = matches.slice(0, displayLimit).map(cardMarkup).join('');
    catalogStatus.textContent = `${matches.length}作品中 ${Math.min(matches.length, displayLimit)}作品を表示`;
    showMore.hidden = displayLimit >= matches.length;
    updateSavedButtons();
  };

  const openDialog = (item) => {
    dialogContent.innerHTML = `
      <div class="dialog-layout">${poster(item, 'anime-poster--dialog')}<div class="dialog-copy">
        <p class="dialog-index">WORLD FILE / ${String(anime.indexOf(item) + 1).padStart(2, '0')}</p><h2>${escapeHtml(item.title)}</h2>
        <div class="result-meta"><span>${escapeHtml(item.format)}</span><span>${item.year}</span><span>${item.episodes}話 / ${totalLabel(item)}</span></div>
        <div class="genre-row">${item.genres.map((genre) => `<span>${escapeHtml(genre)}</span>`).join('')}</div>
        <p class="result-summary">${escapeHtml(item.summary)}</p>
        <h3>CHARACTERS</h3><ul class="dialog-characters">${characterMarkup(item)}</ul>
        <div class="result-actions">${actionLinks(item, 'dialog')}</div>
      </div></div>`;
    if (typeof dialog.showModal === 'function') dialog.showModal(); else dialog.setAttribute('open', '');
    track('anime_detail_open', { anime_title: item.title });
  };

  const savedIds = () => {
    try { return JSON.parse(localStorage.getItem('sekai-log-saved') || '[]'); } catch { return []; }
  };
  const toggleSave = (id) => {
    const saved = new Set(savedIds());
    if (saved.has(id)) saved.delete(id); else saved.add(id);
    localStorage.setItem('sekai-log-saved', JSON.stringify([...saved]));
    updateSavedButtons();
    track('anime_save', { anime_id: id, saved: saved.has(id) });
  };
  const updateSavedButtons = () => {
    const saved = new Set(savedIds());
    document.querySelectorAll('[data-save]').forEach((button) => {
      const active = saved.has(button.dataset.save);
      button.classList.toggle('is-saved', active);
      if (button.classList.contains('tile-save')) button.textContent = active ? '✓' : '＋';
      else button.textContent = active ? '✓ SAVED' : '＋ SAVE';
    });
  };

  const share = async (item) => {
    const text = `SEKAI LOGのルーレットで「${item.title}」が選ばれました。`;
    const url = `${location.origin}${location.pathname}#result`;
    if (navigator.share) {
      try { await navigator.share({title: item.title, text, url}); track('share_result', {anime_title: item.title, method: 'native'}); return; } catch (error) { if (error.name === 'AbortError') return; }
    }
    window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent(`${text}\n${url}`)}`, '_blank', 'noopener');
    track('share_result', {anime_title: item.title, method: 'x'});
  };

  const initDailyGame = () => {
    const date = new Date();
    const key = `${date.getFullYear()}-${date.getMonth() + 1}-${date.getDate()}`;
    const yesterday = new Date(date); yesterday.setDate(date.getDate() - 1);
    const yesterdayKey = `${yesterday.getFullYear()}-${yesterday.getMonth() + 1}-${yesterday.getDate()}`;
    const seed = Number(key.replaceAll('-', ''));
    const answer = anime[seed % anime.length];
    const decoys = anime.filter((item) => item.id !== answer.id).sort((a, b) => ((seed * (anime.indexOf(a) + 3)) % 97) - ((seed * (anime.indexOf(b) + 3)) % 97)).slice(0, 3);
    const choices = [...decoys, answer].sort((a, b) => ((seed + anime.indexOf(a) * 13) % 31) - ((seed + anime.indexOf(b) * 13) % 31));
    const hints = [`${answer.year}年に始まった${answer.format}`, `ジャンルは「${answer.genres.slice(0, 2).join('・')}」`, answer.hint];
    $('#hint-list').innerHTML = hints.map((hint, index) => `<div><span>HINT 0${index + 1}</span><p>${escapeHtml(hint)}</p></div>`).join('');
    $('#game-choices').innerHTML = choices.map((item) => `<button type="button" data-answer="${escapeHtml(item.id)}">${escapeHtml(item.title)}</button>`).join('');
    const played = localStorage.getItem('sekai-log-daily') === key;
    const streak = Number(localStorage.getItem('sekai-log-streak') || 0);
    $('#game-streak').textContent = String(streak);
    if (played) $('#game-message').textContent = '今日は回答済みです。明日また挑戦してください。';
    $('#game-choices').addEventListener('click', (event) => {
      const button = event.target.closest('[data-answer]');
      if (!button || localStorage.getItem('sekai-log-daily') === key) return;
      const correct = button.dataset.answer === answer.id;
      document.querySelectorAll('[data-answer]').forEach((choice) => {
        choice.disabled = true;
        if (choice.dataset.answer === answer.id) choice.classList.add('is-correct');
      });
      if (!correct) button.classList.add('is-wrong');
      $('#game-message').textContent = correct ? `正解。「${answer.title}」です。` : `惜しい。正解は「${answer.title}」でした。`;
      localStorage.setItem('sekai-log-daily', key);
      const lastPlayed = localStorage.getItem('sekai-log-last-daily');
      const nextStreak = correct ? (lastPlayed === yesterdayKey ? streak + 1 : 1) : 0;
      localStorage.setItem('sekai-log-streak', String(nextStreak));
      localStorage.setItem('sekai-log-last-daily', key);
      $('#game-streak').textContent = String(nextStreak);
      track('daily_game_answer', {correct, anime_title: answer.title});
    });
  };

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
    const save = event.target.closest('[data-save]');
    if (save) { event.stopPropagation(); toggleSave(save.dataset.save); return; }
    const tile = event.target.closest('.anime-tile');
    if (tile) openDialog(anime.find((item) => item.id === tile.dataset.id));
  });
  grid.addEventListener('keydown', (event) => {
    if ((event.key === 'Enter' || event.key === ' ') && event.target.classList.contains('anime-tile')) { event.preventDefault(); event.target.click(); }
  });
  result.addEventListener('click', (event) => {
    const save = event.target.closest('[data-save]');
    if (save) toggleSave(save.dataset.save);
  });
  document.addEventListener('click', (event) => {
    const link = event.target.closest('[data-action]');
    if (link) track('outbound_click', {destination: link.dataset.action, anime_title: link.dataset.title});
  });
  dialogClose.addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', (event) => { if (event.target === dialog) dialog.close(); });

  renderResult(current);
  renderCatalog();
  initDailyGame();
})();
