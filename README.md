# Second Brain Starter Kit

Стартовый набор «Claude Code как второй мозг + рабочий ассистент» от
[PaloAlto AI Research Lab](https://github.com/Palo-Alto-AI-Research-Lab).
Это рабочая система, которой мы пользуемся сами каждый день, — очищенная от
личных данных и урезанная до переносимого ядра: **метод, не данные**.

## Что внутри

| Папка / файл | Что это |
|---|---|
| `SEED.md` | Стартовое сообщение для ПЕРВОЙ сессии Claude Code — с него всё начинается |
| `BOOTSTRAP-CLAUDE.md` | Инструкция для самого Claude: как установить и адаптировать набор |
| `CLAUDE-EXTERNAL.md` | Наши рабочие принципы (стиль работы ассистента) — основа для твоего CLAUDE.md |
| `skills/` | **Все 101 скилл-команда**, которыми система работает каждый день — карта: [`skills/INDEX.md`](skills/INDEX.md). Личные данные в примерах заменены на вымышленные ([как именно](docs/WHAT-IS-SHARED.md)) |
| `templates/` | Шаблоны заметок второго мозга (концепты, решения, ревью недели/месяца) |
| `crm-template/` | CRM: markdown «карточка = файл» + [движок](crm-template/ENGINE.md) со скорингом теплоты и безопасным исходящим, с демо-данными |
| `docs/` | Как пользоваться CLAUDE.md, онбординг, что шарится |
| [`HANDOVER.md`](HANDOVER.md) | **Уже есть свой флот агентов?** Слепок всей системы и карта наших репозиториев — точка входа для тебя и твоей модели |


📖 **Вики репозитория** — карта на английском: [что здесь на самом деле лежит](https://github.com/Palo-Alto-AI-Research-Lab/second-brain-starter-kit/wiki) · [архитектура (4 слоя)](https://github.com/Palo-Alto-AI-Research-Lab/second-brain-starter-kit/wiki/Architecture) · [первая неделя](https://github.com/Palo-Alto-AI-Research-Lab/second-brain-starter-kit/wiki/First-week) · [как адаптировать под свою машину](https://github.com/Palo-Alto-AI-Research-Lab/second-brain-starter-kit/wiki/Adapting-it-to-your-machine)

## Быстрый старт (10 минут)

1. Подписка Claude Pro или Max → установи Claude Code:
   `npm install -g @anthropic-ai/claude-code` (нет npm → Mac: `brew install node`, Windows: nodejs.org).
2. Запусти `claude`, залогинься по подписке.
3. Установи [Obsidian](https://obsidian.md) — смотреть свой второй мозг глазами.
4. Склонируй этот репозиторий: `git clone https://github.com/Palo-Alto-AI-Research-Lab/second-brain-starter-kit.git`
   (или скачай zip кнопкой Code → Download ZIP).
5. Открой `SEED.md`, подставь своё имя и вставь текст первым сообщением в Claude Code.
   Дальше Claude сделает всё сам по `BOOTSTRAP-CLAUDE.md`.

## Принципы, на которых это стоит

- **Второй мозг = перестань терять полезное.** Каждое решение, договорённость,
  идея → заметка в волт, с перелинковкой.
- **АК-47:** самое простое решение, которое владелец может починить сам.
- **Квитанции:** ассистент доказывает, что сохранил («записал X → заметка Y»),
  а не говорит «понял».
- **Рутина, повторённая дважды, становится скиллом** — командой `/имя`.
- **Приватность:** всё живёт локально у тебя; деньги / удаление / отправка
  вовне — только с твоего явного ОК.

## Дорожная карта

**Сейчас — [v0.1.0](https://github.com/Palo-Alto-AI-Research-Lab/second-brain-starter-kit/releases/tag/v0.1.0).**
101 скилл, 246 движков, которые эти скиллы реально зовут, шаблоны заметок, CRM-движок
со скорингом теплоты и безопасным исходящим, `SEED.md` + `BOOTSTRAP-CLAUDE.md` для первой
сессии и `HANDOVER.md` для тех, у кого уже есть свой флот агентов.

**Дальше** — в том порядке, в котором взялись бы сами:

- **Починить онбординг** ([#1](https://github.com/Palo-Alto-AI-Research-Lab/second-brain-starter-kit/issues/1)):
  `ONBOARDING.md` ведёт новичка через пять папок, которых в этом репозитории нет. Первый
  экран для чужого человека — и он врёт; это верх очереди.
- **Проверка «поставил и работает» на чужой машине.** Сейчас доказательство одно — мы
  пользуемся этим сами каждый день. Это использование, а не тест: чужой машины никто не видел.
- **Английская версия README.** Карта на английском уже есть в
  [вики](https://github.com/Palo-Alto-AI-Research-Lab/second-brain-starter-kit/wiki), сам
  README пока только по-русски.

Каждое заметное изменение выходит новым релизом, поэтому
[лента релизов](https://github.com/Palo-Alto-AI-Research-Lab/second-brain-starter-kit/releases) —
честная запись того, что в наборе на самом деле уже есть, а не история коммитов.

## Кто из ИИ здесь работал

Проект делает команда «человек + ИИ», и это видно в истории коммитов: Claude
пишет большую часть кода, Codex и Grok его ревьюят, Gemini приносит ресёрч.
Модель отмечается в коммите **только если её вывод реально изменил содержимое
этого коммита** — декоративных подписей не ставим. Единое правило лаборатории:
[AI-CONTRIBUTORS.md](https://github.com/Palo-Alto-AI-Research-Lab/.github/blob/main/AI-CONTRIBUTORS.md).

## Лицензия и происхождение

Метод открыт — берите, адаптируйте, делитесь. Секретов и персональных данных
в наборе нет (прогнан автоматическим секрет-сканером). Вопросы и идеи — в
Issues.

## Связаться с нами

Вопросы, истории с полей или хотите развернуть это у себя:

- 💬 WhatsApp: **+1 341 222 9178**
- 🐦 X: [@Tony_Stef_](https://x.com/Tony_Stef_)
- 📣 Telegram: [@ClawRus](https://t.me/ClawRus) (RU) · [@ClawEng](https://t.me/ClawEng) (EN)
- 🌐 [palo-alto.ai](https://palo-alto.ai) · [Palo Alto AI Research Lab](https://github.com/Palo-Alto-AI-Research-Lab)
