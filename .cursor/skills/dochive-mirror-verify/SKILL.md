---
name: dochive-mirror-verify
description: Проверяет качество зеркала Dochive — preflight/postflight каталога, placeholders, errors.yaml, утечки ссылок, sync. Используй после mirror, при «проверь зеркало», verify-only без mirror, «ссылки на оригинал».
disable-model-invocation: true
---

# Dochive Mirror Verify

Пост-проверка зеркала после `dochive mirror`, partial smoke или в режиме **verify-only** (mirror не запускался). Дополняет выборочный просмотр 2–3 страниц на live-сайте.

**Экспериментально:** сценарии и инструкции пока не проходили полное тестирование; на рабочих зеркалах действуй осторожно.

## Когда включать

- После каждого `dochive mirror` (пара с **dochive-mirror**).
- Verify-only: страница уже `placeholder: false`, mirror не нужен.
- Перед `dochive publish`.

## Шаг 0. Preflight / postflight каталога

### До mirror (агент обязан записать)

Из `mirror_root/_catalog/summary.yaml`:

- `counts.pages` — baseline

При наличии предыдущего прогона — `sync.yaml` → `counts`.

**Не** сравнивай `structure.yaml` и `pages.yaml` по числу строк: в structure все узлы TOC, в pages — только записанные страницы.

### После mirror — тревоги (критично)

Прочитай `mirror_root/_catalog/sync.yaml`:

| Условие | Значение |
|---------|----------|
| `counts.deleted` > `counts.added + counts.changed` | **Каталог повреждён** — стоп, не продолжать догрузку |
| `counts.pages` в `summary.yaml` упал >5 без объяснения scope | Регрессия каталога |
| Массовый `deleted` в списке `deleted:` | Регрессия |

**Нормально** на partial mirror: высокие глобальные placeholders и link leaks в **незагруженных** разделах.

**Никогда нормально:** падение `counts.pages` после incremental smoke.

### Verify-only (mirror не запускался)

1. Целевая страница: `placeholder: false`, контент не stub.
2. Выборочно соседний раздел — не затронут.
3. Опционально `check_mirror.sh` для общей картины (интерпретируй с учётом partial mirror).

## Быстрый автоматический прогон

```bash
bash skills/dochive-mirror-verify/scripts/check_mirror.sh \
  --root "<mirror_root>" \
  --source-host "<doc-host>"
```

Пример: `--root ./mirror/www.naumen.ru`, `--source-host www.naumen.ru`.

- Exit `0` — автоматические проверки пройдены.
- Exit `1` — placeholders, errors или link leaks (на partial mirror leaks в незагруженных разделах ожидаемы).
- Exit `2` — неверные аргументы.

Запуск: **`bash skills/.../check_mirror.sh`**, не `python3`.

### Интерпретация на большом partial mirror

Ожидаемо: много `placeholders` и `live_doc_link_leaks` по всему root.

Для smoke/догрузки одной ветки проверь **точечно** (см. **dochive-mirror** → после incremental) + postflight `sync.yaml` и `counts.pages`.

## Ручной чеклист

### 1. Placeholders

- `pages.yaml` / frontmatter: `placeholder: true` только в намеренно незагруженных разделах.
- Stub: «Раздел ожидает отдельного зеркалирования».

### 2. Ошибки

```bash
cat "<mirror_root>/_catalog/errors.yaml"
cat "<mirror_root>/_catalog/summary.yaml"
```

### 3. Утечки live doc-host

В **теле** статей internal links не должны вести на doc-host. Допустимо: `source_url:` во frontmatter, строка `Источник:` в stub.

```bash
rg '\]\(https?://[^)]*www\.example\.com' "<mirror_root>" --glob '*.md' \
  | grep -v 'Источник:' | grep -v 'source_url:'
```

### 4. Unresolved internal links

`summary.yaml` → `unresolved_internal_links`; `links.yaml` → `internal_unresolved`.

### 5. Partial mirror regression

- Другой раздел остаётся `placeholder: false`.
- Cross-section ссылки — `.md` в mirror, не `https://`.
- `counts.pages` не упал (см. шаг 0).

### 6. Качество MadCap (выборочно)

- `{% table %}`, `:::note:false`, `<details>` для «Подробнее».
- Иконки: список inline ≤52 px; абзац — `<image>` на отдельной строке.
- Заголовки `H4` / `data-mc-autonum`.

## Отчёт

1. **Статус** — OK / догрузка / **каталог повреждён**.
2. **Метрики** — pages до/после, sync deleted/added/changed, placeholders, leaks (с контекстом partial).
3. **Действия** — следующий `--source`, флаги; при повреждении каталога — не продолжать mirror до разбора.

## Если проверка не прошла

| Проблема | Действие |
|----------|----------|
| Каталог повреждён (`deleted` >> `added+changed`) | Стоп; проверь `--out`, не использовался ли `links`; восстанови из git/backup |
| Много placeholders | Incremental mirror, тот же `--out`, `auto`/`toc` |
| `internal_link_unresolved` | `--include-url-prefix`, догрузить соседей |
| Утечки в **загруженной** странице | Повтор mirror актуальным кодом |
| Утечки только в незагруженных разделах | Норма для partial; догружать по плану |
| Partial mirror затёр соседний раздел | dochive ≥0.2.4; не `links`; не пересоздавать structure |
| Неверный `--out` (вложенный domain) | `--out` = родитель; перенести/исправить каталог |

Не меняй `--out` при исправлении incremental-прогонов.
