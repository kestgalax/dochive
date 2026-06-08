# Dochive CLI — шпаргалка для зеркалирования

Полная документация: [docs/USAGE.md](../../docs/USAGE.md) (EN), [docs/USAGE.ru.md](../../docs/USAGE.ru.md) (RU).

## Пути: `--out` vs `mirror_root`

| | Значение (Naumen) | Куда передаётся |
|---|-------------------|-----------------|
| `--out` | `./mirror` | `dochive mirror`, `dochive structure` |
| `mirror_root` | `./mirror/www.naumen.ru` | `dochive catalog --root`, verify, чтение `_catalog/` |

CLI создаёт `mirror_root = <out>/<domain>/` автоматически ([`source_root_name`](../../src/dochive/url_utils.py)).

## Режимы (кратко)

| Режим | structure | mirror |
|-------|-----------|--------|
| Greenfield | да (`auto`/`toc`) | да |
| Incremental fill | **нет** | да (`auto`/`toc`, не `links`) |
| Refresh | **нет** | да, с согласия |
| Verify-only | **нет** | **нет** |

## `--structure-mode`

| Ситуация | auto | toc | links |
|----------|------|-----|-------|
| Новое MadCap зеркало | да | да | нет |
| Существующее MadCap, догрузка/refresh | да | да | **запрещено** |
| Wiki.js без TOC (greenfield) | да | — | да |

`links` на существующем MadCap-зеркале отключает TOC и рискует повредить каталог.

## Команды

| Команда | Назначение |
|---------|------------|
| `dochive structure` | Сохранить `structure.yaml` (greenfield / пересборка TOC) |
| `dochive mirror` | Скачать/конвертировать страницы |
| `dochive catalog --root` | Пути `_catalog/*.yaml` |
| `dochive query --root --text` | Поиск по зеркалу |
| `dochive publish --root` | Git commit/push |

## Общие флаги

| Флаг | По умолчанию | Заметка |
|------|--------------|---------|
| `--source` | — | URL, файл или каталог |
| `--out` | — | **Родитель**; не `mirror_root` |
| `--scope` | `subtree` | `domain` — только с согласия |
| `--structure-mode` | `auto` | MadCap existing: не `links` |
| `--max-depth` | 3 | Глубина link-crawl |
| `--max-pages` | 500 | Лимит за прогон; smoke: `1` |
| `--include-url-prefix` | — | Shared-ветки вне subtree |
| `--anti-bot` | `basic` | `off` для диагностики |

## Только mirror

| Флаг | По умолчанию |
|------|--------------|
| `--render-js` | off |
| `--save-assets` | пусто; `images`, `images,videos` |
| `--image-size-mode` | `intrinsic`; скриншоты: `max-width` + `--image-max-width 900` |
| `--image-inline-max-px` | 52 |

## Каталоги (`mirror_root/_catalog/`)

| Файл | Содержание |
|------|------------|
| `structure.yaml` | Все узлы TOC (много placeholders) |
| `pages.yaml` | Записанные страницы (для сравнения до/после) |
| `summary.yaml` | `counts.pages` — baseline preflight |
| `sync.yaml` | added/changed/deleted после прогона |
| `errors.yaml` | Ошибки и предупреждения |

Не сравнивай `structure.yaml` и `pages.yaml` по числу строк — разная семантика.

## Partial mirror (0.2.4+)

- Cross-section link rewrite по всему `pages.yaml`.
- Записи вне sync scope сохраняются.
- Прогресс на stderr; skip существующих assets; timeout 30 с.

## Gramax-вывод MadCap

| Источник | Mirror |
|----------|--------|
| HTML-таблицы | `{% table %}` + `{% colwidth=[…] %}` |
| `<p class="comment">` | `:::note:false` |
| «Подробнее» / MCDropDown | `<details>` / `<summary>` |
| Иконки в списке (≤52 px) | inline, `<image>` на отдельной строке |
| Иконки в абзаце | `<image>` на отдельной строке + пустые строки |
| Крупные скриншоты | `max-width` 900 |
