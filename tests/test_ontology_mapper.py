"""Tests for ontology mapper — T-01 through T-10+."""
from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_GRAPH = FIXTURES / "sample_graph.json"
SAMPLE_ONTOLOGY = FIXTURES / "sample_ontology.ttl"


@pytest.fixture
def graph_json():
    return json.loads(SAMPLE_GRAPH.read_text(encoding="utf-8"))


@pytest.fixture
def ontology_graph():
    from graphify.ontology_mapper import load_ontology
    return load_ontology(SAMPLE_ONTOLOGY)


# ---------------------------------------------------------------------------
# T-01: Document nodes → oas:Document
# ---------------------------------------------------------------------------
class TestT01DocumentNode:
    def test_document_md_maps_to_document(self):
        from graphify.ontology_mapper import _match_node_class
        node = {"file_type": "document", "source_file": "dictionaries/IB/bond_types.md"}
        assert _match_node_class(node) == "Document"

    def test_document_node_in_rdf(self, graph_json, ontology_graph):
        from rdflib import RDF, Namespace
        from graphify.ontology_mapper import map_graph_to_ontology
        OAS = Namespace("http://spec.openapis.org/oas/ontology#")

        g = map_graph_to_ontology(graph_json, ontology_graph)
        base = "http://project.local/graph#"
        node_uri = g.value(predicate=RDF.type, object=OAS.Document)
        assert node_uri is not None


# ---------------------------------------------------------------------------
# T-02: Code nodes (Python) → oas:Schema
# ---------------------------------------------------------------------------
class TestT02CodeNode:
    def test_python_code_maps_to_schema(self):
        from graphify.ontology_mapper import _match_node_class
        node = {"file_type": "code", "source_file": "services/calc.py"}
        assert _match_node_class(node) == "Schema"

    def test_ts_code_maps_to_schema(self):
        from graphify.ontology_mapper import _match_node_class
        node = {"file_type": "code", "source_file": "app/main.ts"}
        assert _match_node_class(node) == "Schema"

    def test_java_code_maps_to_schema(self):
        from graphify.ontology_mapper import _match_node_class
        node = {"file_type": "code", "source_file": "src/Main.java"}
        assert _match_node_class(node) == "Schema"


# ---------------------------------------------------------------------------
# T-03: OpenAPI nodes → oas:Service
# ---------------------------------------------------------------------------
class TestT03OpenAPINode:
    def test_openapi_yaml_maps_to_service(self):
        from graphify.ontology_mapper import _match_node_class
        node = {"file_type": "openapi", "source_file": "openapi/bonds.yaml"}
        assert _match_node_class(node) == "Service"

    def test_openapi_yml_maps_to_service(self):
        from graphify.ontology_mapper import _match_node_class
        node = {"file_type": "openapi", "source_file": "api/spec.yml"}
        assert _match_node_class(node) == "Service"

    def test_openapi_json_maps_to_service(self):
        from graphify.ontology_mapper import _match_node_class
        node = {"file_type": "openapi", "source_file": "api/spec.json"}
        assert _match_node_class(node) == "Service"


# ---------------------------------------------------------------------------
# T-04: Edge "references" → oas:schema
# ---------------------------------------------------------------------------
class TestT04EdgeReferences:
    def test_references_maps_to_schema(self):
        from graphify.ontology_mapper import _match_edge_property
        assert _match_edge_property("references") == "schema"

    def test_imports_maps_to_schema(self):
        from graphify.ontology_mapper import _match_edge_property
        assert _match_edge_property("imports") == "schema"

    def test_foreign_key_maps_to_referenced_table(self):
        from graphify.ontology_mapper import _match_edge_property
        assert _match_edge_property("foreign_key") == "referencedTable"

    def test_edge_in_rdf(self, graph_json, ontology_graph):
        from rdflib import Namespace, URIRef
        from graphify.ontology_mapper import map_graph_to_ontology
        OAS = Namespace("http://spec.openapis.org/oas/ontology#")
        BASE = Namespace("http://project.local/graph#")

        g = map_graph_to_ontology(graph_json, ontology_graph)
        # calc_service --references--> bond_types should become oas:schema
        assert (BASE["calc_service"], OAS.schema, BASE["bond_types"]) in g


