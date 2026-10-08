/*
 * Ask the Archive — chat widget.
 *
 * Vanilla JS, no build step (the site vendors everything). Talks to
 * POST /api/chat/ (SSE over fetch + ReadableStream — POST body rules out
 * EventSource) and GET /api/chat/suggestions/.
 *
 * State is per-series in sessionStorage: trimmed history plus the server's
 * sanitized tool_context echo (stateless server; see chat/views.py).
 */
(function () {
  'use strict';

  var ctxEl = document.getElementById('fabula-chat-context');
  if (!ctxEl) return;
  var pageCtx;
  try { pageCtx = JSON.parse(ctxEl.textContent); } catch (e) { return; }

  var SERIES = pageCtx.series || '';
  var STORE_KEY = 'fabula-chat:' + (SERIES || 'catalog');
  var HISTORY_CAP = 8;

  var ICONS = {
    book: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 7v14"/><path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/></svg>',
    send: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></svg>',
    close: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>'
  };

  /* ---------- state ---------- */

  function loadState() {
    try {
      var raw = sessionStorage.getItem(STORE_KEY);
      if (raw) return JSON.parse(raw);
    } catch (e) { /* fall through */ }
    return { history: [], toolContext: [] };
  }
  function saveState() {
    state.history = state.history.slice(-HISTORY_CAP);
    try { sessionStorage.setItem(STORE_KEY, JSON.stringify(state)); }
    catch (e) { /* storage full/blocked — stateless chat still works */ }
  }
  var state = loadState();
  var streaming = false;

  /* ---------- markdown-lite (escape first, then transform) ---------- */

  function escapeHtml(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function renderMarkdown(text) {
    var html = escapeHtml(text);
    // Links: keep only internal catalog paths; external/invented → plain text.
    html = html.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, function (m, label, url) {
      if (/^\/[a-z]/.test(url)) {
        return '<a href="' + url + '">' + label + '</a>';
      }
      return label;
    });
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/(^|[\s(])\*([^*\n]+)\*/g, '$1<em>$2</em>');

    var blocks = html.split(/\n{2,}/);
    return blocks.map(function (block) {
      var lines = block.split('\n');
      var isList = lines.length > 0 && lines.every(function (l) {
        return /^\s*[-•]\s+/.test(l) || l.trim() === '';
      });
      if (isList) {
        return '<ul>' + lines.filter(function (l) { return l.trim(); })
          .map(function (l) {
            return '<li>' + l.replace(/^\s*[-•]\s+/, '') + '</li>';
          }).join('') + '</ul>';
      }
      return '<p>' + block.replace(/\n/g, '<br>') + '</p>';
    }).join('');
  }

  /* ---------- DOM scaffold ---------- */

  function el(tag, className, html) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (html !== undefined) node.innerHTML = html;
    return node;
  }

  var launcher = el('button', 'fchat-launcher',
    ICONS.book + '<span>ask the archive</span>');
  launcher.type = 'button';
  launcher.setAttribute('aria-expanded', 'false');
  launcher.setAttribute('aria-label', 'Open Ask the Archive chat');

  var panel = el('aside', 'fchat-panel');
  panel.hidden = true;
  panel.setAttribute('role', 'dialog');
  panel.setAttribute('aria-label', 'Ask the Archive');

  var header = el('div', 'fchat-header');
  header.appendChild(el('span', 'fchat-header__eyebrow', 'ask the archive'));
  header.appendChild(el('span', 'fchat-header__series',
    escapeHtml(pageCtx.series_title || 'fabula')));
  var closeBtn = el('button', 'fchat-close', ICONS.close);
  closeBtn.type = 'button';
  closeBtn.setAttribute('aria-label', 'Close chat');
  header.appendChild(closeBtn);

  var messagesEl = el('div', 'fchat-messages');
  messagesEl.setAttribute('aria-live', 'polite');

  var chipsEl = el('div', 'fchat-chips');

  var composer = el('form', 'fchat-composer');
  var input = el('textarea', 'fchat-input');
  input.rows = 1;
  input.placeholder = 'Ask about ' + (pageCtx.series_title || 'the archive') + '…';
  input.setAttribute('aria-label', 'Your question');
  var sendBtn = el('button', 'fchat-send', ICONS.send);
  sendBtn.type = 'submit';
  sendBtn.setAttribute('aria-label', 'Send');
  composer.appendChild(input);
  composer.appendChild(sendBtn);

  panel.appendChild(header);
  panel.appendChild(messagesEl);
  panel.appendChild(chipsEl);
  panel.appendChild(composer);
  document.body.appendChild(launcher);
  document.body.appendChild(panel);

  /* ---------- message rendering ---------- */

  function scrollToEnd() { messagesEl.scrollTop = messagesEl.scrollHeight; }

  function addMessage(role, text) {
    var node = el('div', 'fchat-msg fchat-msg--' + role);
    node.innerHTML = renderMarkdown(text);
    messagesEl.appendChild(node);
    scrollToEnd();
    return node;
  }

  function addActivity(tool, args) {
    var label = tool;
    var argBits = [];
    Object.keys(args || {}).forEach(function (k) {
      var v = String(args[k]);
      if (v.length > 28) v = v.slice(0, 28) + '…';
      argBits.push(v);
    });
    if (argBits.length) label += ' · ' + argBits.join(', ');
    var node = el('div', 'fchat-activity', escapeHtml(label));
    messagesEl.appendChild(node);
    scrollToEnd();
    return node;
  }

  function addRichLinks(links) {
    var wrap = el('div', 'fchat-links');
    links.forEach(function (link) {
      var card = el('a', 'fchat-link-card fchat-link-card--' + link.kind);
      card.href = link.url;
      card.innerHTML =
        '<div class="fchat-link-card__kind">' + escapeHtml(link.kind) + '</div>' +
        '<div class="fchat-link-card__title">' + escapeHtml(link.title) + '</div>' +
        (link.subtitle
          ? '<div class="fchat-link-card__sub">' + escapeHtml(link.subtitle) + '</div>'
          : '');
      wrap.appendChild(card);
    });
    messagesEl.appendChild(wrap);
    scrollToEnd();
  }

  function setChips(chips) {
    chipsEl.innerHTML = '';
    (chips || []).forEach(function (chip) {
      var node;
      if (chip.url) {
        node = el('a', 'fchat-chip', escapeHtml(chip.label) + ' ↗');
        node.href = chip.url;
      } else {
        node = el('button', 'fchat-chip', escapeHtml(chip.label));
        node.type = 'button';
        node.addEventListener('click', function () { send(chip.send); });
      }
      chipsEl.appendChild(node);
    });
  }

  /* ---------- SSE reader ---------- */

  function parseSSE(buffer, onEvent) {
    // Returns unconsumed remainder of buffer.
    var chunks = buffer.split('\n\n');
    var remainder = chunks.pop();
    chunks.forEach(function (chunk) {
      var eventName = 'message';
      var dataLines = [];
      chunk.split('\n').forEach(function (line) {
        if (line.indexOf('event:') === 0) eventName = line.slice(6).trim();
        else if (line.indexOf('data:') === 0) dataLines.push(line.slice(5).trim());
      });
      var data = dataLines.join('\n');
      if (data === '[DONE]') { onEvent('done', null); return; }
      if (!data) return;
      try { onEvent(eventName, JSON.parse(data)); }
      catch (e) { /* malformed frame — skip */ }
    });
    return remainder;
  }

  function send(text) {
    text = (text || '').trim();
    if (!text || streaming) return;

    streaming = true;
    sendBtn.disabled = true;
    input.value = '';
    autosize();
    setChips([]);

    addMessage('user', text);
    state.history.push({ role: 'user', content: text });
    saveState();

    var assistantNode = null;
    var assistantText = '';
    var activityNode = null;

    function ensureAssistantNode() {
      if (!assistantNode) {
        assistantNode = addMessage('assistant', '');
        assistantNode.classList.add('fchat-msg--streaming');
      }
      return assistantNode;
    }
    function clearActivity() {
      if (activityNode) { activityNode.remove(); activityNode = null; }
    }
    function finish() {
      streaming = false;
      sendBtn.disabled = false;
      clearActivity();
      if (assistantNode) assistantNode.classList.remove('fchat-msg--streaming');
      if (assistantText) {
        state.history.push({ role: 'assistant', content: assistantText });
        saveState();
      }
      input.focus();
    }

    fetch('/api/chat/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        series: SERIES,
        history: state.history.slice(0, -1).slice(-HISTORY_CAP),
        page_context: pageCtx,
        tool_context: state.toolContext || []
      })
    }).then(function (resp) {
      if (!resp.ok) {
        return resp.json().catch(function () { return {}; })
          .then(function (body) {
            throw new Error(body.error || ('The archive returned ' + resp.status + '.'));
          });
      }
      var reader = resp.body.getReader();
      var decoder = new TextDecoder();
      var buffer = '';

      function onEvent(name, data) {
        if (name === 'content') {
          clearActivity();
          assistantText += data.text;
          ensureAssistantNode().innerHTML = renderMarkdown(assistantText);
          scrollToEnd();
        } else if (name === 'tool_start') {
          clearActivity();
          activityNode = addActivity(data.tool, data.args);
        } else if (name === 'rich_links') {
          addRichLinks(data.links);
        } else if (name === 'followups') {
          setChips(data.chips);
        } else if (name === 'metadata') {
          state.toolContext = data.tool_context || [];
          saveState();
        } else if (name === 'error') {
          clearActivity();
          addMessage('error', data.message);
        }
      }

      function pump() {
        return reader.read().then(function (step) {
          if (step.done) return;
          buffer += decoder.decode(step.value, { stream: true });
          buffer = parseSSE(buffer, onEvent);
          return pump();
        });
      }
      return pump();
    }).catch(function (err) {
      addMessage('error', err.message || 'The archive is unreachable.');
    }).then(finish, finish);
  }

  /* ---------- welcome ---------- */

  var welcomed = false;
  function welcome() {
    if (welcomed) return;
    welcomed = true;

    // Replay stored conversation for this series, if any.
    if (state.history.length) {
      state.history.forEach(function (m) {
        addMessage(m.role === 'user' ? 'user' : 'assistant', m.content);
      });
      scrollToEnd();
    } else {
      var intro = el('div', 'fchat-intro',
        'I’m the Archivist. I answer from Fabula’s narrative graph — ' +
        'events, characters, and the connections between them — and I’ll ' +
        'link every claim back to its page in the catalog.');
      messagesEl.appendChild(intro);
    }

    var params = new URLSearchParams({
      page_type: pageCtx.page_type || '',
      entity_name: pageCtx.entity_name || '',
      series: SERIES
    });
    fetch('/api/chat/suggestions/?' + params)
      .then(function (r) { return r.json(); })
      .then(function (body) { if (!streaming) setChips(body.chips || []); })
      .catch(function () { /* chips are decoration */ });
  }

  /* ---------- events ---------- */

  function openPanel() {
    panel.hidden = false;
    launcher.hidden = true;
    launcher.setAttribute('aria-expanded', 'true');
    welcome();
    input.focus();
  }
  function closePanel() {
    panel.hidden = true;
    launcher.hidden = false;
    launcher.setAttribute('aria-expanded', 'false');
    launcher.focus();
  }

  launcher.addEventListener('click', openPanel);
  closeBtn.addEventListener('click', closePanel);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && !panel.hidden) closePanel();
  });

  composer.addEventListener('submit', function (e) {
    e.preventDefault();
    send(input.value);
  });
  input.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send(input.value);
    }
  });

  function autosize() {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 104) + 'px';
  }
  input.addEventListener('input', autosize);
})();
