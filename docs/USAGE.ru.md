# Использование Dochive

[English](USAGE.md) | [Русский](USAGE.ru.md)

## Требования

- Python 3.10 или новее
- Git, только для checkout исходников или `dochive publish`
- Опционально: зависимости Crawl4AI для JavaScript-rendered web crawling

Dochive — это Python-пакет с console command `dochive`. Рекомендуемая установка одинакова для Windows, Linux и macOS: создать virtual environment, установить пакет, затем запускать `dochive`.

## Установка из исходников

Склонируйте репозиторий:

```bash
git clone https://github.com/kestgalax/dochive.git
cd dochive
```

Создайте virtual environment:

```bash
python3 -m venv .venv
```

Активируйте его в Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Активируйте его в Linux или macOS:

```bash
source .venv/bin/activate
```

Обновите `pip` и установите Dochive в editable mode:

```bash
python -m pip install --upgrade pip
python -m pip install -e .
```

Проверьте, что CLI доступен:

```bash
dochive --help
```

Во время разработки editable installation сохраняет command `dochive` указывающей на текущий код в `src/`. Также можно запускать package module напрямую из корня репозитория:

```bash
python -m dochive --help
```

## Обзор команд

Dochive предоставляет пять команд:

- `dochive mirror`: зеркалирует URL, локальный HTML-файл или локальную HTML-директорию в Markdown и YAML catalogs.
- `dochive structure`: обнаруживает и сохраняет web navigation structure перед зеркалированием контента.
- `dochive catalog`: печатает ожидаемые пути catalog files для mirror.
- `dochive query`: выполняет lexical search по mirrored Markdown и YAML files.
- `dochive publish`: коммитит и опционально push-ит mirror directory через Git.

### macOS Homebrew Python

Homebrew Python не разрешает устанавливать пакеты в global interpreter. Если `python3 -m pip install -e .` завершается ошибкой `externally-managed-environment`, сначала создайте virtual environment:

```bash
cd dochive
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m dochive --help
```

После активации `python` указывает на `.venv/bin/python`, поэтому для mirror commands в этом shell используйте `python -m dochive ...`.

Если `.venv` уже существует и был создан другим Python installer, проверьте его перед диагностикой HTTPS errors:

```bash
.venv/bin/python -c "import ssl, sys; print(sys.executable); print(ssl.get_default_verify_paths())"
```

Если `cafile=None`, пересоздайте environment с Homebrew Python или переустановите Dochive после обновления этой версии проекта.

## Опциональные зависимости для web crawling

Local HTML mirroring не требует browser dependencies. Для JavaScript-rendered web documentation установите optional Crawl4AI extra:

```bash
python -m pip install -e ".[crawl4ai]"
```

После установки Crawl4AI скачайте Playwright browser binaries:

```bash
playwright install chromium
```

Для всех браузеров (Chromium, Firefox, WebKit):

```bash
playwright install
```

Затем запускайте web crawls с `--render-js`. Local HTML mirroring продолжит работать без Crawl4AI.

Dochive задаёт workspace-local defaults для Crawl4AI во время web crawling. Если вы вызываете Crawl4AI tools напрямую, можно задать эти переменные самостоятельно.

Windows PowerShell:

```powershell
$env:CRAWL4_AI_BASE_DIRECTORY = "$PWD\.crawl4ai-data"
$env:PLAYWRIGHT_BROWSERS_PATH = "$PWD\.playwright-browsers"
$env:PYTHONIOENCODING = "utf-8"
```

Linux или macOS:

```bash
export CRAWL4_AI_BASE_DIRECTORY="$PWD/.crawl4ai-data"
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.playwright-browsers"
export PYTHONIOENCODING="utf-8"
```

## Обнаружение web structure

Для web documentation со стабильным navigation tree постройте структуру перед зеркалированием контента:

```bash
dochive structure \
  --source "https://docs.example.com/start.htm" \
  --out ./mirror \
  --max-depth 3 \
  --scope subtree \
  --structure-mode auto
```

Команда записывает `_catalog/structure.yaml` внутри mirror root. В нём сохраняются известные source URLs, navigation paths, parent links, order, placeholder status и итоговые Gramax paths. Последующие запуски `dochive mirror` в ту же output directory переиспользуют этот файл: отсутствующие страницы остаются placeholders, а отдельно зеркалированные разделы заполняют существующие пути вместо создания второй раскладки.

`--structure-mode auto` обнаруживает MadCap WebHelp navigation из `Data/HelpSystem.xml` и его TOC chunks, когда они доступны. Используйте `--structure-mode toc`, чтобы требовать этот TOC, или `--structure-mode links`, чтобы использовать link-based discovery. В TOC mode `--scope subtree` означает выбранную пользовательскую ветку TOC, а не только URL directory.

Используйте `--include-url-prefix`, когда documentation branch легитимно ссылается за пределы выбранного subtree, но такие страницы тоже должны быть доступны:

