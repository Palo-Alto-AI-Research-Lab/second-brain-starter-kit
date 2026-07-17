---
name: defuddle
description: Clean web→markdown extraction via kepano's defuddle CLI (engine of Obsidian Web Clipper) — turn any article URL into a vault-ready markdown note WITHOUT ads/nav/comments, saving 40-60% tokens vs WebFetch. Trigger on "/defuddle <url>", "вытащи статью <url>", "статью в волт", "чистый импорт страницы", "clean import this page", or PREFER it over WebFetch whenever the task is "read/ingest a normal web article/blog/docs page". NOT for .md URLs (WebFetch direct), not for JS-heavy apps/paywalls (fallback WebFetch/Chrome). Installed 2026-07-04 per Anton's "+" (2026-06-28). Canon: dr-friends-starter-kit-2026-07-02 (vault), memory always-archive-artifacts-to-vault.
---

# /defuddle — чистый web→markdown

CLI `defuddle` (kepano, MIT, v0.19.1) установлен глобально через npm. Node — единственная зависимость.

## Команды
```bash
# статья → чистый markdown в stdout
defuddle parse <url> --markdown

# с frontmatter (title/author/published/domain) — для волта
defuddle parse <url> --markdown --frontmatter

# сразу в файл
defuddle parse <url> --markdown --frontmatter --output "<path>.md"
```

## Флоу «статью в волт»
1. `defuddle parse <url> --markdown --frontmatter` → черновик.
2. Дальше стандартный ingest: заметка в волт (provenance `origin: external`!), реиндекс, перелинковка ≥1 (правила `always-archive-artifacts-to-vault`, `no-orphan-notes-rule`).

## ⚠️ Гадости (проверено /tt 2026-07-04)
- **exit-код = 0 даже при ошибке** («Error: fetch failed» печатается, но код успеха). В скриптах проверять stdout на `^Error:`, НЕ exit-код.
- Пустой ввод → невнятная ошибка destructure (тоже exit 0).
- CLI machine-local: на другой машине сначала `npm install -g defuddle` (node нужен). Скилл синкается кластером, бинарь — нет.

## Когда НЕ defuddle
`.md`-URL → WebFetch напрямую; JS-тяжёлые SPA, пейволы, логины → WebFetch или Claude-in-Chrome.
