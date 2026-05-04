/* tweaks.js — Tweaks panel for the Fabula site
   Exposes: accent color, type scale, console live cursor, marginalia.
*/
(function () {
  const DEFAULTS = (typeof TWEAK_DEFAULTS !== 'undefined' && TWEAK_DEFAULTS) || {
    accent: '#7a2a26',
    consoleAnim: true,
    marginalia: true,
    scale: 'comfortable'
  };

  // Backwards-compat: older saved files may still have denseTrustStrip set
  if ('denseTrustStrip' in DEFAULTS && !('marginalia' in DEFAULTS)) {
    DEFAULTS.marginalia = true;
  }

  const state = {
    accent: DEFAULTS.accent ?? '#7a2a26',
    consoleAnim: DEFAULTS.consoleAnim ?? true,
    marginalia: DEFAULTS.marginalia ?? true,
    scale: DEFAULTS.scale ?? 'comfortable'
  };

  function apply() {
    const root = document.documentElement;
    root.style.setProperty('--accent', state.accent);
    // also recompute the muted accent token so trust strip / etc. stay in family
    root.dataset.consoleAnim = state.consoleAnim ? 'on' : 'off';
    root.dataset.marginalia = state.marginalia ? 'on' : 'off';
    const scaleMap = { compact: '17px', comfortable: '19px', loose: '21px' };
    document.body.style.fontSize = scaleMap[state.scale] || '19px';
  }

  function persist() {
    try {
      window.parent.postMessage({
        type: '__edit_mode_set_keys',
        edits: {
          accent: state.accent,
          consoleAnim: state.consoleAnim,
          marginalia: state.marginalia,
          scale: state.scale
        }
      }, '*');
    } catch (e) {}
  }

  function buildPanel() {
    const panel = document.createElement('aside');
    panel.id = 'tweaks-panel';
    panel.style.cssText = `
      position: fixed; right: 1.2rem; bottom: 1.2rem; z-index: 200;
      width: 280px; background: oklch(97.5% 0.008 75);
      border: 1px solid oklch(85% 0.012 70);
      font-family: 'JetBrains Mono', ui-monospace, monospace;
      font-size: 0.78rem; color: oklch(20% 0.012 60);
      box-shadow: 0 8px 24px oklch(20% 0.012 60 / 0.08);
      display: none;
    `;
    panel.innerHTML = `
      <header style="display:flex;justify-content:space-between;align-items:center;padding:0.7rem 0.9rem;border-bottom:1px solid oklch(85% 0.012 70);">
        <strong style="font-weight:500;letter-spacing:0.06em;text-transform:uppercase;font-size:0.7rem;">Tweaks</strong>
        <button id="tweaks-close" aria-label="Close" style="background:transparent;border:0;color:oklch(55% 0.014 60);cursor:pointer;font-size:1rem;line-height:1;">×</button>
      </header>
      <div style="padding:0.9rem;display:flex;flex-direction:column;gap:1rem;">

        <label style="display:flex;flex-direction:column;gap:0.4rem;">
          <span style="color:oklch(55% 0.014 60);font-size:0.7rem;letter-spacing:0.04em;">Accent color</span>
          <div style="display:flex;gap:0.4rem;flex-wrap:wrap;">
            ${[
              ['oxblood', '#7a2a26'],
              ['ink', '#2a2a2a'],
              ['cobalt', '#1f3a78'],
              ['forest', '#2a4f33'],
              ['amber', '#9a6a1a']
            ].map(([n, c]) => `<button data-accent="${c}" title="${n}" style="width:24px;height:24px;border-radius:50%;border:1px solid oklch(85% 0.012 70);background:${c};cursor:pointer;padding:0;"></button>`).join('')}
          </div>
        </label>

        <label style="display:flex;flex-direction:column;gap:0.4rem;">
          <span style="color:oklch(55% 0.014 60);font-size:0.7rem;letter-spacing:0.04em;">Type scale</span>
          <div style="display:flex;border:1px solid oklch(85% 0.012 70);">
            ${['compact','comfortable','loose'].map(s => `<button data-scale="${s}" style="flex:1;padding:0.4rem;border:0;background:transparent;cursor:pointer;font-family:inherit;font-size:0.72rem;color:inherit;">${s}</button>`).join('')}
          </div>
        </label>

        <label style="display:flex;align-items:center;justify-content:space-between;gap:0.6rem;">
          <span style="color:oklch(55% 0.014 60);font-size:0.72rem;">Console live cursor</span>
          <input id="tweak-anim" type="checkbox" ${state.consoleAnim ? 'checked' : ''} />
        </label>

        <label style="display:flex;align-items:center;justify-content:space-between;gap:0.6rem;">
          <span style="color:oklch(55% 0.014 60);font-size:0.72rem;">Marginalia <span style="color:oklch(55% 0.014 60); font-style:italic;">(§ marks &amp; footnotes)</span></span>
          <input id="tweak-marg" type="checkbox" ${state.marginalia ? 'checked' : ''} />
        </label>

      </div>
    `;
    document.body.appendChild(panel);

    panel.querySelectorAll('[data-accent]').forEach(b => b.addEventListener('click', () => {
      state.accent = b.dataset.accent;
      apply(); persist();
    }));
    panel.querySelectorAll('[data-scale]').forEach(b => {
      b.addEventListener('click', () => {
        state.scale = b.dataset.scale;
        apply(); persist();
        panel.querySelectorAll('[data-scale]').forEach(x => {
          x.style.background = x.dataset.scale === state.scale ? 'oklch(20% 0.012 60)' : 'transparent';
          x.style.color = x.dataset.scale === state.scale ? 'oklch(97.5% 0.008 75)' : 'inherit';
        });
      });
      if (b.dataset.scale === state.scale) {
        b.style.background = 'oklch(20% 0.012 60)';
        b.style.color = 'oklch(97.5% 0.008 75)';
      }
    });
    panel.querySelector('#tweak-anim').addEventListener('change', e => {
      state.consoleAnim = e.target.checked; apply(); persist();
    });
    panel.querySelector('#tweak-marg').addEventListener('change', e => {
      state.marginalia = e.target.checked; apply(); persist();
    });
    panel.querySelector('#tweaks-close').addEventListener('click', () => {
      panel.style.display = 'none';
      try { window.parent.postMessage({ type: '__edit_mode_dismissed' }, '*'); } catch (e) {}
    });
    return panel;
  }

  function init() {
    apply();
    let panel = null;
    window.addEventListener('message', (e) => {
      const d = e.data || {};
      if (d.type === '__activate_edit_mode') {
        if (!panel) panel = buildPanel();
        panel.style.display = 'block';
      } else if (d.type === '__deactivate_edit_mode') {
        if (panel) panel.style.display = 'none';
      }
    });
    try {
      window.parent.postMessage({ type: '__edit_mode_available' }, '*');
    } catch (e) {}
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
