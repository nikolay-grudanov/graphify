OAS_NS = "http://spec.openapis.org/oas/ontology#"

# Node mapping: (file_type, source_file pattern) → OWL class local name
# First match wins. Order matters for priority.
MAPPING_RULES: list[dict] = [
    {"file_type": "document",  "source_file_pattern": r".*\.md$",           "owl_class": "Document"},
    {"file_type": "openapi",   "source_file_pattern": r".*\.(yaml|yml|json)$", "owl_class": "Service"},
    {"file_type": "asyncapi",  "source_file_pattern": r".*\.(yaml|yml)$",   "owl_class": "KafkaChannel"},
    {"file_type": "dbml",      "source_file_pattern": r".*\.dbml$",         "owl_class": "DbTable"},
    {"file_type": "code",      "source_file_pattern": r".*\.py$",           "owl_class": "Schema"},  # Python module → Schema (code structure)
    {"file_type": "code",      "source_file_pattern": r".*\.(ts|tsx|js|jsx)$", "owl_class": "Schema"},
    {"file_type": "code",      "source_file_pattern": r".*\.(java|kt)$",    "owl_class": "Schema"},
    {"file_type": "plantuml",  "source_file_pattern": r".*\.(puml|plantuml|pu)$", "owl_class": "Document"},
]

# Fallback for unmatched nodes
DEFAULT_OWL_CLASS = "Document"  # oas:Document as base fallback

# For nodes without source_file
EXTERNAL_OWL_CLASS = "Schema"  # external dependencies

# Edge mapping: graphify relation → OWL property local name
EDGE_MAPPING: dict[str, str] = {
    "references":     "schema",        # oas:schema — references a schema
    "imports":        "schema",
    "imports_from":   "schema",
    "calls":          "supportedOperation",
    "contains":       "hasField",
    "has_column":     "hasField",
    "has_operation":  "supportedOperation",
    "method":         "method",
    "foreign_key":    "referencedTable",
    "inherits":       "schema",
    "defines":        "definesChannel",
    "depends_on":     "schema",
    "association":    "schema",
    "dependency":     "schema",
    "composition":    "hasField",
    "aggregation":    "hasField",
    "inheritance":    "schema",
    "external_ref":   "schema",
    "flow":           "supportedOperation",
    "_default":       "mentionedInDocument",
}
