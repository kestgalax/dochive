# Agent Skills — зеркалирование

[English](SKILLS.md) | [Русский](SKILLS.ru.md)

Навыки в [`skills/`](../skills/) помогают агенту (Cursor, Claude Code, OpenCode и др.) безопасно зеркалировать документацию через Dochive: **с нуля**, **догрузкой раздела** или **проверкой** уже готового зеркала.

## Навыки

| Навык | Назначение |
|-------|------------|
| **dochive-mirror** | Preflight → выбор режима → `structure` / `mirror` |
| **dochive-mirror-verify** | Проверка каталога, placeholders, `sync.yaml`, утечек ссылок |

Подробная логика: [`skills/dochive-mirror/SKILL.md`](../skills/dochive-mirror/SKILL.md), примеры: [`examples.md`](../skills/dochive-mirror/examples.md).

## Установка

```bash
# macOS / Linux — в каталог IDE проекта
./setup.sh --target cursor --force

# Windows
setup.bat --target cursor

# Вручную (Cursor)
cp -r skills/dochive-mirror .cursor/skills/
cp -r skills/dochive-mirror-verify .cursor/skills/
```

После `git pull` с изменениями в `skills/` **переустановите** навыки (`--force`). Копия в `.cursor/skills/` сама не обновляется.

## Как вызвать в чате

Навыки не подхватываются автоматически — назовите явно:

- «Примени **dochive-mirror** для `https://…` в `./mirror`»
- «**dochive-mirror-verify** для `./mirror/www.example.com`»

## Режимы (кратко)

| Режим | Когда |
|-------|-------|
| **Greenfield** | Нет `_catalog/` — сначала `structure`, потом `mirror` |
| **Incremental** | Страница `placeholder: true` — только `mirror`, `structure` не трогать |
| **Refresh** | Страница уже готова, нужно перекачать — только с вашего согласия |
| **Verify-only** | Страница готова, mirror не нужен — только verify |

Перед любой командой агент делает **preflight**: читает `pages.yaml` / frontmatter целевой страницы и фиксирует `counts.pages` из `summary.yaml`.

## Пути `--out` (частая ошибка)

```text
--out ./mirror                 ← аргумент CLI
  └── www.naumen.ru/           ← mirror_root (catalog, verify)
        └── _catalog/
```

- В `mirror` / `structure` передавайте **`--out ./mirror`**, не `./mirror/www.naumen.ru`.
- `dochive catalog --root` и verify — на **mirror_root**.

## Красные флаги

Не делайте на существующем MadCap-зеркале:

- `--structure-mode links` (ломает опору на TOC)
- `dochive structure` без запроса «пересобрать TOC»
- `--out`, указывающий на `mirror_root` вместо родителя

## Быстрая проверка вручную

```bash
bash skills/dochive-mirror-verify/scripts/check_mirror.sh \
  --root ./mirror/www.naumen.ru \
  --source-host www.naumen.ru
```

После partial mirror смотрите `sync.yaml`: массовый `deleted` — признак повреждения каталога.

## См. также

- [USAGE.ru.md](USAGE.ru.md) — CLI Dochive
- [README.ru.md](../README.ru.md) — установка пакета
