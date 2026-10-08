/* One terminal renderer for the server-backed prototype and compiled HTML. */
(() => {
  'use strict';
  const terminal = document.querySelector('[data-story-terminal]');
  if (!terminal) return;
  const $ = selector => document.querySelector(selector);
  const form = $('[data-command-form]');
  const input = form.elements.command;
  const transcript = $('[data-transcript]');
  const errorBox = $('[data-error]');
  const compiledNode = $('#compiled-world');
  const compiled = compiledNode ? JSON.parse(compiledNode.textContent) : null;
  let state = null;
  let busy = false;
  let retryRequest = null;
  let history = [];
  let historyIndex = 0;
  let draft = '';
  const clone = value => JSON.parse(JSON.stringify(value));
  const normalize = value => {
    let text = value.toLowerCase().trim().replace(/[.?!]+$/, '').replace(/\s+/g, ' ').trim();
    for (const prefix of ['please ', 'can i ', 'could i ', 'i want to ', "i'd like to "]) {
      if (text.startsWith(prefix)) text = text.slice(prefix.length);
    }
    return text;
  };
  const saveKey = compiled ? 'fabula-written-world:' + compiled.export_id : '';

  function offlineStart() {
    const fresh = clone(compiled.initial);
    for (const key of ['objects', 'authored', 'model_calls']) fresh[key] = compiled.saved[key];
    fresh.frozen = true;
    fresh.author_backend = 'offline';
    return fresh;
  }

  function offlineLoad() {
    try {
      const saved = JSON.parse(localStorage.getItem(saveKey));
      if (saved && compiled.states[saved.state_key] && Array.isArray(saved.transcript)) return saved;
    } catch (_) { /* Storage may be unavailable for file URLs. */ }
    return {...clone(compiled.saved), frozen: true, author_backend: 'offline'};
  }

  function offlineTurn(command) {
    let next = clone(state);
    const clean = normalize(command);
    if (clean === 'restart story') return offlineStart();
    const position = compiled.states[state.state_key];
    const action = command.trim() === '?' ? 'help' : (compiled.aliases[clean] || position.aliases[clean]);
    const result = position.actions[action];
    let blocks;
    if (result) {
      next.state_key = result.next;
      const destination = compiled.states[result.next];
      next.scene = destination.scene;
      next.props = destination.props;
      next.discoveries = destination.discoveries;
      next.suggestions = destination.suggestions;
      next.moves += result.move;
      next.replays += result.replay;
      blocks = result.blocks;
    } else {
      blocks = [{kind: 'system', text: 'That action is not available here. Try ' + state.suggestions.join(', ') + '.'}];
    }
    next.transcript.push({kind: 'command', text: command}, ...blocks);
    next.transcript = next.transcript.slice(-300);
    next.version += 1;
    return next;
  }

  function setBusy(value) {
    busy = value;
    input.disabled = value;
    document.querySelectorAll('[data-command-form] button, [data-suggestions] button, [data-action], [data-freeze], [data-restart], [data-author-switch]').forEach(button => {button.disabled = value;});
    if (value) $('[data-save]').textContent = 'working on your action…';
  }

  function addBlock(item, parent = transcript) {
    const node = document.createElement('p');
    const kinds = ['title', 'command', 'narration', 'discovery', 'system', 'hint', 'written', 'closure'];
    node.className = 'story-block story-block--' + (kinds.includes(item.kind) ? item.kind : 'narration');
    node.textContent = (item.kind === 'command' ? '> ' : '') + item.text;
    parent.appendChild(node);
  }

  function render(next, initial = false) {
    const nearBottom = transcript.scrollHeight - transcript.scrollTop - transcript.clientHeight < 90;
    const previousScroll = transcript.scrollTop;
    state = next;
    transcript.replaceChildren();
    for (const item of state.transcript) addBlock(item);
    transcript.scrollTop = initial
      ? (state.transcript.some(item => item.kind === 'command') ? transcript.scrollHeight : 0)
      : (nearBottom ? transcript.scrollHeight : previousScroll);
    $('[data-location]').textContent = state.scene.name;
    $('[data-moment]').textContent = state.scene.time + ' · Jonathan Harker';
    $('[data-discoveries]').textContent = state.discoveries.length;
    $('[data-moves]').textContent = state.moves;
    $('[data-written]').textContent = state.authored;
    $('[data-slot-count]').textContent = state.slot_count;
    $('[data-replays]').textContent = state.replays;
    $('[data-model-calls]').textContent = state.model_calls;
    $('[data-save]').textContent = compiled ? 'offline · saved on this device' : 'story saved';
    $('[data-author-label]').textContent = state.frozen ? 'written world · author off' : 'story mode · saved as you explore';
    $('[data-backend]').textContent = compiled
      ? 'Offline edition. These passages are already written; there is no author or model connection.'
      : state.author_backend === 'local'
        ? 'Local author: selects prepared prose variants. No LLM calls. This mode tests writing, persistence and replay without an API key.'
        : 'LLM author: OpenRouter writes bounded object descriptions and interprets unfamiliar phrasing. Accepted passages are saved. Narrative text is game adaptation.';
    const suggestions = $('[data-suggestions]');
    suggestions.replaceChildren();
    for (const command of state.suggestions) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = command;
      button.addEventListener('click', () => submit(command));
      suggestions.appendChild(button);
    }
    $('[data-objects]').replaceChildren();
    for (const object of state.objects) {
      const li = document.createElement('li');
      li.textContent = object.name + ' · written by ' + (object.backend === 'local' ? 'the local author' : 'the LLM author');
      $('[data-objects]').appendChild(li);
    }
    $('[data-freeze]').textContent = state.frozen ? 'enable author' : 'freeze this world';
    $('[data-freeze]').hidden = Boolean(compiled);
    $('[data-author-switch]').hidden = Boolean(compiled) || !state.llm_available;
    $('[data-author-switch]').textContent = state.author_backend === 'local' ? 'use live LLM author' : 'use local author';
    $('[data-download]').hidden = Boolean(compiled);
    history = state.transcript.filter(item => item.kind === 'command').map(item => item.text);
    historyIndex = history.length;
    if (!initial) {
      const lastCommand = state.transcript.map(item => item.kind).lastIndexOf('command');
      $('[data-announcement]').textContent = state.transcript.slice(lastCommand + 1).map(item => item.text).join('\n');
    }
    if (compiled) {
      try { localStorage.setItem(saveKey, JSON.stringify(state)); }
      catch (_) { $('[data-save]').textContent = 'offline · saving unavailable'; }
    }
  }

  function showError(message, canRetry) {
    errorBox.replaceChildren();
    errorBox.hidden = false;
    const text = document.createElement('span');
    text.textContent = message;
    errorBox.appendChild(text);
    if (canRetry) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = 'retry';
      button.addEventListener('click', () => retryRequest ? submit(retryRequest.command, retryRequest) : boot());
      errorBox.appendChild(button);
    }
  }

  async function submit(command, previousRequest = null) {
    if (busy || !state || !command.trim()) return;
    errorBox.hidden = true;
    const request = previousRequest || {command, version: state.version, request_id: crypto.randomUUID()};
    retryRequest = request;
    input.value = command;
    const nearBottom = transcript.scrollHeight - transcript.scrollTop - transcript.clientHeight < 90;
    addBlock({kind: 'command', text: command});
    if (nearBottom) transcript.scrollTop = transcript.scrollHeight;
    setBusy(true);
    try {
      let next;
      if (compiled) {
        next = offlineTurn(command);
      } else {
        const token = document.cookie.split('; ').find(row => row.startsWith('csrftoken='));
        const response = await fetch('/play/api/turn/', {
          method: 'POST', credentials: 'same-origin',
          headers: {'Content-Type': 'application/json', 'X-CSRFToken': token ? decodeURIComponent(token.slice(10)) : ''},
          body: JSON.stringify(request)
        });
        const data = await response.json();
        if (!response.ok) {
          if (data.state) { render(data.state); retryRequest = null; }
          throw new Error(data.error || 'The story could not be saved. Please retry.');
        }
        next = data;
      }
      render(next);
      input.value = '';
      draft = '';
      retryRequest = null;
    } catch (error) {
      render(state);
      $('[data-save]').textContent = 'action not confirmed';
      showError(error.message || 'Connection lost. Your last saved position is safe.', Boolean(retryRequest));
    } finally {
      setBusy(false);
      // Do not autofocus on page load. A submitted command keeps the
      // keyboard interaction in the terminal without scrolling the page.
      input.focus({preventScroll: true});
    }
  }

  form.addEventListener('submit', event => {event.preventDefault(); submit(input.value);});
  input.addEventListener('keydown', event => {
    if (!['ArrowUp', 'ArrowDown'].includes(event.key) || event.altKey || event.ctrlKey || event.metaKey || !history.length) return;
    event.preventDefault();
    if (historyIndex === history.length) draft = input.value;
    historyIndex = Math.max(0, Math.min(history.length, historyIndex + (event.key === 'ArrowUp' ? -1 : 1)));
    input.value = historyIndex === history.length ? draft : history[historyIndex];
  });
  document.querySelectorAll('[data-action]').forEach(button => button.addEventListener('click', () => submit(button.dataset.action)));
  $('[data-freeze]').addEventListener('click', () => submit(state.frozen ? 'enable author' : 'freeze world'));
  $('[data-author-switch]').addEventListener('click', () => submit(state.author_backend === 'local' ? 'use live author' : 'use local author'));
  $('[data-restart]').addEventListener('click', () => {
    if (!busy && state && confirm('Start the investigation again? Your written object descriptions will be kept.')) submit('restart story');
  });

  async function boot() {
    setBusy(true);
    errorBox.hidden = true;
    try {
      if (compiled) render(offlineLoad(), true);
      else {
        const response = await fetch('/play/api/state/', {credentials: 'same-origin'});
        if (!response.ok) throw new Error('The story is unavailable. Reload or try again.');
        render(await response.json(), true);
      }
      setBusy(false);
    } catch (error) {
      busy = false;
      $('[data-save]').textContent = 'could not open story';
      showError(error.message, true);
    }
  }
  boot();
})();
