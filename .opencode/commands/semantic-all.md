---
description: "Step 3B семантическая экстракция по ВСЕМ файлам (code + docs + papers + images)"
---

# Семантическая экстракция — все файлы

Запусти Step 3B (семантическую экстракцию) по **всем** файлам из `.graphify_detect.json`.

## Предусловия

- Убедись что файл `.graphify_detect.json` существует (Step 2 detect уже выполнен).
- Убедись что файл `.graphify_ast.json` существует (Step 3A AST уже выполнен).
- Если какого-то файла нет — сообщи пользователю что сначала нужно запустить `/graphify` до шага 3A.

## Шаг 1 — Проверить кеш

```bash
$(cat .graphify_python) -c "
import json
from graphify.cache import check_semantic_cache
from pathlib import Path

detect = json.loads(Path('.graphify_detect.json').read_text())
all_files = [f for files in detect['files'].values() for f in files]

cached_nodes, cached_edges, cached_hyperedges, uncached = check_semantic_cache(all_files)

if cached_nodes or cached_edges or cached_hyperedges:
    Path('.graphify_cached.json').write_text(json.dumps({'nodes': cached_nodes, 'edges': cached_edges, 'hyperedges': cached_hyperedges}))
Path('.graphify_uncached.txt').write_text('\n'.join(uncached))
print(f'Режим: ВСЕ ФАЙЛЫ')
print(f'Всего файлов: {len(all_files)}')
print(f'Из кеша: {len(all_files)-len(uncached)}')
print(f'Нужна экстракция: {len(uncached)}')
"
```

Если все файлы в кеше — перейди сразу к шагу merge.

## Шаг 2 — Разбить на чанки и запустить субагентов

Загрузи файлы из `.graphify_uncached.txt`. Разбей на чанки по 20-25 файлов. Изображения — каждое в отдельный чанк. Группируй файлы из одной директории вместе.

Выведи оценку времени: "Семантическая экстракция: ~N файлов → X агентов, ~Ys"

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

## Шаг 3 — Собрать результаты, закешировать, смержить

Собери JSON из всех чанков, сохрани в кеш, смержи с кешированными результатами в `.graphify_semantic.json`.

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
print(f'Семантика: {len(deduped)} нод, {len(all_edges)} рёбер ({len(cached[\"nodes\"])} из кеша, {len(new.get(\"nodes\",[]))} новых)')
"
```

## Шаг 4 — Merge AST + Semantic

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
