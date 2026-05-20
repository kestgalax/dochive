# Dochive

[English](README.md) | [Русский](README.ru.md)

CLI-инструмент для зеркалирования HTML-документации в Markdown-first репозиторий:

- Markdown-файлы страниц с YAML frontmatter
- `_index.yaml` в каждой папке
- глобальные файлы `_catalog/*.yaml`
- детерминированное сопоставление URL и файлов

Dochive — инструмент общего назначения, но у него есть полноценная поддержка документации в стиле MadCap WebHelp и Wiki.js.

## Основные возможности

- Зеркалирует HTML-документацию в Markdown-репозиторий, готовый для Gramax.
- Поддерживает локальные HTML-файлы, локальные HTML-папки и опциональный web crawling через Crawl4AI с JavaScript rendering.
- Сохраняет иерархию документации, порядок страниц, внутренние ссылки и `_index.md` страницы для разделов с дочерними страницами.
- Обнаруживает структуру перед зеркалированием контента, поэтому повторные и частичные запуски сохраняют стабильные пути и placeholders.
- Читает навигацию MadCap WebHelp из `Data/HelpSystem.xml`, когда она доступна, вместо опоры только на ссылки страниц.
- Обрабатывает Wiki.js-style extensionless URLs, language prefixes, service links, permalink heading anchors и повторяющийся site chrome.
- Скачивает или копирует изображения в page-local media folders; HTML video sources также можно локализовать через `--save-assets videos`.
- Рендерит изображения как Gramax `<image .../>` tags с intrinsic sizes или ограниченной шириной.
- Восстанавливает заголовки из HTML-паттернов стилей, например `p class="H4"` и MadCap `h2 data-mc-autonum`.
- Очищает типичный шум документации, включая повторяющийся page chrome, выбранные tags, selectors и точные noisy lines.
- Записывает каталоги и отчёты по страницам, ссылкам, assets, структуре, ошибкам и incremental sync.
- Предоставляет lexical search и Git publish helpers для mirrored repositories.

## Установка

Dochive требует Python 3.10 или новее.

```bash
git clone https://github.com/kestgalax/dochive.git
cd dochive
python3 -m venv .venv
```

Активируйте virtual environment.

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Linux или macOS:

```bash
source .venv/bin/activate
```

Установите пакет:

```bash
python -m pip install --upgrade pip
python -m pip install -e .
dochive --help
```

На macOS с Homebrew Python устанавливайте в virtual environment, как показано выше. Если `python3 -m pip install -e .` завершается ошибкой `externally-managed-environment`, создайте и активируйте `.venv`, затем используйте `python -m pip install -e .` внутри него.

Если `.venv` был создан до смены Python installer, пересоздайте его с Homebrew `python3` или проверьте `.venv/bin/python -c "import ssl; print(ssl.get_default_verify_paths())"` перед диагностикой HTTPS asset failures.

## Использование

Зеркалировать локальный HTML:

```bash
dochive mirror --source ./site-html --out ./mirror --max-depth 3 --save-assets images
```

Зеркалировать один локальный HTML-файл можно так же:

```bash
dochive mirror --source ./site-html/index.html --out ./mirror --max-depth 1
```

Для web crawling установите optional Crawl4AI extra и Playwright browsers:

```bash
python -m pip install -e ".[crawl4ai]"
playwright install chromium
dochive structure --source https://docs.example.com --out ./mirror --max-depth 3 --structure-mode auto
dochive mirror --source https://docs.example.com --out ./mirror --render-js --structure-mode auto --save-assets images
```

`dochive structure` сохраняет `_catalog/structure.yaml` с известным navigation tree и итоговыми Gramax paths. Последующие запуски `mirror` переиспользуют эту структуру, сохраняя placeholders стабильными, пока каждый раздел не будет зеркалирован.

Для сайтов MadCap WebHelp `--structure-mode auto` читает официальный TOC из `Data/HelpSystem.xml`, когда он доступен, поэтому `--scope subtree` следует по пользовательской ветке навигации.

Для сайтов Wiki.js `--structure-mode auto` откатывается к link-based discovery, сохраняет extensionless pages в Gramax layout с `_index.md`, фильтрует типичные service links вроде login/tag routes, нормализует ссылки с language prefix и удаляет характерный Wiki.js chrome из mirrored Markdown.

Для focused Wiki.js subtree начинайте с фактической страницы с language prefix и оставляйте `--scope subtree`:

```bash
dochive mirror --source https://wiki.example.com/ru/advices --out ./mirror --render-js --structure-mode auto --scope subtree --save-assets images
```

Полезные команды:

```bash
dochive catalog --root ./mirror/docs.example.com
dochive query --root ./mirror/docs.example.com --text "quick start" --limit 5
dochive publish --root ./mirror/docs.example.com --dry-run --init
```

Во время разработки editable installation сохраняет console command `dochive` указывающей на текущий код в `src/`. Также можно запускать package module напрямую из корня репозитория:

```bash
python -m dochive --help
```

Если HTTPS asset downloads завершаются с `CERTIFICATE_VERIFY_FAILED`, убедитесь, что crawl запускается в Python environment с настроенными CA certificates. Свежий `.venv`, созданный через Homebrew `python3`, обычно наследует Homebrew certificate bundle; python.org macOS installer также можно исправить через `/Applications/Python 3.x/Install Certificates.command`.

## Документация проекта

- [Roadmap](docs/ROADMAP.md)
- [Usage](docs/USAGE.md)
- [Usage на русском](docs/USAGE.ru.md)
- [Stage artifacts](docs/stages/)

## Лицензия

Dochive распространяется под Apache License 2.0. См. [LICENSE](LICENSE).

Пожалуйста, сохраняйте атрибуцию этого репозитория при использовании или распространении проекта:
https://github.com/kestgalax/dochive

## Уведомления о сторонних компонентах

Dochive использует или может использовать стороннее open-source ПО:

- certifi: MPL-2.0; предоставляет Mozilla's CA Bundle для TLS certificate verification.
- Crawl4AI: Apache-2.0; используется только при установке optional `crawl4ai` extra.

Опциональная web crawling функциональность может использовать Crawl4AI, open-source проект UncleCode:
https://github.com/unclecode/crawl4ai

Подробности атрибуции см. в [NOTICE](NOTICE).

## Ответственное использование

Dochive зеркалирует и конвертирует документационный контент. Перед публикацией mirrored output убедитесь, что у вас есть право копировать, конвертировать, хранить или распространять стороннюю документацию.
