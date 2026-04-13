# Custom Architecture & API Artifact Parsers

graphify can parse architecture and API definition files alongside your source code. These parsers use regex-based extraction (no external YAML or grammar libraries required) to produce the same node/edge graph structures as the tree-sitter code extractors.

## Supported Formats

### OpenAPI (`.yaml`, `.yml`)

Files are detected as OpenAPI when the first 20 lines contain `openapi: 3.x`. The parser extracts:

- **Endpoints** — path entries under `paths:` (e.g. `/api/users`) become nodes of type `endpoint`
- **Operations** — `operationId` values become nodes of type `operation`
- **Schemas** — entries under `components/schemas` become nodes of type `schema`
- **References** — `$ref: '#/components/schemas/...'` entries create `references` edges linking the referencing endpoint to the target schema

### AsyncAPI (`.yaml`, `.yml`)

Files are detected as AsyncAPI when the first 20 lines contain `asyncapi:`. The parser extracts:

- **Channels** — entries under `channels:` become nodes of type `channel`
- **Operations** — `publish`, `subscribe`, `send`, and `receive` blocks become nodes of type `operation`, linked to their parent channel via `has_operation` edges
- **Messages** — `$ref` references to `components/messages` or `components/schemas` create `message` nodes and `references` edges

### DBML (`.dbml`)

Database Markup Language files are parsed for:

- **Tables** — `Table tablename { ... }` blocks become nodes of type `table`
- **Columns** — column definitions inside table blocks become nodes of type `column`, connected to their table via `has_column` edges
- **Foreign keys** — `Ref: orders.user_id > users.id` lines create `foreign_key` edges between the referenced tables

### PlantUML (`.puml`, `.plantuml`, `.pu`)

PlantUML diagram files are parsed for:

- **Entities** — `class`, `interface`, `component`, and `actor` declarations become nodes with corresponding types
- **Relationships** — arrow notations are mapped to semantic edge types:
  - `-->` — `association`
  - `--|>` — `inheritance`
  - `..>` — `dependency`
  - `--*` — `composition`
  - `--o` — `aggregation`

## How nodes appear in graph.json

Each parser produces standard graphify nodes and edges:

```json
{
  "nodes": [
    {"id": "openapi_petstore_api_pets", "label": "/api/pets", "type": "endpoint", "file": "petstore.yaml"},
    {"id": "openapi_petstore_pet", "label": "Pet", "type": "schema", "file": "petstore.yaml"}
  ],
  "edges": [
    {"source": "openapi_petstore_api_pets", "target": "openapi_petstore_pet", "type": "references", "label": "$ref"}
  ]
}
```

Node IDs are built with `_make_id(prefix, file_stem, name)` to guarantee uniqueness and stability across runs.

## How to use

Simply point graphify at a folder that contains these files alongside your code:

```bash
graphify ./my-project
```

graphify automatically detects `.yaml`, `.yml`, `.dbml`, `.puml`, `.plantuml`, and `.pu` files, classifies them, and routes them to the appropriate parser. YAML files that are not OpenAPI or AsyncAPI specs are classified as documents rather than code and are not sent through these parsers.