```bash
dochive structure \
  --source "https://docs.example.com/product/start.htm" \
  --out ./mirror \
  --scope subtree \
  --include-url-prefix "https://docs.example.com/shared/"
```

## Зеркалирование локального HTML

Примеры ниже используют PowerShell line continuations. В Linux или macOS используйте те же options в одну строку или замените завершающие backticks на `\`.

```powershell
dochive mirror `
  --source .\examples\local-html `
  --out .\mirror-test `
  --max-depth 3 `
  --save-assets images
```

`--source` может указывать на директорию или на один `.html`/`.htm` file. Local mirroring использует filesystem и не требует `--render-js`.

## Зеркалирование subtree web documentation

**macOS / Linux:**

```bash
dochive mirror \
  --source "url" \
  --out ./mirror \
  --render-js \
  --max-depth 1 \
  --max-pages 20 \
  --scope subtree \
  --structure-mode auto \
  --save-assets images \
  --image-size-mode max-width \
  --image-max-width 900
```

**Windows PowerShell:**

```powershell
dochive mirror `
  --source "url" `
  --out .\mirror `
  --render-js `
  --max-depth 1 `
  --max-pages 20 `
  --scope subtree `
  --structure-mode auto `
  --save-assets images `
  --image-size-mode max-width `
  --image-max-width 900
