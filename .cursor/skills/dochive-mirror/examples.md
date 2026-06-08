# Примеры — dochive-mirror

## MadCap / Naumen NSD Pro (web)

Стартовая страница:

`https://www.naumen.ru/docs/sd/nsdpro/Content/main_page.htm`

### 1. Структура

```bash
dochive structure \
  --source "https://www.naumen.ru/docs/sd/nsdpro/Content/main_page.htm" \
  --out ./mirror \
  --scope subtree \
  --structure-mode auto \
  --max-depth 6 \
  --max-pages 2000
```

Проверь: `./mirror/<source_root>/_catalog/structure.yaml` — число узлов и `placeholder: true`.

### 2. Mirror (малый subtree — один прогон)

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

### 3. Mirror по ветке TOC (средний/большой объём)

Возьми `fetch_url` дочернего корня из `structure.yaml`:

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

Повтори для каждой верхней ветки; **не меняй** `--out`.

### 4. Verify

```bash
bash skills/dochive-mirror-verify/scripts/check_mirror.sh \
  --root ./mirror/<source_root> \
  --source-host www.naumen.ru
```

Или примени навык **dochive-mirror-verify**.

### 5. Smoke: одна TOC-страница (partial mirror)

Когда структура и часть страниц уже есть, догрузить **одну** страницу без перезаписи соседних разделов:

```bash
python3 -m dochive mirror \
  --source "https://www.naumen.ru/docs/sd/nsdpro/Content/sd/sd.htm?tocpath=%D0%9F%D1%80%D0%B0%D0%BA%D1%82%D0%B8%D0%BA%D0%B8%20NSD%C2%A0Pro%7C%D0%9F%D1%80%D0%B0%D0%BA%D1%82%D0%B8%D0%BA%D0%B0%20Servi%D1%81e%20Desk%7C_____0" \
  --out ./mirror \
  --render-js \
  --max-depth 1 \
  --max-pages 1 \
  --scope subtree \
  --anti-bot basic \
  --save-assets images
```

Ожидаемый mirror path: `mirror/www.naumen.ru/docs/sd/nsdpro/content/nsdpro_practices/sd/_index.md`.

После прогона проверь: целевая страница заполнена; `introduction/_index.md` и другие разделы **не** откатились в placeholder.

## Локальный HTML (без structure)

```bash
dochive mirror \
  --source ./path/to/html-dir \
  --out ./mirror-test \
  --max-depth 3 \
  --save-assets images
```

Verify с `--source-host` не нужен, если в теле страниц нет ссылок на внешний doc-host; всё равно проверь `errors.yaml` и placeholders.

## Wiki.js subtree

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

## Confluence (защищённый)

```bash
cp .env.example .env
# DOCHIVE_AUTH_TOKEN=...

dochive mirror \
  --source "https://wiki.example.com/pages/viewpage.action?pageId=123" \
  --out ./mirror \
  --render-js \
  --source-type confluence \
  --auth bearer \
  --scope subtree \
  --save-assets images
```
