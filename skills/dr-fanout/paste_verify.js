/* dr-fanout / paste_verify.js — детерминированная вставка-и-проверка промпта в композер DR.
 * Цель: сделать ПУСТОЙ Send технически невозможным. Лечит корень бага 2026-07-10
 * (ChatGPT-hires: execCommand insertText не сел → DR стартовал на пустом → отчёт про смертность).
 *
 * ⭐ 2026-07-17 (FLEE-03) — КОРЕНЬ бага Grok-сабмита (07-10/07-17) найден:
 *   Grok 4.5 сменил композер на TipTap/ProseMirror contenteditable (`div.tiptap.ProseMirror`).
 *   Видимый <textarea> в который целил старый каскад — это СКРЫТОЕ ЗЕРКАЛО: nativeSetter в него
 *   возвращал ok:true, но React/ProseMirror-состояние из зеркала НЕ обновлялось → кнопка
 *   button[type=submit] не рендерилась, Enter=no-op, ран не стартовал (квота цела, но время потеряно).
 *   ФИКС: заполнять РЕАЛЬНЫЙ `.tiptap.ProseMirror` через СИНТЕТИЧЕСКИЙ paste-event
 *   (ClipboardEvent('paste', {clipboardData: DataTransfer})) → ProseMirror штатно адоптит текст →
 *   Submit-кнопка появляется enabled → клик стартует ран. Проверено вживую 17.07 (Grok FLEE-03).
 *   Старые методы (execCommand/nativeSetter/directSet) оставлены ФОЛБЭКОМ — UI ещё плывёт.
 *
 * Как звать (Claude-in-Chrome javascript_tool), подставив PROMPT и VENDOR:
 *   window.__drPasteVerify(PROMPT_STRING, "chatgpt"|"gemini"|"grok")
 * Возвращает КОМПАКТНЫЙ объект-вердикт:
 *   { ok:bool, method:str, gotLen:int, wantLen:int, headOK:bool, tailOK:bool, sel:str, reason:str }
 *
 * ⛔ ГЕЙТ: клик Send/Run разрешён ТОЛЬКО при ok===true. ok===false → повтор (макс 2), потом
 *    пропустить вендора, записать в леджер, пинг Антону. Квоту на пустой запуск не жечь.
 */