```

Используйте `--scope subtree` для controlled crawl. Используйте `--scope domain` только если намеренно хотите разрешить весь domain.
Для focused crawls, которым нужны shared assets или common pages directory, добавьте один или несколько `--include-url-prefix` values.

## Output layout

Dochive записывает вложенные страницы в layout, ожидаемый Gramax. Когда у crawled page есть child pages, страница становится папкой, а исходный page content записывается в `_index.md`; страницы без children остаются обычными Markdown files.

До того как child pages известны, page path выглядел бы плоским:

```text
docs/sd/nsdpro/content/change_list/beta_35.md
```

С crawled children generated mirror становится:

```text
docs/sd/nsdpro/content/change_list/beta_35/_index.md
docs/sd/nsdpro/content/change_list/beta_35/kakaya-to-stranica.md
docs/sd/nsdpro/content/change_list/change_list_arch.md
```

Internal Markdown links, page frontmatter, `_catalog/*.yaml`, sync reports и folder `_index.yaml` files используют итоговые `_index.md` paths. Page frontmatter также получает `order` на основе source navigation order, чтобы Gramax мог сортировать sibling pages так же, как исходная документация.

Используйте `--save-assets images`, когда screenshots нужно копировать локально и Markdown image links должны указывать на page-local media, например `./example.png` из Gramax `_index.md` page.

## Anti-bot modes

Web crawling по умолчанию использует `--anti-bot basic`. Браузер остаётся headless, но Crawl4AI получает запрос randomize user agent и применяет лёгкое page interaction и navigator overrides:

```powershell
dochive mirror `
  --source "url" `
  --out .\mirror `
  --render-js `
  --anti-bot basic
```

Используйте `--anti-bot off`, когда нужно старое plain Crawl4AI behavior для diagnostics или reproducibility.

Зарезервированные modes:

- `--anti-bot stealth`: planned to enable Crawl4AI stealth mode and tune delays for protected sites.
- `--anti-bot aggressive`: planned to add proxy escalation, retry rounds, and optional fallback fetch providers.

Эти reserved modes принимаются CLI choices, но намеренно останавливаются с понятной ошибкой, пока required runtime configuration не реализована. Aggressive mode потребует proxy list, вероятно через `--proxy` и/или environment variable `DOCHIVE_PROXIES`, плюс optional fallback fetch provider для сайтов, которые блокируют все browser attempts.

## Вывод изображений

По умолчанию linked screenshots записываются в Gramax image form:

```html
<image src="./example.png" crop="0,0,100,100" scale="100" width="1427px" height="617px" float="center"/>
```

Default `--image-size-mode intrinsic` читает реальные downloaded image dimensions и записывает их в Gramax image tag. Saved media хранится рядом с Markdown page: обычные `beta_35.md` pages используют `beta_35/`, а Gramax head pages используют ту же папку, что и `beta_35/_index.md`.

Для wide screenshots ограничьте rendered width с сохранением aspect ratio:

```powershell
--image-size-mode max-width --image-max-width 900
```

Это выдаёт responsive HTML вроде:

```html
<image src="./example.png" crop="0,0,100,100" scale="63" width="900px" height="389px" float="center"/>
```

Отключайте image size attributes только для diagnostics:

```powershell
--image-size-mode none
```

Используйте Markdown image output только когда это явно нужно:

```powershell
--image-render-mode markdown
```

Используйте `--image-link-mode linked` только когда явно нужны standard Markdown linked images:

```markdown
[![](thumb.png)](full.png)
```

## Зеркалирование видео

HTML `<video>` blocks сохраняются в Markdown как Gramax video tags:

```html
<video path="./change_list_30_video/example.mp4"/>
```

Без asset saving video tags сохраняют исходный remote URL. Чтобы копировать MP4 sources из HTML `<video>` blocks в mirror и переписывать video `path` attributes на page-local media folder, включите `videos` в `--save-assets`:

```powershell
dochive mirror `
  --source "url" `
  --out .\mirror `
  --render-js `
  --save-assets images,videos
```

## Улучшение extraction через selectors

Если у documentation site есть стабильный content container, лучше сузить extraction:

```powershell
dochive mirror `
  --source "https://docs.example.com/start.html" `
  --out .\mirror `
  --render-js `
  --content-selector "main" `
  --exclude-selector ".sidebar,.topbar,.search"
```

Также можно удалить точные noisy Markdown lines:

```powershell
dochive mirror `
  --source .\site-html `
  --out .\mirror `
  --noise-line "Account" `
  --noise-line "Logout"
```

Отключайте cleanup только для diagnostics:

```powershell
dochive mirror --source .\site-html --out .\mirror --no-clean-markdown
```

По умолчанию cleanup также обрезает повторяющийся page chrome перед первым article heading и удаляет Naumen legal footer. Site-wide navigation остаётся доступной через `_index.yaml` и `_catalog/*.yaml`; она не дублируется внутри каждой Markdown article.

## Восстановление заголовков

Некоторые documentation generators не выражают все headings как plain `h2`/`h3` elements в Markdown, который создаёт Crawl4AI. Mirror восстанавливает headings из source HTML перед Markdown cleanup.

Поддерживаемые patterns включают:

```html
<p class="H4">Типовая конфигурация до 500 одновременных пользователей (sd_pro_small)</p>
<h2 data-mc-autonum=""><span class="autonumber"><span></span></span>Типы компонентов систем SD Pro</h2>
```

Web crawler использует full HTML response для этого восстановления, потому что Crawl4AI `cleaned_html` может пропускать некоторые MadCap `h2 data-mc-autonum` headings. Local HTML parser также трактует `p` и `div` classes с именами `H1` through `H6` как Markdown headings.

Специальный CLI flag не нужен. Если recovered headings не появляются после обычного запуска, сначала проверьте, что команда использует текущий код репозитория, например через `python -m dochive ...` из repo root.

## Проверка каталогов

```powershell
dochive catalog --root .\mirror\www.naumen.ru
```

Важные файлы:

```text
_catalog/summary.yaml
_catalog/sync.yaml
_catalog/sync_history.yaml
_catalog/structure.yaml
_catalog/pages.yaml
_catalog/links.yaml
_catalog/assets.yaml
_catalog/errors.yaml
```

Каждая folder также получает `_index.yaml` для hierarchical LLM navigation.

## Поиск без векторов

```powershell
dochive query --root .\mirror\www.naumen.ru --text "быстрый старт" --limit 5
```

Это выполняет lexical file search по Markdown и YAML. Это первый retrieval layer для будущего Telegram bot или LLM assistant.

## Проверка incremental sync

Повторные запуски сравнивают новые page content hashes с предыдущим `_catalog/pages.yaml` и записывают:

```text
_catalog/sync.yaml
_catalog/sync_history.yaml
```

`sync.yaml` содержит latest run. `sync_history.yaml` добавляет каждый запуск отдельным YAML document, чтобы повторные mirrors одного сайта оставались inspectable over time.

Каждый report включает:

- `added`
- `changed`
- `unchanged`
- `deleted`

Те же counts также embedded in `_catalog/summary.yaml`.

## Проверка errors и warnings

Diagnostics записываются в:

```text
_catalog/errors.yaml
```

Типичные warnings:

- unresolved internal links, потому что `--max-depth` или `--max-pages` были слишком низкими;
- missing local HTML links;
- missing or failed assets.

Если remote image downloads завершаются с `CERTIFICATE_VERIFY_FAILED`, Python не смог проверить HTTPS certificate chain сайта. Используйте Python environment с настроенными CA certificates, например свежий `.venv`, созданный через Homebrew `python3`, затем переустановите Dochive внутри него. Для python.org macOS installer один раз запустите bundled `/Applications/Python 3.x/Install Certificates.command` и повторите mirror.

## Публикация через Git

Сначала просмотрите Git actions:

```powershell
dochive publish `
  --root .\mirror\www.naumen.ru `
  --dry-run `
  --init `
  --message "Update documentation mirror"
```

Сделайте локальный commit:

```powershell
dochive publish `
  --root .\mirror\www.naumen.ru `
  --init `
  --message "Update documentation mirror"
```

Push после commit выполняйте только когда remote уже настроен:

```powershell
dochive publish `
  --root .\mirror\www.naumen.ru `
  --message "Update documentation mirror" `
  --push
```
