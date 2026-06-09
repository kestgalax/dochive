# История изменений

[Русский](CHANGELOG.ru.md) | [English](CHANGELOG.md)

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/).

## [Unreleased]

### Added

- Agent skills `dochive-mirror` и `dochive-mirror-verify` в `skills/`: structure → план зеркалирования по объёму → verify после прогона. **Экспериментально:** сценарии пока не проходили полное тестирование на разных сайтах и в средах агентов.
- Установщики `setup.sh` и `setup.bat` (как у pochemuchka) для OpenCode, Claude Code, Codex и Cursor.
- Скрипт `skills/dochive-mirror-verify/scripts/check_mirror.sh` для проверки placeholders, `errors.yaml` и утечек ссылок на live-site.

### Changed

- Навыки: preflight, режимы greenfield/incremental/refresh/verify-only, пояснение `--out` vs `mirror_root`, запрет `--structure-mode links` на существующем MadCap-зеркале; после `git pull` переустановка: `./setup.sh --target cursor --force`.
- Локальные установки навыков в IDE (`.cursor/skills/`, `.opencode/skills/`) больше не в git; источник — каталог `skills/`.
- Краткий гайд по навыкам: `docs/SKILLS.ru.md` / `docs/SKILLS.md`.

## [0.2.6] — 2026-06-09

Ветка `fix/drop-wiki-back-h6-headings`.

### Changed

- В двуязычной документации переключатели языка и ссылки на пары файлов идут в порядке RU → EN (`[Русский] | [English]`, `*.ru.md` / `*.md`).
- При записи зеркала и в `dochive relink` повторно выполняется Markdown cleanup (если включён `clean_markdown`), чтобы обновлённый Dochive мог убрать устаревший Wiki.js chrome из уже скачанного зеркала без полного re-crawl.

### Fixed

- Нормализация Markdown удаляет навигационный chrome Wiki.js в заголовках H6 (`###### назад`, `###### [__назад__](...)` и английские варианты `back`); родительская навигация в Gramax уже задаётся через `_index.yaml` и каталоги.

## [0.2.5] — 2026-06-08

Ветка `cursor/image-isolation-relink-partial-sync`.

### Added

- Команда `dochive relink` офлайн переписывает абсолютные Markdown-ссылки во внутренние пути зеркала по `_catalog/structure.yaml` и `pages.yaml`; поддерживаются `--dry-run` и `--path-prefix` для выборочного прогона.
- Тесты в `tests/test_relink.py`, `tests/test_markdown_normalizer.py` и `tests/test_writer_images.py` для relink, очистки пустых ссылок и изоляции Gramax-блоков `<image>`.

### Changed

- Любые Gramax-теги `<image>`, включая мелкие иконки MadCap в списках, записываются отдельными блоками с пустыми строками до и после; текст пункта идёт после image-блока, а не внутри буллита (например списки clockGreen/clockRed).
- `docs/USAGE.md` / `docs/USAGE.ru.md`: описаны единое правило block-layout для `<image>` и incremental-workflow с `relink` после порционного зеркалирования.

### Fixed

- Нормализация Markdown удаляет пустые метки ссылок `[](url)` из невалидных вложенных MadCap-якорей (например `доступно [](...)[по ссылке](...)` → `доступно [по ссылке](...)`), не затрагивая `![](...)` и блоки кода.
- Partial mirror больше не удаляет соседние страницы в той же папке, если follow-up прогон зеркалит только другую страницу этого каталога.
- Follow-up mirror с `structure.yaml` записывает ancestor-placeholder страницы, нужные для навигации (например `introduction/_index.md` при зеркалировании дочернего раздела вроде Change List).

## [0.2.4] — 2026-06-08

Ветка `fix/incremental-cross-section-links`: переписывание ссылок и сохранение каталога при порционном mirror.

### Fixed

- При partial mirror внутренние ссылки переписываются на страницы, уже записанные в `_catalog/pages.yaml`, а не только на URL текущего прогона (например ссылки из introduction на QuickStart после отдельного зеркалирования разделов).
- Partial mirror больше не заменяет ранее зеркалированные разделы placeholder-markdown при зеркалировании другой ветки TOC в ту же output directory.
- Регрессия, при которой merge catalog paths расширял `sync_roots` на весь mirror и выбрасывал записи других разделов из `_catalog/pages.yaml`.

### Changed

- `dochive mirror` выводит пошаговый прогресс в stderr (`Reading catalog...`, `Writing N pages...`, `Updating catalog...` и связанные этапы).
- При partial sync обновляются `_index.yaml` только в пределах текущего sync scope, а не всего дерева mirror.
- Завершение Crawl4AI явно закрывает браузер с таймаутом; локализованные изображения не скачиваются повторно, если файл уже есть на диске.
- Загрузка ассетов использует таймаут URL 30 секунд.