window.__drPasteVerify = function (prompt, vendor) {
  const V = (vendor || "").toLowerCase();

  // 1) Кандидаты-композеры по вендорам (UI плывёт — пробуем список, берём первый видимый).
  //    ⭐ ProseMirror/TipTap contenteditable — ПЕРВЫМ (это настоящий редактор); голый <textarea>
  //    у Grok/ChatGPT = скрытое зеркало, форма из него не обновляется (см. шапку). Оставляем
  //    textarea последним фолбэком на случай старой/иной верстки.
  const SELECTORS = {
    chatgpt: ['#prompt-textarea', 'div.ProseMirror[contenteditable="true"]', 'div[contenteditable="true"].ProseMirror', 'textarea[name="prompt-textarea"]', 'form textarea'],
    gemini:  ['div.ql-editor[contenteditable="true"]', 'rich-textarea .ql-editor', 'div[contenteditable="true"][role="textbox"]'],
    grok:    ['div.tiptap.ProseMirror[contenteditable="true"]', 'div.ProseMirror[contenteditable="true"]', 'div[contenteditable="true"].tiptap', 'div[contenteditable="true"]', 'textarea'],
  }[V] || ['div.ProseMirror[contenteditable="true"]', 'div[contenteditable="true"]', 'textarea'];

  const isVisible = (el) => !!(el && el.offsetParent !== null && el.getClientRects().length);
  let el = null, sel = '';
  for (const s of SELECTORS) {
    const cand = Array.from(document.querySelectorAll(s)).filter(isVisible);
    if (cand.length) { el = cand[cand.length - 1]; sel = s; break; }
  }
  if (!el) return { ok: false, reason: 'composer-not-found', vendor: V, tried: SELECTORS.join('|') };

  const isTextarea = el.tagName === 'TEXTAREA';
  // ProseMirror/TipTap contenteditable — нужен paste-event, а НЕ innerHTML-клобер (тот десинхронит PM-состояние).
  const isPM = !isTextarea && !!(el.classList && (el.classList.contains('ProseMirror') || el.classList.contains('tiptap')));
  const readText = () => (isTextarea ? el.value : el.innerText) || '';

  const selectAllInEl = () => {
    try {
      el.focus();
      const r = document.createRange();
      r.selectNodeContents(el);
      const s = window.getSelection();
      s.removeAllRanges();
      s.addRange(r);
    } catch (e) {}
  };

  // 2) Пере-фокус ОБЯЗАТЕЛЕН: клик по меню DR-режима крадёт фокус, вставка улетает в никуда.
  el.focus();
  el.click();
  el.focus();

  // 3) Очистить прежний ввод. Для ProseMirror НЕ трогаем innerHTML напрямую (это и есть корень бага —
  //    прямой DOM-клобер обходит модель PM) → выделяем всё и даём методам заменить выделение.
  try {
    if (isTextarea) { el.value = ''; }
    else if (isPM) { selectAllInEl(); }
    else { el.innerHTML = ''; document.execCommand('selectAll', false, null); document.execCommand('delete', false, null); }
  } catch (e) {}

  const fireInput = () => {
    el.dispatchEvent(new InputEvent('input', { bubbles: true, cancelable: true, inputType: 'insertText', data: prompt }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  };

  // 4) КАСКАД вставки — до первого, что реально сел. Порядок от «родного» к «грубому».
  const methods = [];

  // (a0) ⭐ СИНТЕТИЧЕСКИЙ PASTE-EVENT — для ProseMirror/TipTap contenteditable (Grok 4.5+, ChatGPT).
  //      ProseMirror адоптит текст своим штатным обработчиком paste → React-состояние обновляется →
  //      Submit-кнопка рендерится. Это ЕДИНСТВЕННЫЙ путь, что реально включает отправку у Grok 4.5.
  if (!isTextarea) {
    methods.push(['pasteEvent', () => {
      selectAllInEl();               // заменяем всё содержимое, а не дописываем
      const dt = new DataTransfer();
      dt.setData('text/plain', prompt);
      el.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true }));
    }]);
  }

  // (a) execCommand insertText — работает на contenteditable и часто на textarea.
  methods.push(['execCommand', () => {
    el.focus();
    if (!isTextarea) selectAllInEl();
    document.execCommand('insertText', false, prompt);
    fireInput();
  }]);

  // (b) Нативный React-сеттер + InputEvent — для КОНТРОЛИРУЕМОГО <textarea> (React игнорит el.value=).
  if (isTextarea) {
    methods.push(['nativeSetter', () => {
      const proto = window.HTMLTextAreaElement.prototype;
      const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
      setter.call(el, prompt);
      fireInput();
    }]);
  } else {
    // (b') Для contenteditable — построить параграфы узлами (обход TrustedHTML/CSP у Gemini-Quill).
    methods.push(['nodeParagraphs', () => {
      el.focus();
      el.innerHTML = '';
      const lines = String(prompt).split('\n');
      for (const line of lines) {
        const p = document.createElement('p');
        if (line.length) p.textContent = line; else p.appendChild(document.createElement('br'));
        el.appendChild(p);
      }
      fireInput();
    }]);
  }

  // (c) Грубый фолбэк: прямая установка + input (последняя надежда).
  methods.push(['directSet', () => {
    el.focus();
    if (isTextarea) el.value = prompt; else el.textContent = prompt;
    fireInput();
  }]);

  // 5) Прогон каскада + СВЕРКА после каждого. Успех = длина совпала и хвост совпал.
  //    Для ProseMirror сверка читается из el.innerText (не из textarea-зеркала).
  const want = String(prompt);
  const wantLen = want.length;
  const norm = (s) => s.replace(/\r/g, '').replace(/ /g, ' ');
  const wantN = norm(want);
  const headN = wantN.slice(0, 40);
  const tailN = wantN.slice(-40);

  let last = { ok: false, reason: 'no-method-ran' };
  for (const [name, fn] of methods) {
    try { fn(); } catch (e) { last = { ok: false, method: name, reason: 'threw:' + (e && e.message) }; continue; }
    const gotN = norm(readText());
    const gotLen = gotN.length;
    const headOK = gotN.indexOf(headN) !== -1;
    const tailOK = gotN.indexOf(tailN) !== -1;
    // допускаем небольшой люфт длины (±2%) на нормализацию переводов строк
    const lenOK = gotLen >= Math.floor(wantLen * 0.98);
    const ok = lenOK && headOK && tailOK;
    last = { ok, method: name, gotLen, wantLen, headOK, tailOK, sel, isPM, vendor: V, reason: ok ? 'verified' : 'mismatch' };
    if (ok) break;
  }
  window.__drLastVerify = last;
  return last;
};
