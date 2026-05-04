/* console.js — syntax highlighting + live cursor + occasional re-render
   Looks for <pre class="console" data-lang="json|yaml|plain"> blocks.
   Tokens get spans. Last value of `confidence`, `resolution_confidence`
   or marked tokens get a blinking caret to suggest a running pipeline.
*/
(function () {
  const LIVE_KEYS = ['confidence', 'resolution_confidence', 'strength'];

  function escapeHtml(s) {
    return s.replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
  }

  function highlightJSON(src) {
    let s = escapeHtml(src);
    const stash = [];
    const stashTok = (html) => {
      stash.push(html);
      return `\u0000${stash.length - 1}\u0000`;
    };
    // comments
    s = s.replace(/(\/\/[^\n]*)/g, (_m, c) => stashTok(`<span class="tok-com">${c}</span>`));
    // strings (key vs value)
    s = s.replace(/"((?:[^"\\\n]|\\.)*)"(\s*:)?/g, (_m, body, colon) => {
      if (colon) return stashTok(`<span class="tok-key">"${body}"</span>`) + colon;
      return stashTok(`<span class="tok-str">"${body}"</span>`);
    });
    // numbers
    s = s.replace(/(\b-?\d+\.?\d*)([,\s\]\}])/g, (_m, num, tail) => stashTok(`<span class="tok-num">${num}</span>`) + tail);
    // bools/null
    s = s.replace(/\b(true|false|null)\b/g, (_m, w) => stashTok(`<span class="tok-bool">${w}</span>`));
    // punctuation
    s = s.replace(/([{}\[\],])/g, (_m, p) => stashTok(`<span class="tok-punct">${p}</span>`));
    // restore
    s = s.replace(/\u0000(\d+)\u0000/g, (_m, i) => stash[+i]);
    return s;
  }

  function highlightYAML(src) {
    let s = escapeHtml(src);
    // Use placeholders to avoid regexes matching tokens inside emitted spans.
    const stash = [];
    const stashTok = (html) => {
      stash.push(html);
      return `\u0000${stash.length - 1}\u0000`;
    };
    // comments first
    s = s.replace(/(#[^\n]*)/g, (_m, c) => stashTok(`<span class="tok-com">${c}</span>`));
    // quoted strings next
    s = s.replace(/"((?:[^"\\\n]|\\.)*)"/g, (_m, body) => stashTok(`<span class="tok-str">"${body}"</span>`));
    // keys (key: at start of line / after dash)
    s = s.replace(/^(\s*-?\s*)([a-zA-Z_][a-zA-Z0-9_]*)(:)/gm,
      (_m, lead, key, col) => `${lead}${stashTok(`<span class="tok-key">${key}</span>`)}${stashTok(`<span class="tok-punct">${col}</span>`)}`);
    // restore
    s = s.replace(/\u0000(\d+)\u0000/g, (_m, i) => stash[+i]);
    return s;
  }

  function applyChrome(pre) {
    if (pre.dataset.chrome === 'off') return;
    if (pre.querySelector('.console__chrome')) return;
    const path = pre.dataset.path || 'fabula://pipeline';
    const time = new Date();
    const stamp = time.toISOString().replace('T', ' ').slice(0, 19) + 'Z';
    const chrome = document.createElement('div');
    chrome.className = 'console__chrome';
    chrome.innerHTML = `<span class="dot"></span><span class="console__path">${path}</span><span class="console__time">${stamp}</span>`;
    pre.insertBefore(chrome, pre.firstChild);
  }

  function liveTouch(pre) {
    // find numbers next to live keys and wrap them
    pre.querySelectorAll('.tok-key').forEach(k => {
      const txt = k.textContent.replace(/"/g, '');
      if (!LIVE_KEYS.includes(txt)) return;
      let n = k.nextSibling;
      // walk forward for the next tok-num span
      while (n && !(n.classList && n.classList.contains('tok-num'))) {
        n = n.nextSibling;
      }
      if (n && n.classList.contains('tok-num')) {
        n.classList.add('tok-live-target');
      }
    });
  }

  function reRender(pre) {
    if (document.documentElement.dataset.consoleAnim === 'off') return;
    const targets = pre.querySelectorAll('.tok-live-target');
    if (!targets.length) return;
    targets.forEach(t => {
      const base = parseFloat(t.dataset.base || t.textContent);
      if (!t.dataset.base) t.dataset.base = base;
      // wobble within ±0.01 to suggest re-extraction
      const jitter = (Math.random() - 0.5) * 0.012;
      const next = Math.max(0, Math.min(1, base + jitter));
      const decimals = (t.dataset.base.split('.')[1] || '').length || 2;
      t.textContent = next.toFixed(decimals);
      t.classList.add('tok-live');
      setTimeout(() => t.classList.remove('tok-live'), 1200);
    });
  }

  function processBlock(pre) {
    const raw = pre.textContent;
    const lang = pre.dataset.lang || 'json';
    const html = lang === 'yaml' ? highlightYAML(raw)
              : lang === 'plain' ? escapeHtml(raw)
              : highlightJSON(raw);
    pre.innerHTML = html;
    applyChrome(pre);
    liveTouch(pre);
  }

  function init() {
    const blocks = document.querySelectorAll('pre.console');
    blocks.forEach(processBlock);
    // Stagger re-render across blocks so different ones blink at different times
    blocks.forEach((b, i) => {
      setInterval(() => reRender(b), 4500 + i * 1700);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
