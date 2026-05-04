/* nav.js — verb tabs + nav active state */
(function () {
  function initVerbTabs() {
    const root = document.querySelector('[data-verbs]');
    if (!root) return;
    const btns = root.querySelectorAll('.verbs__btn');
    const panels = root.querySelectorAll('.verbs__panel');
    btns.forEach(b => b.addEventListener('click', () => {
      btns.forEach(x => x.setAttribute('aria-selected', x === b ? 'true' : 'false'));
      panels.forEach(p => {
        if (p.dataset.verb === b.dataset.verb) p.setAttribute('data-active', '');
        else p.removeAttribute('data-active');
      });
    }));
  }

  function init() { initVerbTabs(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
