# Парсеры архитектурных и API-артефактов

graphify парсит архитектурные артефакты и API-спецификации наравне с исходным кодом. Все парсеры построены на регулярных выражениях — без внешних YAML или grammar-библиотек. Результат — стандартные node/edge структуры graphify, идентичные тем, что генерирует tree-sitter для кода.

## Поддерживаемые форматы

### OpenAPI (`.yaml`, `.yml`)

Файл определяется как OpenAPI, если в первых 20 строках есть `openapi: 3.x`. Парсер извлекает:

- **Эндпоинты** — записи из секции `paths:` (например `/api/users`) → ноды типа `endpoint`
- **Операции** — значения `operationId` → ноды типа `operation`
- **Схемы** — записи из `components/schemas` → ноды типа `schema`
- **Ссылки** — `$ref: '#/components/schemas/...'` создают рёбра `references` между эндпоинтом и целевой схемой

**Multi-file поддержка:** Если `$ref` указывает на внешний файл (например `../models/Dto.yaml#/components/schemas/Dto`), резолвер рекурсивно подтягивает содержимое и извлекает схемы. Поддерживаются цепочки на 3+ уровней глубины.

### AsyncAPI (`.yaml`, `.yml`)

Файл определяется как AsyncAPI, если в первых 20 строках есть `asyncapi:`. Парсер извлекает:

- **Каналы** — записи из секции `channels:` → ноды типа `channel`
- **Операции** — блоки `publish`, `subscribe`, `send`, `receive` → ноды типа `operation`, связанные с каналом рёбрами `has_operation`
- **Сообщения** — ссылки `$ref` на `components/messages` или `components/schemas` → ноды типа `message` и рёбра `references`

**Multi-file поддержка:** Аналогично OpenAPI — внешние `$ref` на `channel.yaml`, модели и shared-схемы резолвятся рекурсивно. Защита от циклических ссылок через `_visited` set.

### DBML (`.dbml`)

Database Markup Language — парсер извлекает:

- **Таблицы** — блоки `Table tablename { ... }` → ноды типа `table`
- **Колонки** — определения колонок внутри таблиц → ноды типа `column`, связанные с таблицей рёбрами `has_column`
- **Внешние ключи** — строки `Ref: orders.user_id > users.id` → рёбра `foreign_key` между таблицами

**Enterprise-возможности:**
- Quoted identifiers: `Table "kful_schema.kful_opportunities"` — кавычки корректно обрабатываются
- Inline refs: `column_name type [ref: > table.column]` — извлекаются FK прямо из определения колонки
- Named FKs: `Ref fk_name: table_a.col > table_b.col` — именованные ссылки

### PlantUML (`.puml`, `.plantuml`, `.pu`)

Парсер поддерживает три типа диаграмм:

#### Class / Component диаграммы
- **Сущности** — `class`, `interface`, `component`, `actor` → ноды соответствующих типов
- **Связи** — стрелочная нотация:
  - `-->` — `association`
  - `--|>` — `inheritance`
  - `..>` — `dependency`
  - `--*` — `composition`
  - `--o` — `aggregation`

#### Sequence диаграммы
- **Участники** — `participant "Name" as Alias`, `actor`, `queue` → ноды типа `participant` / `actor`
- **Сообщения** — `->` (message), `<->` (bidirectional), `<--` / `-->` (return)
- **Устойчивость к синтаксису** — `activate/deactivate`, `box/end box`, `loop/end`, `alt/else/end`, `note`, `ref over`, `destroy`, `autonumber`, `!include`, `[[links]]` — не крашат парсер

#### Activity диаграммы
- **Действия** — `:Текст действия;` → ноды типа `action`
- **Цветные действия** — `#pink:Ошибка;`, `#blue:Переход;` → цвет убирается, label сохраняется
- **Решения** — `if (Условие?) then` → ноды типа `decision`
- **Устойчивость** — `start/stop/kill`, вложенные `if/else/endif` (до 4+ уровней), `!pragma`, комментарии (`'`) — обрабатываются корректно

## Структура нод в graph.json

Каждый парсер генерирует стандартные graphify-ноды и рёбра:

```json
{
  "nodes": [
    {"id": "openapi_petstore_api_pets", "label": "/api/pets", "type": "endpoint", "file": "petstore.yaml"},
    {"id": "openapi_petstore_pet", "label": "Pet", "type": "schema", "file": "petstore.yaml"},
    {"id": "dbml_kful_schema_kful_opportunities", "label": "kful_schema.kful_opportunities", "type": "table", "file": "schema.dbml"},
    {"id": "plantuml_search_получение_запроса", "label": "Получение запроса на поиск данных", "type": "action", "file": "search.puml"}
  ],
  "edges": [
    {"source": "openapi_petstore_api_pets", "target": "openapi_petstore_pet", "type": "references", "label": "$ref"}
  ]
}
```

Node ID строятся через `_make_id(prefix, file_stem, name)` — стабильные и уникальные. Кириллические символы сохраняются в ID.

## Как использовать

Просто укажите graphify на директорию с артефактами:

```bash
graphify ./my-project
```

graphify автоматически определяет `.yaml`, `.yml`, `.dbml`, `.puml`, `.plantuml`, `.pu` файлы, классифицирует их и направляет в нужный парсер. YAML-файлы, не являющиеся OpenAPI/AsyncAPI-спецификациями, классифицируются как документы.

## Cross-file `$ref` resolver

Для multi-file OpenAPI/AsyncAPI спецификаций резолвер:

1. Находит все `$ref:` ссылки на внешние файлы
2. Рекурсивно подтягивает содержимое файлов
3. Встраивает его в основной документ
4. Передаёт результат в соответствующий парсер

Поддерживаемые форматы `$ref`:
- `$ref: ../models/Dto.yaml#/components/schemas/Dto`
- `$ref: ./channel.yaml`
- `$ref: ../../shared/Model.yaml#/components/schemas/Model`

Защита от циклов: каждый файл резолвится максимум один раз (через `_visited` set).
