---
name: fb-reply
description: Read who commented on Anton's recent Facebook posts and post PERSONALIZED replies through his real logged-in Chrome (Claude-in-Chrome MCP = low-ban-risk live-tab path), draft-first and rate-limit-guarded. Trigger on "/fb-reply", "ответь на комменты", "ответь комментаторам", "разбери комментарии под постами", "reply to my facebook comments", "ответь в фейсбуке на комменты". Replying on your OWN posts is the LOW-risk task (B), but FB still bans on tempo: every reply is gated by fb_guard.py (<=40/day, >=5 min apart, no bursts). Replies are written in Anton's voice (Opus), each one varied & specific to the comment (identical text = spam flag). NEVER click "View more comments" on shared/reposted posts (it navigates away -- account-safety). Draft-first: show Anton the batch, post only on his "+". Phase-1 sibling of /fb-post; engine guard = ~/.claude/scripts/fb_guard.py. Canon: Decision Memo 2026-06-28 (FB skill set) + memory chrome-autonomy-self-drive.
---

# /fb-reply — ответить на комментарии под постами Антона (безопасно)

**Зачем.** Под постами копятся комменты (часто ценные — как контр-тезис Ковач про tailscale). Отвечать на СВОИ посты — низко-рисковая задача, но Facebook всё равно банит за ТЕМП. Поэтому: читаем безопасно, пишем персонально голосом Антона, постим по одному с паузами под счётчиком.

