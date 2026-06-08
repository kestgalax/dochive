# Dochive CLI — шпаргалка для зеркалирования

Полная документация: [docs/USAGE.md](../../docs/USAGE.md) (EN), [docs/USAGE.ru.md](../../docs/USAGE.ru.md) (RU).

## Команды

| Команда | Назначение |
|---------|------------|
| `dochive structure` | Сохранить `_catalog/structure.yaml` до зеркалирования контента |
| `dochive mirror` | Скачать/конвертировать страницы в Markdown + каталоги |
| `dochive catalog --root` | Показать пути `_catalog/*.yaml` |
| `dochive query --root --text` | Лексический поиск по зеркалу |
| `dochive publish --root` | Git commit/push зеркала |

## Общие флаги (structure и mirror)

| Флаг | По умолчанию | Заметка |
|------|--------------|---------|
| `--source` | — | URL, файл `.html` или каталог |
| `--out` | — | Корень вывода; внутри появится `<source_root_name>/` |
| `--scope` | `subtree` | `domain` — только с согласия пользователя |
| `--structure-mode` | `auto` | MadCap: `toc` / `links` |
| `--max-depth` | 3 | Глубина link-crawl |
| `--max-pages` | 500 | Лимит страниц за прогон |
| `--include-url-prefix` | — | Повторяемый; shared-ветки вне subtree |
| `--source-type` | `auto` | `confluence` + `--auth bearer` |
| `--anti-bot` | `basic` | `off` для диагностики |

## Только mirror

| Флаг | По умолчанию |
|------|--------------|
| `--render-js` | off (нужен `[crawl4ai]` + Playwright) |
| `--save-assets` | пусто; пример: `images`, `images,videos` |
| `--content-selector` | — |
| `--exclude-selector` | — |
| `--noise-line` | повторяемый |
| `--no-clean-markdown` | cleanup включён |
| `--image-size-mode` | `intrinsic`; для скриншотов: `max-width` + `--image-max-width 900` |
| `--image-inline-max-px` | 48 |

## Каталоги зеркала (`<mirror_site_root>/_catalog/`)

| Файл | Содержание |
|------|------------|
| `structure.yaml` | Дерево навигации, placeholders |
| `pages.yaml` | Страницы, пути, хеши |
| `links.yaml` | Внутренние/внешние ссылки |
| `errors.yaml` | Предупреждения и ошибки |
| `sync.yaml` | added/changed/unchanged/deleted |
| `summary.yaml` | Сводка, счётчики |

Placeholder в Markdown: заголовок + «Раздел ожидает отдельного зеркалирования» + строка `Источник: <url>`.

## Пороги стратегии (навык)

- < ~50 страниц в ветке → один mirror.
- ~50–300 → mirror по URL верхних узлов TOC, тот же `--out`.
- > ~300 → те же ветки + `--max-pages` 80–150, повтор до заполнения placeholders.

## Partial mirror (с 0.2.4)

- Повторные прогоны в тот же `--out` сохраняют уже записанные разделы и каталог.
- Переписывание internal links использует `_catalog/pages.yaml` целиком, не только URL текущего crawl.
- CLI печатает прогресс на stderr (`Reading catalog...`, `Writing N pages...`, …).
