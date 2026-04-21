"""Ontology mapper — maps graphify graph.json to OWL/TTL using ontology.ttl."""
from __future__ import annotations
import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

def load_ontology(ttl_path: Path) -> Any:
    """Load ontology.ttl, return rdflib.Graph. Graceful on errors."""
    try:
        import rdflib
    except ImportError:
        raise ImportError(
            "rdflib is required for ontology mapping. "
            "Install with: pip install graphifyy[ontology]"
        )
    g = rdflib.Graph()
    try:
        # The file is N-Triples format
        g.parse(str(ttl_path), format="nt")
    except Exception as e:
        logger.warning(f"Failed to parse ontology {ttl_path}: {e}. Continuing without validation.")
        g = rdflib.Graph()
    return g

def load_graph_json(json_path: Path) -> dict:
    """Load graphify's graph.json output."""
    return json.loads(json_path.read_text(encoding="utf-8"))

def _match_node_class(node: dict) -> str:
    """Return OWL class local name for a node based on mapping rules."""
    from graphify.ontology_rules import MAPPING_RULES, DEFAULT_OWL_CLASS, EXTERNAL_OWL_CLASS

    file_type = node.get("file_type", "")
    source_file = node.get("source_file") or ""

    if not source_file:
        return EXTERNAL_OWL_CLASS

    for rule in MAPPING_RULES:
        if rule["file_type"] == file_type and re.match(rule["source_file_pattern"], source_file):
            return rule["owl_class"]

    return DEFAULT_OWL_CLASS

def _match_edge_property(relation: str) -> str:
    """Return OWL property local name for an edge relation."""
    from graphify.ontology_rules import EDGE_MAPPING
    return EDGE_MAPPING.get(relation, EDGE_MAPPING["_default"])

def map_graph_to_ontology(
    graph_json: dict,
    ontology_graph: Any,  # rdflib.Graph
    base_uri: str = "http://project.local/graph#",
) -> Any:  # returns rdflib.Graph
    """Map graphify graph to OWL individuals using ontology classes."""
    import rdflib
    from rdflib import URIRef, Literal, Namespace, RDF, RDFS
    from graphify.ontology_rules import OAS_NS

    OAS = Namespace(OAS_NS)
    BASE = Namespace(base_uri)

    g = rdflib.Graph()
    g.bind("oas", OAS)
    g.bind("base", BASE)
    g.bind("rdfs", RDFS)

    # Map nodes
    for node in graph_json.get("nodes", []):
        node_id = node.get("id", "")
        if not node_id:
            continue

        node_uri = BASE[node_id]
        owl_class_name = _match_node_class(node)

        # rdf:type
        g.add((node_uri, RDF.type, OAS[owl_class_name]))

        # rdfs:label
        label = node.get("label", node_id)
        g.add((node_uri, RDFS.label, Literal(label)))

        # oas:hasName
        g.add((node_uri, OAS.hasName, Literal(label)))

        # Source metadata as annotation properties
        source_file = node.get("source_file")
        if source_file:
            g.add((node_uri, OAS.definedInDocument, Literal(source_file)))

        source_location = node.get("source_location")
        if source_location:
            g.add((node_uri, OAS.hasIdentifier, Literal(str(source_location))))

        author = node.get("author")
        if author:
            g.add((node_uri, OAS.hasName, Literal(author)))  # author info

        # Mark external artifacts
        if not source_file:
            g.add((node_uri, OAS.isMeta, Literal(True)))

    # Map edges
    for edge in graph_json.get("edges", []):
        source_id = edge.get("source", "")
        target_id = edge.get("target", "")
        relation = edge.get("relation", "")

        if not source_id or not target_id:
            continue

        source_uri = BASE[source_id]
        target_uri = BASE[target_id]
        property_name = _match_edge_property(relation)

        g.add((source_uri, OAS[property_name], target_uri))

        # Confidence as annotation
        confidence = edge.get("confidence")
        if confidence:
            # Use reification or just add a label note
            pass  # Skip reification for simplicity — confidence in JSON output only

    return g

def save_ttl(graph: Any, output_path: Path) -> None:
    """Serialize rdflib.Graph to Turtle file."""
    ttl_content = graph.serialize(format="turtle")
    output_path.write_text(ttl_content, encoding="utf-8")
    logger.info(f"TTL graph saved to {output_path}")

def enrich_json(graph_json: dict, base_uri: str = "http://project.local/graph#") -> dict:
    """Add owl_class and owl_uri fields to graph_json nodes and edges."""
    enriched = json.loads(json.dumps(graph_json))  # deep copy

    for node in enriched.get("nodes", []):
        owl_class = _match_node_class(node)
        node["owl_class"] = f"oas:{owl_class}"
        node["owl_uri"] = f"{base_uri}{node.get('id', '')}"

    for edge in enriched.get("edges", []):
        relation = edge.get("relation", "")
        owl_prop = _match_edge_property(relation)
        edge["owl_property"] = f"oas:{owl_prop}"

    return enriched

def run_mapping(
    graph_json_path: Path,
    ontology_path: Path,
    output_ttl_path: Path | None = None,
    output_json: bool = False,
    base_uri: str = "http://project.local/graph#",
) -> None:
    """Main entry point for ontology mapping."""
    # Load inputs
    graph_json = load_graph_json(graph_json_path)
    ontology_g = load_ontology(ontology_path)

    # Map to TTL
    result_g = map_graph_to_ontology(graph_json, ontology_g, base_uri)

    # Save TTL
    if output_ttl_path is None:
        output_ttl_path = graph_json_path.parent / "graph_ontology.ttl"
    save_ttl(result_g, output_ttl_path)

    node_count = len(graph_json.get("nodes", []))
    edge_count = len(graph_json.get("edges", []))
    print(f"Ontology mapping: {node_count} nodes, {edge_count} edges → {output_ttl_path}")

    # Optionally save enriched JSON
    if output_json:
        enriched = enrich_json(graph_json, base_uri)
        json_out = output_ttl_path.with_suffix(".json")
        json_out.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Enriched JSON → {json_out}")