# ---------------------------------------------------------------------------
# T-05: Unknown relation → oas:mentionedInDocument (fallback)
# ---------------------------------------------------------------------------
class TestT05UnknownRelation:
    def test_unknown_relation_fallback(self):
        from graphify.ontology_mapper import _match_edge_property
        assert _match_edge_property("totally_unknown_relation") == "mentionedInDocument"

    def test_unknown_edge_in_rdf(self, graph_json, ontology_graph):
        from rdflib import Namespace
        from graphify.ontology_mapper import map_graph_to_ontology
        OAS = Namespace("http://spec.openapis.org/oas/ontology#")
        BASE = Namespace("http://project.local/graph#")

        g = map_graph_to_ontology(graph_json, ontology_graph)
        assert (BASE["unknown_type_node"], OAS.mentionedInDocument, BASE["bond_types"]) in g


# ---------------------------------------------------------------------------
# T-06: Unknown file_type → oas:Document (fallback)
# ---------------------------------------------------------------------------
class TestT06UnknownFileType:
    def test_unknown_filetype_fallback(self):
        from graphify.ontology_mapper import _match_node_class
        node = {"file_type": "weird_format", "source_file": "weird/file.xyz"}
        assert _match_node_class(node) == "Document"


# ---------------------------------------------------------------------------
# T-07: CLI help still works (no regression)
# ---------------------------------------------------------------------------
class TestT07CLIHelp:
    def test_help_contains_ontology(self):
        result = subprocess.run(
            [sys.executable, "-m", "graphify", "--help"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0
        assert "ontology" in result.stdout


# ---------------------------------------------------------------------------
# T-08: Invalid ontology TTL → warning logged, no crash
# ---------------------------------------------------------------------------
class TestT08InvalidOntology:
    def test_invalid_ttl_no_crash(self, tmp_path):
        from graphify.ontology_mapper import load_ontology
        bad_file = tmp_path / "bad.ttl"
        bad_file.write_text("this is not valid N-Triples at all <<<>>>", encoding="utf-8")

        g = load_ontology(bad_file)
        # Should return an empty graph, not crash
        assert len(g) == 0

    def test_invalid_ttl_logs_warning(self, tmp_path, caplog):
        from graphify.ontology_mapper import load_ontology
        bad_file = tmp_path / "bad.ttl"
        bad_file.write_text("this is not valid N-Triples at all <<<>>>", encoding="utf-8")

        with caplog.at_level(logging.WARNING):
            load_ontology(bad_file)
        assert any("Failed to parse ontology" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# T-09: Mixed project — all nodes typed
# ---------------------------------------------------------------------------
class TestT09MixedProject:
    def test_all_nodes_typed(self, graph_json, ontology_graph):
        from rdflib import RDF, Namespace
        from graphify.ontology_mapper import map_graph_to_ontology
        OAS = Namespace("http://spec.openapis.org/oas/ontology#")
        BASE = Namespace("http://project.local/graph#")

        g = map_graph_to_ontology(graph_json, ontology_graph)

        for node in graph_json["nodes"]:
            node_uri = BASE[node["id"]]
            types = list(g.objects(node_uri, RDF.type))
            assert len(types) >= 1, f"Node {node['id']} has no rdf:type"

    def test_expected_types(self, graph_json, ontology_graph):
        from rdflib import RDF, Namespace
        from graphify.ontology_mapper import map_graph_to_ontology
        OAS = Namespace("http://spec.openapis.org/oas/ontology#")
        BASE = Namespace("http://project.local/graph#")

        g = map_graph_to_ontology(graph_json, ontology_graph)

        expected = {
            "bond_types": OAS.Document,
            "calc_service": OAS.Schema,
            "api_bonds": OAS.Service,
            "opportunity_state": OAS.KafkaChannel,
            "kful_schema": OAS.DbTable,
            "unknown_type_node": OAS.Document,
            "external_dep": OAS.Schema,  # no source_file → EXTERNAL_OWL_CLASS
        }
        for node_id, expected_type in expected.items():
            assert (BASE[node_id], RDF.type, expected_type) in g, \
                f"Node {node_id} should be {expected_type}"


# ---------------------------------------------------------------------------
# T-10: enrich_json — owl_class and owl_uri fields
# ---------------------------------------------------------------------------
class TestT10EnrichJSON:
    def test_enriched_nodes_have_owl_class(self, graph_json):
        from graphify.ontology_mapper import enrich_json
        enriched = enrich_json(graph_json)

        for node in enriched["nodes"]:
            assert "owl_class" in node, f"Node {node['id']} missing owl_class"
            assert node["owl_class"].startswith("oas:"), f"owl_class should start with oas:"

    def test_enriched_nodes_have_owl_uri(self, graph_json):
        from graphify.ontology_mapper import enrich_json
        enriched = enrich_json(graph_json)

        for node in enriched["nodes"]:
            assert "owl_uri" in node, f"Node {node['id']} missing owl_uri"
            assert node["owl_uri"].startswith("http://project.local/graph#")

    def test_enriched_edges_have_owl_property(self, graph_json):
        from graphify.ontology_mapper import enrich_json
        enriched = enrich_json(graph_json)

        for edge in enriched["edges"]:
            assert "owl_property" in edge, f"Edge {edge['source']}->{edge['target']} missing owl_property"
            assert edge["owl_property"].startswith("oas:")

    def test_custom_base_uri(self, graph_json):
        from graphify.ontology_mapper import enrich_json
        custom_uri = "http://custom.local/ns#"
        enriched = enrich_json(graph_json, base_uri=custom_uri)

        for node in enriched["nodes"]:
            assert node["owl_uri"].startswith(custom_uri)


# ---------------------------------------------------------------------------
# T-11: save_ttl writes valid Turtle
# ---------------------------------------------------------------------------
class TestT11SaveTTL:
    def test_save_and_reload(self, graph_json, ontology_graph, tmp_path):
        import rdflib
        from graphify.ontology_mapper import map_graph_to_ontology, save_ttl

        g = map_graph_to_ontology(graph_json, ontology_graph)
        out = tmp_path / "output.ttl"
        save_ttl(g, out)

        assert out.exists()
        # Reload and verify
        g2 = rdflib.Graph()
        g2.parse(str(out), format="turtle")
        assert len(g2) == len(g)


# ---------------------------------------------------------------------------
# T-12: run_mapping end-to-end (CLI entry point)
# ---------------------------------------------------------------------------
class TestT12RunMapping:
    def test_run_mapping_creates_ttl(self, tmp_path):
        from graphify.ontology_mapper import run_mapping
        import shutil

        graph_path = tmp_path / "graph.json"
        shutil.copy(SAMPLE_GRAPH, graph_path)

        ontology_path = tmp_path / "ontology.ttl"
        shutil.copy(SAMPLE_ONTOLOGY, ontology_path)

        out_ttl = tmp_path / "out.ttl"
        run_mapping(graph_path, ontology_path, out_ttl)

        assert out_ttl.exists()
        content = out_ttl.read_text(encoding="utf-8")
        assert "oas:" in content or "openapis" in content

    def test_run_mapping_with_json(self, tmp_path):
        from graphify.ontology_mapper import run_mapping
        import shutil

        graph_path = tmp_path / "graph.json"
        shutil.copy(SAMPLE_GRAPH, graph_path)

        ontology_path = tmp_path / "ontology.ttl"
        shutil.copy(SAMPLE_ONTOLOGY, ontology_path)

        out_ttl = tmp_path / "out.ttl"
        run_mapping(graph_path, ontology_path, out_ttl, output_json=True)

        assert out_ttl.exists()
        json_out = out_ttl.with_suffix(".json")
        assert json_out.exists()

        enriched = json.loads(json_out.read_text(encoding="utf-8"))
        assert "owl_class" in enriched["nodes"][0]


# ---------------------------------------------------------------------------
# T-13: AsyncAPI and DBML node types
# ---------------------------------------------------------------------------
class TestT13AsyncAPIAndDBML:
    def test_asyncapi_maps_to_kafka_channel(self):
        from graphify.ontology_mapper import _match_node_class
        node = {"file_type": "asyncapi", "source_file": "kafka/channel.yaml"}
        assert _match_node_class(node) == "KafkaChannel"

    def test_dbml_maps_to_db_table(self):
        from graphify.ontology_mapper import _match_node_class
        node = {"file_type": "dbml", "source_file": "db/schema.dbml"}
        assert _match_node_class(node) == "DbTable"


# ---------------------------------------------------------------------------
# T-14: External dependencies (no source_file) → Schema
# ---------------------------------------------------------------------------
class TestT14ExternalDep:
    def test_no_source_file_maps_to_schema(self):
        from graphify.ontology_mapper import _match_node_class
        node = {"file_type": "code", "source_file": None}
        assert _match_node_class(node) == "Schema"

    def test_external_marked_as_meta(self, graph_json, ontology_graph):
        from rdflib import Literal, Namespace
        from graphify.ontology_mapper import map_graph_to_ontology
        OAS = Namespace("http://spec.openapis.org/oas/ontology#")
        BASE = Namespace("http://project.local/graph#")

        g = map_graph_to_ontology(graph_json, ontology_graph)
        assert (BASE["external_dep"], OAS.isMeta, Literal(True)) in g
