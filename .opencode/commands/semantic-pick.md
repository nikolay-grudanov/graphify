---
description: "Step 3B с интерактивным выбором файлов/директорий для семантической экстракции"
---

# Семантическая экстракция — выбор файлов

Покажи пользователю содержимое `.graphify_detect.json` и дай выбрать, какие файлы или директории отправить на семантическую экстракцию (Step 3B).

## Предусловия

- Убедись что файл `.graphify_detect.json` существует (Step 2 detect уже выполнен).
- Убедись что файл `.graphify_ast.json` существует (Step 3A AST уже выполнен).
- Если какого-то файла нет — сообщи пользователю что сначала нужно запустить `/graphify` до шага 3A.

## Шаг 1 — Показать обзор файлов по категориям и директориям

```bash
$(cat .graphify_python) -c "
import json
from pathlib import Path
from collections import Counter

detect = json.loads(Path('.graphify_detect.json').read_text())
files = detect.get('files', {})

print('=== Обзор корпуса ===')
print(f'Всего файлов: {detect[\"total_files\"]}')
print(f'Всего слов: {detect[\"total_words\"]:,}')
print()

for category in ('code', 'document', 'paper', 'image'):
    file_list = files.get(category, [])
    if not file_list:
        continue
    print(f'--- {category.upper()} ({len(file_list)} файлов) ---')
    # Группируем по директориям верхнего уровня
    dirs = Counter()
    for f in file_list:
        parts = Path(f).parts
        top_dir = parts[0] if len(parts) > 1 else '.'
        dirs[top_dir] += 1
    for d, count in dirs.most_common(15):
        print(f'  {d}/ — {count} файлов')
    if len(dirs) > 15:
        print(f'  ... и ещё {len(dirs) - 15} директорий')
    print()
"
```

## Шаг 2 — Спросить пользователя

Покажи результат и спроси:

> Какие файлы отправить на семантическую экстракцию? Варианты:
>
> 1. **Все файлы** — полная экстракция (эквивалент `/semantic-all`)
> 2. **Только документы** — docs + papers + images, без code (эквивалент `/semantic-docs`)
> 3. **Конкретные директории** — укажи директории через пробел (например: `docs/ specs/ README.md`)
> 4. **Конкретные файлы** — укажи пути к файлам
> 5. **По паттерну** — glob-паттерн (например: `**/*.md`, `docs/**/*.yaml`)

Дождись ответа пользователя.

## Шаг 3 — Сформировать список файлов

В зависимости от выбора пользователя:

**Вариант 1 (все):** берём все файлы из всех категорий:
```python
selected = [f for files in detect['files'].values() for f in files]
```

**Вариант 2 (документы):** берём только document + paper + image:
```python
selected = []
for cat in ('document', 'paper', 'image'):
    selected.extend(detect['files'].get(cat, []))
```

**Вариант 3 (директории):** фильтруем файлы по указанным директориям:
```python
dirs = user_dirs  # список директорий от пользователя
selected = [f for files in detect['files'].values() for f in files
            if any(f.startswith(d) for d in dirs)]
```

**Вариант 4 (конкретные файлы):** используем указанные пути напрямую.

**Вариант 5 (паттерн):** используем glob для фильтрации:
```python
import fnmatch
pattern = user_pattern
all_files = [f for files in detect['files'].values() for f in files]
selected = [f for f in all_files if fnmatch.fnmatch(f, pattern)]
```

Запиши отфильтрованный список и покажи пользователю:

```bash
$(cat .graphify_python) -c "
import json
from graphify.cache import check_semantic_cache
from pathlib import Path

# selected_files задаётся на основе выбора пользователя
selected_files = $SELECTED_FILES_JSON

cached_nodes, cached_edges, cached_hyperedges, uncached = check_semantic_cache(selected_files)

if cached_nodes or cached_edges or cached_hyperedges:
    Path('.graphify_cached.json').write_text(json.dumps({'nodes': cached_nodes, 'edges': cached_edges, 'hyperedges': cached_hyperedges}))
Path('.graphify_uncached.txt').write_text('\n'.join(uncached))

print(f'Режим: ВЫБОРОЧНЫЙ')
print(f'Выбрано файлов: {len(selected_files)}')
print(f'Из кеша: {len(selected_files)-len(uncached)}')
print(f'Нужна экстракция: {len(uncached)}')
"
```

Подтверди у пользователя: "Будет обработано N файлов (~X агентов, ~Ys). Продолжить?"

## Шаг 4 — Разбить на чанки и запустить субагентов

Загрузи файлы из `.graphify_uncached.txt`. Разбей на чанки по 20-25 файлов. Изображения — каждое в отдельный чанк.

Запусти ВСЕ субагенты одним сообщением через @agent:

```
@agent Чанк 1 из N: [промпт экстракции с FILE_LIST]
@agent Чанк 2 из N: [промпт экстракции с FILE_LIST]
...
```

Промпт для каждого субагента:

