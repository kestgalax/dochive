---
name: dochive-mirror
description: Оркестрирует зеркалирование документации через Dochive — structure, выбор стратегии по объёму, mirror, verify. Используй при «зеркалируй документацию», URL + --out, dochive mirror, MadCap/Naumen WebHelp, Wiki.js, частичное зеркало по разделам.
disable-model-invocation: true
---

# Dochive Mirror

Навык управляет полным циклом зеркалирования HTML-документации в Markdown-first репозиторий с помощью CLI [Dochive](https://github.com/kestgalax/dochive). После каждого прогона `mirror` обязательно применяй навык **dochive-mirror-verify** (или его чеклист).

Подробные флаги CLI: [reference.md](reference.md). Примеры: [examples.md](examples.md).

## Когда включать

- Пользователь дал URL документации и хочет локальное зеркало (Gramax/Markdown).
- Нужно спланировать зеркалирование большого сайта по разделам или за один прогон.
- Повторное дозеркалирование в тот же `--out` с сохранением путей.

## Вход

Собери перед стартом:

1. **URL** (`--source`) — стартовая страница или корень ветки.
2. **`--out`** — каталог вывода (спроси, если не указан; не меняй между прогонами одного зеркала).
3. **Цель** — вся ветка TOC / один раздел / пробный smoke.
4. **Права** — напомни про Responsible Use в README: копирование чужой документации только при наличии прав.

## Шаг 0. Окружение

Из корня репозитория dochive (или после `pip install dochive`):

```bash
python -m pip install -e .
# для web + JS:
python -m pip install -e ".[crawl4ai]"
playwright install chromium
```

Для web crawl задай (см. `docs/USAGE.md`):

```bash
export CRAWL4_AI_BASE_DIRECTORY="$PWD/.crawl4ai-data"
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.playwright-browsers"
export PYTHONIOENCODING=utf-8
```

Предпочитай `python -m dochive` из repo root при разработке — так используется актуальный код.

## Шаг 1. Классификация источника

| Признак | Тип | Режим structure |
|--------|-----|-----------------|
| URL содержит `/Content/` и рядом доступен `{webhelp}/Data/HelpSystem.xml` | MadCap WebHelp | `--structure-mode auto` (или `toc`) |
| Extensionless Wiki URL, `/ru/`, login/tag в соседних ссылках | Wiki.js | `auto` или `links` |
| Локальный `.html` / каталог | Локальный | `structure` не нужен, сразу `mirror` |
| Confluence + токен | Confluence | `--source-type confluence --auth bearer` |

**Проба MadCap (без полного mirror):** из URL `.../Content/page.htm` выведи webhelp root (всё до `/Content/`) и проверь HEAD/GET на `{root}/Data/HelpSystem.xml`.

**Проба Wiki.js:** extensionless path, языковой префикс — см. `url_utils` / `markdown_normalizer` в репозитории dochive.

Не используй `--scope domain` без явного согласия пользователя.

## Шаг 2. Обнаружение структуры (web)

Всегда для web-документации со стабильным TOC:

```bash
dochive structure \
  --source "<URL>" \
  --out "<OUT>" \
  --scope subtree \
  --structure-mode auto \
  --max-depth <3-10> \
  --max-pages <500-2000>
```

Добавь `--include-url-prefix` для shared-страниц вне subtree. Для Confluence — флаги auth из reference.

Результат: `<OUT>/<source_root>/_catalog/structure.yaml` с деревом, `placeholder`, `fetch_url`, Gramax paths.

## Шаг 3. План зеркалирования по объёму

Прочитай `structure.yaml` (и при необходимости `pages.yaml`). Подсчитай записи с `placeholder: true` и общее число страниц в ветке.

| Размер ветки | Стратегия |
|--------------|-----------|
| **Малый** (< ~50 страниц) | Один `dochive mirror` с тем же `--source`, `--out`, `--scope subtree` |
| **Средний** (~50–300) | По **дочерним корням TOC**: для каждой верхней ветки отдельный `--source` = URL узла, **тот же `--out`** |
| **Большой** (> ~300 или таймауты) | Те же ветки + `--max-pages` 80–150 за прогон; повторять mirror, пока placeholders не исчезнут |
| **Smoke / одна страница** | `--max-depth 1 --max-pages 1` с URL конкретной TOC-страницы (с `?tocpath=...` для MadCap); тот же `--out` |

Если `_catalog/structure.yaml` уже есть в `--out` — **не перезапускай** `structure` без необходимости; сразу `mirror` по нужному `--source`.

Рекомендуемые флаги mirror (web):

```bash
dochive mirror \
  --source "<URL>" \
  --out "<OUT>" \
  --scope subtree \
  --structure-mode auto \
  --render-js \
  --save-assets images \
  --anti-bot basic \
  --image-size-mode max-width \
  --image-max-width 900
```

Добавь `videos` в `--save-assets`, если на сайте есть `<video>`. Уточни `--content-selector` / `--exclude-selector`, если контент в узком контейнере.

**Жёсткие правила:**

- Не меняй `--out` между прогонами одного зеркала.
- Placeholders заполняются при mirror того же URL из structure — пути файлов остаются стабильными.
- Partial mirror **не затирает** уже зеркалированные разделы при смене ветки TOC в том же `--out`; внутренние ссылки переписываются по `_catalog/pages.yaml`, в том числе на страницы из других прогонов (cross-section links, с 0.2.4).
- CLI печатает прогресс на **stderr** (`Reading catalog...`, `Writing N pages...`, `Updating catalog...`) — это нормально, не ошибка.
- Повторная загрузка уже существующих image-файлов на диске пропускается (0.2.4).
- После **каждого** прогона mirror → **dochive-mirror-verify** (включая smoke с `--max-pages 1`).

### Partial mirror: что проверить после smoke

После догрузки одной TOC-страницы (например `sd/sd.htm`):

1. Целевой `.md` — `placeholder: false`, нет stub «Раздел ожидает отдельного зеркалирования».
2. **Соседний уже зеркалированный раздел** (например `introduction/_index.md`) — по-прежнему `placeholder: false`, тело не затёрто.
3. `_catalog/sync.yaml` — осмысленный `changed`/`added`, **без** массовых `deleted`.
4. Ссылки с новой страницы на уже зеркалированные разделы — относительные пути в mirror, не `https://...` doc-host.

## Шаг 4. Отчёт пользователю

Кратко сообщи:

- Тип источника (MadCap / Wiki / local / Confluence).
- Выбранную стратегию и число прогонов.
- Путь mirror root (`dochive catalog --root ...`).
- Результат verify: placeholders, errors, утечки ссылок на live-site.
- Следующий шаг, если verify не прошёл (какая ветка TOC / какие флаги поменять).

## Связанные команды

```bash
dochive catalog --root <mirror_site_root>
dochive query --root <mirror_site_root> --text "..." --limit 5
```

При публикации зеркала в Git — `dochive publish` (отдельная задача, не часть mirror).
