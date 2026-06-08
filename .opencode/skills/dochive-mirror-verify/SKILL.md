---
name: dochive-mirror-verify
description: Проверяет качество зеркала Dochive — placeholders, errors.yaml, утечки ссылок на live-site, unresolved internal links, sync. Используй после mirror, при «проверь зеркало», «качество mirror», «ссылки на оригинал».
disable-model-invocation: true
---

# Dochive Mirror Verify

Пост-проверка зеркала после `dochive mirror` или частичного прогона. Дополняет, но не заменяет, выборочный просмотр 2–3 страниц на live-сайте.

## Когда включать

- Сразу после каждого прогона `dochive mirror` (в паре с **dochive-mirror**).
- Пользователь просит проверить готовность зеркала или «все ссылки локальные».
- Перед `dochive publish` в Git.

## Быстрый автоматический прогон

Из корня репозитория dochive:

```bash
skills/dochive-mirror-verify/scripts/check_mirror.sh \
  --root "<mirror_site_root>" \
  --source-host "<doc-host>"
```

Пример: `--root ./mirror/www.naumen.ru` и `--source-host www.naumen.ru`.

- Exit code `0` — автоматические проверки пройдены.
- Exit code `1` — есть placeholders, errors или утечки doc-ссылок в теле Markdown.
- Exit code `2` — неверные аргументы или нет `_catalog/`.

Скрипт печатает JSON-отчёт в stdout (без внешних зависимостей, только stdlib Python).

`--source-host` — hostname без схемы (`www.example.com`). Для чисто локального зеркала без внешних doc-ссылок можно опустить проверку утечек, передав несуществующий host и интерпретируя только placeholders/errors (лучше всё равно указать исходный host, если зеркало с web).

## Ручной чеклист

### 1. Placeholders

- `_catalog/structure.yaml` и `pages.yaml`: записи с `placeholder: true`.
- В `.md`: текст «Раздел ожидает отдельного зеркалирования» и строка `Источник: https://...` (допустимо в stub; после mirror должно уменьшаться).

Цель частичного зеркала: placeholders только в намеренно незагруженных разделах.

### 2. Ошибки и предупреждения

```bash
cat "<root>/_catalog/errors.yaml"
cat "<root>/_catalog/summary.yaml"
```

Обрати внимание на `internal_link_unresolved`, `asset_missing`, crawl failures. Зафиксируй count для отчёта пользователю.

### 3. Утечки на live documentation host

**В теле статей** внутренние Markdown/HTML-ссылки не должны вести на тот же doc-host, что и источник.

Допустимо:

- `source_url:` во frontmatter.
- Строка `Источник: <url>` в placeholder-stub.

Проверка (пример):

```bash
rg '\]\(https?://[^)]*www\.example\.com' "<root>" --glob '*.md' \
  | grep -v 'Источник:' | grep -v 'source_url:'
```

### 4. Unresolved internal links

- `summary.yaml` → `unresolved_internal_links`
- `links.yaml` → `kind: internal_unresolved`

### 5. Incremental sync

После повторного mirror:

```bash
cat "<root>/_catalog/sync.yaml"
```

Ожидай осмысленные `added` / `changed` при догрузке; лишние `deleted` — сигнал регрессии.

### 6. Выборочное качество (ручное)

Открой 2–3 страницы: сравни заголовки, таблицы, изображения с live URL из frontmatter `source_url`.

Для MadCap проверь:

- восстановление `p class="H4"` / `h2 data-mc-autonum`;
- Gramax `{% table %}` вместо битых pipe-таблиц;
- иконки в списках (inline, не растянутые блоки).

## Отчёт пользователю

Структура:

1. **Статус** — OK / нужна догрузка / критические ошибки.
2. **Метрики** — placeholders, errors, link leaks, unresolved internal.
3. **Действия** — какой `--source` (ветка TOC), `--max-pages`, селекторы; повтор mirror + verify.

## Если проверка не прошла

| Проблема | Действие |
|----------|----------|
| Много placeholders | Догрузить ветку: `mirror` с URL узла из structure, тот же `--out` |
| `internal_link_unresolved` | Проверить `--include-url-prefix`, scope, недозеркаленные соседи |
| Утечки на live-host | Повтор mirror с актуальным кодом; проверить path mapping в `pages.yaml` |
| Crawl errors | `--render-js`, `--anti-bot`, сеть, SSL/cafile в venv |

Не меняй `--out` при исправлении — только дополняй mirror.