**Главные правила (из Deep-Research #32):**
- **Темп решает, не «бот/человек».** Каждый ответ проходит `fb_guard check reply`: ≤40/день, ≥5 мин между ответами, без серий подряд. Guard физически не даст перебрать.
- **Каждый ответ персональный и разный** (Opus, голос Антона). Одинаковый текст многим = спам-флаг → бан.
- **Draft-first:** показываю Антону пачку черновиков, постю только после `+`.
- **Account safety:** НЕ кликать «View more comments» на репостах — уводит со страницы. Читаем то, что прогрузилось под оригиналом.

---

## 0. Предохранитель — статус на старте
```bash
python "$USERPROFILE/.claude/scripts/fb_guard.py" status
```
Покажет, сколько ответов уже сегодня и не на паузе ли. Если `reply` уже на дневном лимите — скажи Антону, отложи.

## 1. Браузер + чтение комментаторов (без рискованных кликов)
> Строго ЛОКАЛЬНО, живая вкладка, логин не трогаем. Chrome-MCP подключён? (`list_connected_browsers`).
> ⛔ IP-гейт (anton 16.07): комментинг FB — ТОЛЬКО с хаба `HUB-1` (постоянный IP). На другой машине НЕ отвечать — задачу текстом на хаб. Канон: `reglament-ip-sensitive-deystviya-tolko-s-haba`.

1. Открой нужный пост Антона (он даёт ссылку, или идём по `facebook.com/<профиль>` → его последние посты).
2. **Извлекай комментаторов В САМОЙ СТРАНИЦЕ** (имена/ссылки FB скрывает через MCP-границу → матчим и фильтруем внутри страницы, наружу отдаём только безопасный текст). Через `mcp__Claude_in_Chrome__javascript_tool`:
   ```js
   const out = [];
   const seen = new Set();
   document.querySelectorAll('div[role="article"][aria-label]').forEach(a => {
     const al = a.getAttribute('aria-label') || '';
     if (!/^Comment by|^Ответ от|^Комментар/i.test(al)) return;          // только комменты
     const blocks = [...a.querySelectorAll('div[dir="auto"]')]
       .map(d => (d.innerText || '').trim()).filter(Boolean);
     const text = (blocks.sort((x, y) => y.length - x.length)[0] || '').slice(0, 500);
     if (!text || seen.has(text)) return;
     seen.add(text);
     const link = a.querySelector('a[role="link"][href]');               // профиль автора
     const handle = link ? (new URL(link.href).pathname.replace(/\//g,'')) : '';
     const hasImg = !!a.querySelector('img[src*="scontent"],img[src*="fbcdn"]');
     out.push({ handle, text, hasImg });                                  // handle = username, не имя
   });
   out;
   ```
   Вернётся список `{handle, text, hasImg}` — без скрытых строк, можно показывать.
3. **Виртуализация:** если комментов мало, мягко проскролль область комментов (`computer` scroll вниз по странице, НЕ кликая кнопки-экспандеры) и повтори §1.2. На посте-РЕПОСТЕ кнопку «View more» НЕ жми.
4. **⚠️ ОБЯЗАТЕЛЬНО разверни свёрнутые ветки ПЕРЕД выбором «кому отвечать» (урок 2026-07-05):** FB прячет существующие ответы под «View N replies» — Антон часто УЖЕ ответил сам, снаружи этого не видно (дубль = позор + спам-сигнал). На СВОЁМ посте инлайн-экспандеры веток безопасны (не путать с «View more comments» на репостах). Через JS: кликнуть все тогглы `/View (\d+ )?repl/i`, подождать ~3с, затем собрать `aria-label^="Reply by Anton Dziatkovskii to <Имя>"` → список УЖЕ отвеченных; отвечать только тем, кого в списке нет. В прогоне 2026-07-05 это отсеяло 7 из 8 «кандидатов».

## 2. Черновики ответов (Opus, персонально)
Для каждого коммента, на который стоит ответить, напиши **отдельный** короткий ответ голосом Антона: обратись по имени/контексту коммента, без шаблона, тексты разные. Собери пачку и покажи Антону:
```
1. [Игорь, deios] коммент: «…tailscale…»   →  черновик: «Игорь, в точку. Покажешь, как у тебя транспорт устроен?»
2. ...
```
Жди `+` (или правки). Это draft-first gate.

## 3. Постинг по одному, под счётчиком — ПРОВЕРЕННАЯ МЕХАНИКА (2026-07-04)
> Отлажено вживую: ответ Антона на коммент Alex Kaplunovich лёг как threaded-reply. Ключевые грабли ниже — НЕ обходи их заново.

Для КАЖДОГО одобренного ответа:
1. **Guard-gate:** `python "$USERPROFILE/.claude/scripts/fb_guard.py" check reply`
   - `BLOCKED ...` (exit 3) → СТОП постить. Скажи Антону, сколько ждать / что в очереди. Остаток — позже/следующим заходом.
   - `OK reply` → продолжай.
2. **Открой пост** на `www.facebook.com/<profile>/posts/<pfbid>` (рендерится как модалка `role="dialog"` — это норма, работаем в ней).
   ⚠️ **Проверь, что реально попал на нужный пост** (грабля 2026-07-27): FB умеет увести вкладку на СОСЕДНИЙ пост, а комменты прошлой страницы остаются висеть в DOM скрытыми → цель находится, а ответ уходит не туда. Лечение: после навигации сверить `location.href`/`document.title`, а цель искать ТОЛЬКО среди видимых (`a.offsetParent!==null`).
3. **Скриншот** (`computer` screenshot) чтобы увидеть раскладку и НАЙТИ ГЛАЗАМИ ссылку «Reply». ⚠️ Скрин на тяжёлой модалке иногда виснет («captureScreenshot timed out / renderer frozen») — просто ПОВТОРИ скрин, он отвечает через раз, это не фатально.
4. **Кликни по РЕАЛЬНОЙ ТЕКСТОВОЙ ссылке «Reply»** в строке «Like · Reply · Hide» под нужным комментом — ПО КООРДИНАТЕ из скриншота. ⛔ ГРАБЛЯ: `find` возвращает «Reply»-ref, который при клике уводит фокус на КНОПКУ CLOSE модалки (инлайн-поле НЕ открывается). Кликай визуально по координате текста «Reply», НЕ по find-ref.
5. Откроется инлайн-композер ответа с @упоминанием автора. **Ставь фокус через JS, не кликом по координате** (урок 2026-07-20): модалка реflow-ит между скриншотом и кликом → клик попадает в тело коммента, `type` уходит в никуда (дважды подряд). Рабочий рецепт:

> ⛔ **ГРАБЛИ ВВОДА И ОТПРАВКИ (2026-07-27, доказано вживую — ЭТО ТЕПЕРЬ ОСНОВНОЙ ПУТЬ):**
> **(1) `computer type` СЪЕДАЕТ ПРОБЕЛЫ И ТОЧКИ.** «жду. звёздочку поставлю первым» легло в поле как `ждузвёздочкупоставлюпервым`. Опубликуй не проверив = позор под своим постом. **Вместо `type` вставляй текст через JS** (пробелы сохраняются, @упоминание цело):
> ```js
> f.focus();
> const r=document.createRange(); r.selectNodeContents(f); r.collapse(false);
> const s=getSelection(); s.removeAllRanges(); s.addRange(r);
> document.execCommand('insertText', false, '<текст ответа>');
> ```
> **(2) Дискретные нажатия клавиш (`key Return`, `key BackSpace`) НЕ ДОЛЕТАЮТ до композера** — между MCP-вызовами фокус не держится, поле остаётся с текстом, публикации нет (и Backspace ничего не чистит). **Отправка зависит от ТИПА композера, их ДВА:**
> - **Композер верхнего уровня** (ответ на top-level коммент): есть кнопка — жми её из JS:
> ```js
> let box=f, up=0; while(box && up<8){box=box.parentElement; up++; if(box.querySelector('[aria-label="Post comment"]')) break;}
> box.querySelector('[aria-label="Post comment"]').click();
> ```
> - **Композер вложенной ветки** (ответ на чей-то reply): кнопки `Post comment` НЕТ вообще (проверено подъёмом на 12 уровней — только эмодзи/GIF/стикеры). Отправка = синтетический Enter, **обязательно в ОДНОМ вызове с `focus()`**, иначе фокус теряется и ничего не улетит:
> ```js
> f.focus();
> const r=document.createRange(); r.selectNodeContents(f); r.collapse(false);
> const s=getSelection(); s.removeAllRanges(); s.addRange(r);
> const o={key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true,cancelable:true,composed:true};
> f.dispatchEvent(new KeyboardEvent('keydown',o));
> f.dispatchEvent(new KeyboardEvent('keypress',o));
> f.dispatchEvent(new KeyboardEvent('keyup',o));
> ```
> Универсальный порядок: сначала ищем кнопку, нет кнопки → синтетический Enter.
> **(3) Надо стереть уже набранное** — не Backspace'ом, а выделением в ОДНОМ JS-вызове: каретка в конец → `s.modify('extend','backward','character')` × N → проверить `s.toString().length===N` и что в выделение НЕ попало имя из @упоминания (иначе abort) → `execCommand('insertText', ...)` затрёт выделенное.
> **Вывод одной строкой:** весь цикл (открыть композер → вставить → отправить) делается через JS; `computer` в этом скилле нужен только для скриншотов.

   ```js
   const f=[...document.querySelectorAll('[contenteditable="true"]')]
     .find(e=>/Reply to <Имя>/.test(e.getAttribute('aria-label')||''));
   f.scrollIntoView({block:'center'}); f.focus();
   const r=document.createRange(); r.selectNodeContents(f); r.collapse(false);   // каретка в конец, после @упоминания
   const s=getSelection(); s.removeAllRanges(); s.addRange(r);
   ```
   затем вставить шутку (≤5–7 слов, голос Антона/Opus) через `execCommand('insertText')` — НЕ `computer type`, см. грабли выше. Композер открывать тоже через JS: внутри нужного `article` кликнуть элемент с `innerText==='Reply'`.
6. **Проверь через JS** (скрин может висеть — DOM надёжнее): среди `[contenteditable="true"]` есть поле с `aria-label="Reply to <Имя>"`, и в нём твой текст (упоминание + шутка). Только тогда отправляй.
7. **Отправь:** JS-клик по `[aria-label="Post comment"]` (см. грабли выше). ⛔ `computer key Return` НЕ работает — не долетает до поля.
8. **Подтверди публикацию через JS:** появился `div[role="article"][aria-label^="Reply by <моё-имя> to <Имя>'s comment"]` с твоим текстом И поле ответа очистилось (`innerText===''`). Только это = «опубликовано».
9. `python "$USERPROFILE/.claude/scripts/fb_guard.py" record reply`
10. Guard держит паузу ≥5 мин до следующего — НЕ обходи ускорением (темп = главная причина бана).

## 4. Доложи
Что ответили, что в очереди (ждёт паузы/лимита), сколько сегодня `reply N/40`.

---

## Стоп-краны (account safety)
- Любое предупреждение FB / checkpoint / «слишком часто» → **немедленно СТОП**, доложи Антону, без ретрай-спама.
- НЕ кликать «View more comments» / навигационные кнопки на репостах (уводят со страницы).
- НЕ постить одинаковый текст разным людям.
- Логин/2FA не трогаем.

## Связанное
- `/fb-post` — публикация постов (Фаза 1, тот же guard).
- `/fb-dm` — личка комментаторам (Фаза 2, строгий draft-first; пока не построен).
- Счётчик: `~/.claude/scripts/fb_guard.py`. Голос: `fb-diary-voice`.
- Канон: Decision Memo 2026-06-28, `chrome-autonomy-self-drive`, `browser-work-on-peers-not-hub`.