```
You are a graphify extraction subagent. Read the files listed and extract a knowledge graph fragment.
Output ONLY valid JSON matching the schema below - no explanation, no markdown fences, no preamble.

Files (chunk CHUNK_NUM of TOTAL_CHUNKS):
FILE_LIST

Rules:
- EXTRACTED: relationship explicit in source (import, call, citation, "see §3.2")
- INFERRED: reasonable inference (shared data structure, implied dependency)
- AMBIGUOUS: uncertain - flag for review, do not omit

Code files: focus on semantic edges AST cannot find (call relationships, shared data, arch patterns).
  Do not re-extract imports - AST already has those.
Doc/paper files: extract named concepts, entities, citations. Also extract rationale — sections that explain WHY a decision was made, trade-offs chosen, or design intent. These become nodes with `rationale_for` edges pointing to the concept they explain.
Image files: use vision to understand what the image IS - do not just OCR.

confidence_score is REQUIRED on every edge (EXTRACTED=1.0, INFERRED=0.6-0.9, AMBIGUOUS=0.1-0.3).
Maximum 3 hyperedges per chunk.

Output exactly this JSON:
{"nodes":[{"id":"filestem_entityname","label":"Human Readable Name","file_type":"code|document|paper|image","source_file":"relative/path","source_location":null,"source_url":null,"captured_at":null,"author":null,"contributor":null}],"edges":[{"source":"node_id","target":"node_id","relation":"calls|implements|references|cites|conceptually_related_to|shares_data_with|semantically_similar_to|rationale_for","confidence":"EXTRACTED|INFERRED|AMBIGUOUS","confidence_score":1.0,"source_file":"relative/path","source_location":null,"weight":1.0}],"hyperedges":[{"id":"snake_case_id","label":"Human Readable Label","nodes":["node_id1","node_id2","node_id3"],"relation":"participate_in|implement|form","confidence":"EXTRACTED|INFERRED","confidence_score":0.75,"source_file":"relative/path"}],"input_tokens":0,"output_tokens":0}
```

## Шаг 5 — Собрать результаты, закешировать, смержить

```bash
$(cat .graphify_python) -c "
import json
from graphify.cache import save_semantic_cache
from pathlib import Path

new = json.loads(Path('.graphify_semantic_new.json').read_text()) if Path('.graphify_semantic_new.json').exists() else {'nodes':[],'edges':[],'hyperedges':[]}
saved = save_semantic_cache(new.get('nodes', []), new.get('edges', []), new.get('hyperedges', []))
print(f'Закешировано: {saved} файлов')
"
```

```bash
$(cat .graphify_python) -c "
import json
from pathlib import Path

cached = json.loads(Path('.graphify_cached.json').read_text()) if Path('.graphify_cached.json').exists() else {'nodes':[],'edges':[],'hyperedges':[]}
new = json.loads(Path('.graphify_semantic_new.json').read_text()) if Path('.graphify_semantic_new.json').exists() else {'nodes':[],'edges':[],'hyperedges':[]}

all_nodes = cached['nodes'] + new.get('nodes', [])
all_edges = cached['edges'] + new.get('edges', [])
all_hyperedges = cached.get('hyperedges', []) + new.get('hyperedges', [])
seen = set()
deduped = []
for n in all_nodes:
    if n['id'] not in seen:
        seen.add(n['id'])
        deduped.append(n)

merged = {'nodes': deduped, 'edges': all_edges, 'hyperedges': all_hyperedges,
          'input_tokens': new.get('input_tokens', 0), 'output_tokens': new.get('output_tokens', 0)}
Path('.graphify_semantic.json').write_text(json.dumps(merged, indent=2))
print(f'Семантика (выборочно): {len(deduped)} нод, {len(all_edges)} рёбер ({len(cached[\"nodes\"])} из кеша, {len(new.get(\"nodes\",[]))} новых)')
"
```

## Шаг 6 — Merge AST + Semantic

```bash
$(cat .graphify_python) -c "
import json
from pathlib import Path

ast = json.loads(Path('.graphify_ast.json').read_text())
sem = json.loads(Path('.graphify_semantic.json').read_text())

seen = {n['id'] for n in ast['nodes']}
merged_nodes = list(ast['nodes'])
for n in sem['nodes']:
    if n['id'] not in seen:
        merged_nodes.append(n)
        seen.add(n['id'])

merged = {'nodes': merged_nodes, 'edges': ast['edges'] + sem['edges'],
          'hyperedges': sem.get('hyperedges', []),
          'input_tokens': sem.get('input_tokens', 0), 'output_tokens': sem.get('output_tokens', 0)}
Path('.graphify_extract.json').write_text(json.dumps(merged, indent=2))
print(f'Итого: {len(merged_nodes)} нод, {len(merged[\"edges\"])} рёбер (AST: {len(ast[\"nodes\"])} + Semantic: {len(sem[\"nodes\"])})')
"
```

Очисти временные файлы: `rm -f .graphify_cached.json .graphify_uncached.txt .graphify_semantic_new.json`

После merge выведи итоговую статистику и предложи запустить Step 4 (build + cluster + report).