### Added

- Тесты в `tests/test_writer_links.py` на переписывание cross-section ссылок и сохранение каталога и файлов при partial mirror.

## [0.2.3] — 2026-06-08

Ветка `fix/madcap-spoiler-podrobnee`: восстановление спойлеров MadCap «Подробнее» в выводе Gramax.

### Fixed

- Ссылки MadCap `MCDropDown` «Подробнее» (`[Подробнее](#)` после переписывания — на текущую страницу) снова распознаются и превращаются в блоки Gramax `<details>` / `<summary>` вместо самоссылки на ту же страницу (например пункты листа изменений Naumen NSD Pro `stable-26`).

## [0.2.2] — 2026-06-08

Ветка `fix/gramax-inline-paragraph-images`: отступы вокруг inline-иконок в абзацном тексте для Gramax.

### Changed

- `docs/USAGE.md` / `docs/USAGE.ru.md`: описан блочный вывод мелких иконок в абзацном тексте; иконки в пунктах списка по-прежнему остаются inline.

### Fixed

- Мелкие иконки MadCap, встроенные в середину предложения абзаца, выносятся на отдельную строку `<image>` с пустыми строками до и после — Gramax корректно их отображает (например плитки на страницах быстрого старта Naumen NSD Pro). Иконки в пунктах списка сохраняют прежний inline-формат.

## [0.2.1] — 2026-06-04

Ветка `fix/madcap-tables-comments-colwidth`: восстановление MadCap-таблиц, примечания Gramax и заголовки страниц из HTML.

### Added

- Конвертация исходных HTML-таблиц в блоки Gramax `{% table %}` с `{% colwidth=[…] %}` на каждую ячейку (256 px по умолчанию, 512 px для широких колонок); таблицы с `rowspan`/`colspan` остаются в HTML.
- Замена «рваных» pipe-таблиц Crawl4AI на очищенные таблицы из HTML; поглощение осиротевших буллетов, вырванных из ячеек.
- Преобразование абзацев MadCap `<p class="comment">` в callout Gramax `:::note:false` при web-mirror.
- Вставка заголовков разделов MadCap `<h2>` непосредственно перед каждым восстановленным блоком `{% table %}`.
- Использование текста HTML `<title>` или `<h1>` в метаданных страницы, когда Crawl4AI или навигация дают укороченную метку.

### Fixed

- Дублирующиеся `##` между подряд идущими Gramax-таблицами при одновременной вставке заголовков из HTML и восстановлении по follower-тексту.
- Остаточные pipe-строки, `|`-мусор и буллеты после `{% /table %}` на MadCap-страницах с метриками.
- Лишние строки `-` в ячейках таблиц при вложенной разметке списков `<li><p>` (`<ul class="tab">` в ячейках).
- В Gramax короткий заголовок страницы из TOC при полном заголовке документа в теле статьи.

## [0.2.0] — 2026-06-04

Ветка `codex/madcap-heading-recovery`: восстановление иерархии MadCap WebHelp и корректный вывод мелких иконок в Gramax.

### Added

- Восстановление пропущенных заголовков MadCap (`p class="H1"`–`H6"`) по совпадению текста следующего абзаца или первого пункта списка, когда Crawl4AI полностью вырезает строку заголовка из Markdown.
- Вставка восстановленного заголовка перед блоком `<image>` / `<video>`, если диаграмма в Markdown стоит непосредственно перед follower-текстом из HTML (исправляет порядок «картинка над заголовком», например `### Границы Процесса` на страницах Naumen NSD Pro).
- Режим inline-иконок для списков: изображения с большей стороной ≤ `--image-inline-max-px` (по умолчанию 48) оформляются в формате, совместимом с Gramax (иконка на отдельной строке пункта списка, текст на следующей; без атрибута `scale`).
- CLI-флаг `--image-inline-max-px` (значение `0` отключает поведение).
- Тесты: `tests/test_html_extract.py`, `tests/test_writer_images.py`.

### Changed

- Документация: `README.md` / `README.ru.md`, `docs/USAGE.md` / `docs/USAGE.ru.md`, `docs/stages/010-html-heading-recovery.md` — описаны вставка по follower-тексту и inline-иконки.

### Fixed

- Пропавшие подзаголовки вроде «Общее описание» и «Основные положения Процесса» на MadCap-страницах после web-mirror.
- Сильное растягивание мелких list-иконок в Gramax из-за блочных `<image float="center">` на одной строке с текстом пункта списка.
