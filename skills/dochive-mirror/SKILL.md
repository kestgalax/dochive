---
name: dochive-mirror
description: Оркестрирует зеркалирование документации через Dochive — preflight, режимы (с нуля / догрузка / обновление), mirror, verify. Используй при «зеркалируй документацию», URL + --out, dochive mirror, MadCap/Naumen WebHelp, Wiki.js, частичное зеркало по разделам.
disable-model-invocation: true
---

# Dochive Mirror

Навык управляет зеркалированием HTML-документации в Markdown-first репозиторий через CLI [Dochive](https://github.com/kestgalax/dochive). Работа бывает **с нуля**, **догрузкой раздела** или **обновлением** уже зеркалированной страницы — не предполагай greenfield по умолчанию.

**Экспериментально:** сценарии и инструкции пока не проходили полное тестирование; на рабочих зеркалах действуй осторожно и сверяйся с preflight/verify.

Подробные флаги: [reference.md](reference.md). Примеры: [examples.md](examples.md).

## Когда включать

- Пользователь дал URL и хочет зеркало (Gramax/Markdown).
- Нужно догрузить placeholder, обновить страницу или спланировать зеркало с нуля.
- Повторное зеркалирование в тот же `--out` с сохранением путей.

## Режимы работы

Выбери режим **до** любых команд (после preflight, шаг 0.5):

| Режим | Когда | Что делать |
|-------|-------|------------|
| **Greenfield** | Нет `<mirror_root>/_catalog/` | `structure` → `mirror` по объёму |
| **Incremental fill** | Каталог есть, цель `placeholder: true` | **Только** `mirror`; `structure` не трогать |
| **Refresh** | Каталог есть, цель `placeholder: false`, пользователь хочет перекачать | `mirror` только с явным согласием |
| **Verify-only** | Страница готова (`placeholder: false`), задача — проверка | Только **dochive-mirror-verify**; mirror не запускать |

## Вход

1. **URL** (`--source`) — страница, ветка TOC или корень.
2. **`--out`** — **родительский** каталог вывода (`./mirror`), не `mirror_root`.
3. **Цель** — greenfield / догрузка / refresh / verify.
4. **Права** — Responsible Use в README.

## Структура `--out` (критично)

CLI **всегда** создаёт подкаталог с именем домена:

```text
--out ./mirror                    ← передаёшь в mirror/structure
  └── www.naumen.ru/              ← mirror_root (catalog, verify, чтение каталогов)
        └── _catalog/
        └── docs/...
```

| Переменная | Пример | Назначение |
|------------|--------|------------|
| `--out` | `./mirror` | Аргумент CLI |
| `mirror_root` | `./mirror/www.naumen.ru` | `dochive catalog --root`, verify, чтение `pages.yaml` |

**Ошибка:** `--out ./mirror/www.naumen.ru` → вложенный `www.naumen.ru/www.naumen.ru/`. Если внутри `mirror_root` снова появился `_catalog` во вложенном домене — **стоп**, исправь `--out`.

## Шаг 0. Окружение

```bash
python -m pip install -e .
python -m pip install -e ".[crawl4ai]"
playwright install chromium
```

```bash
export CRAWL4_AI_BASE_DIRECTORY="$PWD/.crawl4ai-data"
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.playwright-browsers"
export PYTHONIOENCODING=utf-8
```

Предпочитай `python -m dochive` из repo root.

## Шаг 0.5. Preflight (обязательный)

Выполни **до** `structure` или `mirror`:

1. **Разреши пути:** `--out` = родитель; `mirror_root` = `<out>/<domain>/`.
2. **Проверь каталог:** есть ли `mirror_root/_catalog/pages.yaml`?
3. **Найди целевую страницу** в `pages.yaml` или frontmatter `.md` (по `canonical_url` / `path` из `structure.yaml`):
   - `placeholder: false` и пользователь не просил refresh → **Verify-only**, mirror не запускать.
   - `placeholder: true` → **Incremental fill**.
   - Нет каталога → **Greenfield**.
4. **Baseline** (запиши для verify после прогона): `summary.yaml` → `counts.pages`; при наличии — `sync.yaml` → counts.
5. **MadCap:** если `structure.yaml` уже есть — **не** запускай `dochive structure` без явного запроса «пересобрать TOC».

## Красные флаги (STOP)

- `--structure-mode links` на **существующем** MadCap-зеркале (для `mirror` и `structure`) — игнорирует TOC, ломает каталог.
- `dochive structure` на существующем зеркале без запроса пересборки — перезаписывает `structure.yaml`.
- `--out` указывает на `mirror_root`, а не на родительский каталог.
- Запуск mirror, когда preflight показал `placeholder: false` без запроса refresh.

## Шаг 1. Классификация источника

| Признак | Тип | structure-mode (MadCap) |
|--------|-----|-------------------------|
| `/Content/` + `HelpSystem.xml` | MadCap WebHelp | `auto` или `toc`; на существующем зеркале **не** `links` |
| Extensionless Wiki URL | Wiki.js | `auto` или `links` (greenfield) |
| Локальный HTML | Локальный | `structure` не нужен |
| Confluence + токен | Confluence | `--source-type confluence --auth bearer` |

Не используй `--scope domain` без согласия пользователя.

## Шаг 2. Обнаружение структуры (только Greenfield)

**Не** запускай для incremental fill / refresh / verify-only.

```bash
dochive structure \
  --source "<URL>" \
  --out "<OUT_PARENT>" \
  --scope subtree \
  --structure-mode auto \
  --max-depth <3-10> \
  --max-pages <500-2000>
```

Результат: `mirror_root/_catalog/structure.yaml`.

Пересборка TOC на существующем зеркале — только по явному запросу пользователя; предупреди о риске.

## Шаг 3. План зеркалирования

Прочитай `structure.yaml` / `pages.yaml` для целевой ветки.

| Размер ветки | Стратегия |
|--------------|-----------|
| **Малый** (< ~50) | Один `mirror`, тот же `--out` |
| **Средний** (~50–300) | Mirror по URL верхних узлов TOC, тот же `--out` |
| **Большой** (> ~300) | Ветки + `--max-pages` 80–150, повтор до заполнения placeholders |
| **Smoke / одна страница** | `--max-depth 1 --max-pages 1`, URL с `?tocpath=...` (MadCap) |

### Листовая TOC-страница (без детей)

Если у узла в `structure.yaml` нет `children` — зеркалируется **одна** страница. Это нормально; не ожидай подстраниц.

### Рекомендуемые флаги mirror (web, существующее MadCap-зеркало)

```bash
dochive mirror \
  --source "<URL>" \
  --out "<OUT_PARENT>" \
  --scope subtree \
  --structure-mode auto \
  --render-js \
  --save-assets images \
  --anti-bot basic \
  --image-size-mode max-width \
  --image-max-width 900
```

Smoke на существующем зеркале: добавь `--max-depth 1 --max-pages 1`; **не** используй `--structure-mode links`.

**Жёсткие правила:**

- Не меняй `--out` между прогонами.
- Partial mirror (0.2.4+) не затирает другие разделы; cross-section links из `_catalog/pages.yaml`.
- Прогресс на stderr — норма.
- После каждого `mirror` → **dochive-mirror-verify**.

### После incremental / smoke

1. Целевой `.md` — `placeholder: false`.
2. Соседний раздел (например `introduction/_index.md`) — всё ещё `placeholder: false`.
3. `sync.yaml` — без массового `deleted`.
4. Cross-section ссылки — относительные пути, не live doc-host.

## Шаг 4. Отчёт

Сообщи: режим (greenfield / incremental / refresh / verify-only), `--out` vs `mirror_root`, стратегию, результат verify, следующий шаг.

## Связанные команды

```bash
dochive catalog --root <mirror_root>
dochive query --root <mirror_root> --text "..." --limit 5
```
