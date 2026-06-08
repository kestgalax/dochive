# Примеры — dochive-mirror

Пути для Naumen:

- `--out` = `./mirror`
- `mirror_root` = `./mirror/www.naumen.ru`

## MadCap / Naumen NSD Pro — greenfield

Старт: `https://www.naumen.ru/docs/sd/nsdpro/Content/main_page.htm`

### 1. Структура (только если нет `mirror_root/_catalog/`)

```bash
dochive structure \
  --source "https://www.naumen.ru/docs/sd/nsdpro/Content/main_page.htm" \
  --out ./mirror \
  --scope subtree \
  --structure-mode auto \
  --max-depth 6 \
  --max-pages 2000
```

### 2. Mirror (малый subtree)

```bash
dochive mirror \
  --source "https://www.naumen.ru/docs/sd/nsdpro/Content/main_page.htm" \
  --out ./mirror \
  --scope subtree \
  --structure-mode auto \
  --render-js \
  --max-pages 500 \
  --save-assets images \
  --image-size-mode max-width \
  --image-max-width 900
```

### 3. Mirror по ветке TOC

```bash
dochive mirror \
  --source "https://www.naumen.ru/docs/sd/nsdpro/Content/<section>/start.htm" \
  --out ./mirror \
  --scope subtree \
  --structure-mode auto \
  --render-js \
  --max-pages 120 \
  --save-assets images
```

## Naumen — `sd/sd.htm` (существующее зеркало)

URL:

`https://www.naumen.ru/docs/sd/nsdpro/Content/sd/sd.htm?tocpath=...`

Ожидаемый path: `mirror/www.naumen.ru/docs/sd/nsdpro/content/nsdpro_practices/sd/_index.md`

### Preflight (обязательно)

```bash
# mirror_root, не --out
grep -A2 "canonical_url.*sd/sd.htm" ./mirror/www.naumen.ru/_catalog/pages.yaml | head -20
# или прочитай frontmatter _index.md:
head -25 ./mirror/www.naumen.ru/docs/sd/nsdpro/content/nsdpro_practices/sd/_index.md
```

Зафиксируй baseline:

```bash
grep "pages:" ./mirror/www.naumen.ru/_catalog/summary.yaml
```

### Сценарий A: страница уже готова (`placeholder: false`)

Mirror **не** запускать. Только verify:

```bash
bash skills/dochive-mirror-verify/scripts/check_mirror.sh \
  --root ./mirror/www.naumen.ru \
  --source-host www.naumen.ru
```

### Сценарий B: догрузка placeholder (`placeholder: true`)

```bash
python3 -m dochive mirror \
  --source "https://www.naumen.ru/docs/sd/nsdpro/Content/sd/sd.htm?tocpath=%D0%9F%D1%80%D0%B0%D0%BA%D1%82%D0%B8%D0%BA%D0%B8%20NSD%C2%A0Pro%7C%D0%9F%D1%80%D0%B0%D0%BA%D1%82%D0%B8%D0%BA%D0%B0%20Servi%D1%81e%20Desk%7C_____0" \
  --out ./mirror \
  --render-js \
  --max-depth 1 \
  --max-pages 1 \
  --scope subtree \
  --structure-mode auto \
  --anti-bot basic \
  --save-assets images
```

**Не** используй `--structure-mode links`. **Не** указывай `--out ./mirror/www.naumen.ru`.

После прогона: `sd/_index.md` заполнен; `introduction/_index.md` не откатился; `sync.yaml` без массового `deleted`.

### Verify

```bash
bash skills/dochive-mirror-verify/scripts/check_mirror.sh \
  --root ./mirror/www.naumen.ru \
  --source-host www.naumen.ru
```

## Локальный HTML

```bash
dochive mirror \
  --source ./path/to/html-dir \
  --out ./mirror-test \
  --max-depth 3 \
  --save-assets images
```

## Wiki.js (greenfield)

```bash
dochive structure \
  --source "https://wiki.example.com/ru/advices" \
  --out ./mirror \
  --scope subtree \
  --structure-mode auto

dochive mirror \
  --source "https://wiki.example.com/ru/advices" \
  --out ./mirror \
  --render-js \
  --scope subtree \
  --structure-mode auto \
  --save-assets images
```

## Confluence

```bash
dochive mirror \
  --source "https://wiki.example.com/pages/viewpage.action?pageId=123" \
  --out ./mirror \
  --render-js \
  --source-type confluence \
  --auth bearer \
  --scope subtree \
  --save-assets images
```
