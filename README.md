# graphify — форк с поддержкой архитектурных артефактов

Форк [safishamsi/graphify](https://github.com/safishamsi/graphify) с добавлением парсеров для enterprise-артефактов: OpenAPI, AsyncAPI, DBML, PlantUML.

> Оригинальная документация: [README_UPSTREAM.md](README_UPSTREAM.md)

## Что добавлено

Парсеры на основе регулярных выражений (без внешних YAML/grammar-библиотек) для четырёх форматов:

| Формат | Расширения | Что извлекается |
|--------|-----------|-----------------|
| OpenAPI 3.x | `.yaml` `.yml` | Эндпоинты, операции, схемы, `$ref`-связи |
| AsyncAPI | `.yaml` `.yml` | Каналы, операции (pub/sub/send/receive), сообщения |
| DBML | `.dbml` | Таблицы, колонки, FK-связи (включая quoted identifiers, inline refs, named FKs) |
| PlantUML | `.puml` `.plantuml` `.pu` | Class/component, sequence (participant, queue, arrows), activity (actions, decisions) |

### Ключевые возможности

- **Cross-file `$ref` resolver** — рекурсивный резолв внешних `$ref` ссылок для multi-file OpenAPI/AsyncAPI спецификаций с защитой от циклов
- **Enterprise DBML** — поддержка quoted identifiers (`Table "schema.name"`), inline refs, named FKs
- **PlantUML: 3 типа диаграмм** — class/component, sequence (participant, queue, actor, activate/deactivate, box), activity (`:action;`, `if/then/else`, `#color:`)
- **Unicode/кириллица** — корректная обработка кириллических идентификаторов в node ID

Подробная документация парсеров: [CUSTOM_PARSERS.md](CUSTOM_PARSERS.md)

## Установка локально

### Требования

- Python 3.10+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (рекомендуется) или pip

### Через uv (рекомендуется)

```bash
# Установка как CLI-инструмента — доступен глобально как команда graphify
uv tool install git+https://github.com/nikolay-grudanov/graphify.git@feature/custom-artifact-parsers

# Проверка
graphify --help
```

Для обновления до последней версии ветки:

```bash
uv tool install --force git+https://github.com/nikolay-grudanov/graphify.git@feature/custom-artifact-parsers
```

Удаление:

```bash
uv tool uninstall graphifyy
```

### Через pip

```bash
pip install git+https://github.com/nikolay-grudanov/graphify.git@feature/custom-artifact-parsers
```

### С дополнительными зависимостями

```bash
# MCP-сервер
uv tool install "graphifyy[mcp] @ git+https://github.com/nikolay-grudanov/graphify.git@feature/custom-artifact-parsers"

# PDF-поддержка
uv tool install "graphifyy[pdf] @ git+https://github.com/nikolay-grudanov/graphify.git@feature/custom-artifact-parsers"

# Все расширения
uv tool install "graphifyy[all] @ git+https://github.com/nikolay-grudanov/graphify.git@feature/custom-artifact-parsers"
```

### Для разработки (editable-режим)

```bash
git clone https://github.com/nikolay-grudanov/graphify.git
cd graphify
git checkout feature/custom-artifact-parsers
uv venv && source .venv/bin/activate
uv pip install -e ".[all]"
```

## Использование

```bash
# Сканирование директории с архитектурными артефактами
graphify ./my-project

# Результат
graphify-out/
├── graph.html       # интерактивный граф
├── GRAPH_REPORT.md  # отчёт: god nodes, связи, вопросы
├── graph.json       # граф для запросов
└── cache/           # SHA256-кэш (повторные запуски обрабатывают только изменения)
```

graphify автоматически определяет `.yaml`, `.yml`, `.dbml`, `.puml`, `.plantuml`, `.pu` файлы, классифицирует их (OpenAPI / AsyncAPI / plain YAML) и направляет в соответствующий парсер.

Multi-file спецификации обрабатываются автоматически — если `$ref` ссылается на соседний файл, он будет рекурсивно подтянут.

## Онтологический маппинг

Модуль `ontology_mapper` сопоставляет ноды графа graphify с классами OWL-онтологии и генерирует обогащённый граф в формате Turtle (`.ttl`).

### Установка

```bash
# Базовая установка (без rdflib)
uv tool install git+https://github.com/nikolay-grudanov/graphify.git@feature/custom-artifact-parsers

# С поддержкой онтологии
uv tool install "graphifyy[ontology] @ git+https://github.com/nikolay-grudanov/graphify.git@feature/custom-artifact-parsers"
```

### Использование

```bash
# Сначала строим граф
graphify update ./my-project

# Затем маппим на онтологию
graphify ontology graphify-out/graph.json --ttl graphify/resources/ontology/ontology.ttl

# С обогащённым JSON
graphify ontology graphify-out/graph.json --ttl ontology.ttl --json --base-uri http://my-project.local/graph#
```

### Таблица маппинга

| file_type graphify | OWL-класс онтологии |
|-------------------|---------------------|
| document (.md) | oas:Document |
| openapi (.yaml) | oas:Service |
| asyncapi (.yaml) | oas:KafkaChannel |
| dbml (.dbml) | oas:DbTable |
| code (.py, .ts, .java) | oas:Schema |
| plantuml (.puml) | oas:Document |

Подробнее: [`CUSTOM_PARSERS.md`](CUSTOM_PARSERS.md)

## Тесты

```bash
cd graphify
python -m pytest tests/test_custom_parsers.py -v
```

85 тестов покрывают все парсеры на enterprise-данных:
- OpenAPI: single-file (Petstore) + multi-file (3-уровневый `$ref` chain)
- AsyncAPI: single-file (Streetlights) + multi-file (Kafka channels, external models)
- DBML: простой (3 таблицы) + enterprise (30 таблиц, quoted identifiers, 19 FKs)
- PlantUML: class/component + sequence (4 диаграммы) + activity (вложенные if/else)

## Статус

Форк находится в стадии **боевой обкатки на промышленных примерах**. Планы:

1. Практическая проверка на реальных enterprise-репозиториях
2. По результатам — либо PR в [upstream](https://github.com/safishamsi/graphify), либо публикация в PyPI

## Коммиты

| Коммит | Описание |
|--------|----------|
| `16f907e` | feat: парсеры OpenAPI, AsyncAPI, DBML, PlantUML |
| `810d14c` | test: 30 тестов + исправление 3 багов парсеров |
| `9cbadfc` | fix: DBML — quoted identifiers, inline refs, named FKs |
| `76ea5fe` | feat: cross-file `$ref` resolver для multi-file спецификаций |
| `16c0de8` | test: multi-file OpenAPI тесты с enterprise-фикстурами |
| `3f76435` | feat: PlantUML — participant, sequence arrows |
| `0e769d4` | feat: PlantUML — queue keyword, enterprise sequence тесты |
| `720ea1a` | feat: PlantUML — activity diagram, фикс кириллицы в `_make_id` |
