"""Tests for custom artifact parsers (OpenAPI, AsyncAPI, DBML, PlantUML)."""
from pathlib import Path
import tempfile

import pytest

from graphify.extract import (
    extract_openapi,
    extract_asyncapi,
    extract_dbml,
    extract_plantuml,
    extract_yaml_dispatch,
)
from graphify.detect import classify_file, classify_yaml, FileType


FIXTURES = Path(__file__).parent / "fixtures"
PETSTORE = FIXTURES / "petstore.yaml"
STREETLIGHTS = FIXTURES / "streetlights.yaml"
SOCIAL = FIXTURES / "social.dbml"
ARCHITECTURE = FIXTURES / "architecture.puml"


# ── detect.py tests ──────────────────────────────────────────────────────────


class TestClassifyFile:
    def test_classify_openapi_yaml(self):
        assert classify_file(PETSTORE) == FileType.CODE

    def test_classify_asyncapi_yaml(self):
        assert classify_file(STREETLIGHTS) == FileType.CODE

    def test_classify_plain_yaml(self, tmp_path):
        plain = tmp_path / "config.yaml"
        plain.write_text("name: test\nversion: 1\n")
        assert classify_file(plain) == FileType.DOCUMENT

    def test_classify_dbml(self):
        assert classify_file(SOCIAL) == FileType.CODE

    def test_classify_puml(self):
        assert classify_file(ARCHITECTURE) == FileType.CODE


# ── extract_openapi tests ────────────────────────────────────────────────────


class TestExtractOpenapi:
    @pytest.fixture(autouse=True)
    def _parse(self):
        self.result = extract_openapi(PETSTORE)

    def test_openapi_returns_nodes_and_edges(self):
        assert "nodes" in self.result
        assert "edges" in self.result

    def test_openapi_finds_endpoints(self):
        labels = {n["label"] for n in self.result["nodes"] if n["type"] == "endpoint"}
        for ep in ("/pet", "/pet/findByStatus", "/store/inventory", "/user", "/user/login"):
            assert ep in labels, f"endpoint {ep!r} not found; got {sorted(labels)}"

    def test_openapi_finds_operations(self):
        labels = {n["label"] for n in self.result["nodes"] if n["type"] == "operation"}
        for op in ("updatePet", "addPet", "findPetsByStatus", "getPetById",
                    "getInventory", "placeOrder", "createUser", "loginUser"):
            assert op in labels, f"operation {op!r} not found; got {sorted(labels)}"

    def test_openapi_finds_schemas(self):
        labels = {n["label"] for n in self.result["nodes"] if n["type"] == "schema"}
        for schema in ("Pet", "Order", "User", "Category", "Tag", "ApiResponse", "Error"):
            assert schema in labels, f"schema {schema!r} not found; got {sorted(labels)}"

    def test_openapi_finds_ref_edges(self):
        ref_edges = [e for e in self.result["edges"] if e["type"] == "references"]
        assert len(ref_edges) > 0, "No $ref edges found"


# ── extract_asyncapi tests ───────────────────────────────────────────────────


class TestExtractAsyncapi:
    @pytest.fixture(autouse=True)
    def _parse(self):
        self.result = extract_asyncapi(STREETLIGHTS)

    def test_asyncapi_returns_nodes_and_edges(self):
        assert "nodes" in self.result
        assert "edges" in self.result

    def test_asyncapi_finds_channels(self):
        labels = {n["label"] for n in self.result["nodes"] if n["type"] == "channel"}
        for ch in ("lightingMeasured", "lightTurnOn", "lightTurnOff", "lightsDim"):
            assert ch in labels, f"channel {ch!r} not found; got {sorted(labels)}"

    def test_asyncapi_finds_ref_messages(self):
        labels = {n["label"] for n in self.result["nodes"] if n["type"] == "message"}
        assert len(labels) > 0, "No message nodes found from $ref references"

    def test_asyncapi_has_edges(self):
        assert len(self.result["edges"]) > 0, "No edges found"


# ── extract_dbml tests ───────────────────────────────────────────────────────


class TestExtractDbml:
    @pytest.fixture(autouse=True)
    def _parse(self):
        self.result = extract_dbml(SOCIAL)

    def test_dbml_finds_tables(self):
        labels = {n["label"] for n in self.result["nodes"] if n["type"] == "table"}
        for tbl in ("follows", "users", "posts"):
            assert tbl in labels, f"table {tbl!r} not found; got {sorted(labels)}"

    def test_dbml_finds_columns(self):
        labels = {n["label"] for n in self.result["nodes"] if n["type"] == "column"}
        for col in ("users.id", "users.username", "posts.title", "posts.user_id"):
            assert col in labels, f"column {col!r} not found; got {sorted(labels)}"

    def test_dbml_finds_has_column_edges(self):
        col_edges = [e for e in self.result["edges"] if e["type"] == "has_column"]
        assert len(col_edges) > 0, "No has_column edges found"

    def test_dbml_finds_foreign_keys(self):
        fk_edges = [e for e in self.result["edges"] if e["type"] == "foreign_key"]
        assert len(fk_edges) >= 2, f"Expected at least 2 foreign_key edges, got {len(fk_edges)}"
        # Check posts -> users and users -> follows FK relationships exist
        pairs = {(e["source"], e["target"]) for e in fk_edges}
        from graphify.extract import _make_id
        posts_id = _make_id("dbml", "social", "posts")
        users_id = _make_id("dbml", "social", "users")
        follows_id = _make_id("dbml", "social", "follows")
        assert (posts_id, users_id) in pairs, f"posts->users FK not found; got {pairs}"
        assert (users_id, follows_id) in pairs, f"users->follows FK not found; got {pairs}"


# ── extract_plantuml tests ───────────────────────────────────────────────────


class TestExtractPlantuml:
    @pytest.fixture(autouse=True)
    def _parse(self):
        self.result = extract_plantuml(ARCHITECTURE)

    def _node_labels(self, ntype=None):
        if ntype:
            return {n["label"] for n in self.result["nodes"] if n["type"] == ntype}
        return {n["label"] for n in self.result["nodes"]}

    def _edge_types(self):
        return {e["type"] for e in self.result["edges"]}

    def test_plantuml_finds_classes(self):
        labels = self._node_labels("class")
        for cls in ("UserService", "OrderService", "PaymentGateway",
                     "UserRepository", "OrderRepository"):
            assert cls in labels, f"class {cls!r} not found; got {sorted(labels)}"

    def test_plantuml_finds_interfaces(self):
        labels = self._node_labels("interface")
        for iface in ("IRepository", "IService"):
            assert iface in labels, f"interface {iface!r} not found; got {sorted(labels)}"

    def test_plantuml_finds_actors(self):
        labels = self._node_labels("actor")
        for act in ("Customer", "Admin"):
            assert act in labels, f"actor {act!r} not found; got {sorted(labels)}"

    def test_plantuml_finds_components(self):
        labels = self._node_labels("component")
        for comp in ("AuthModule", "NotificationModule"):
            assert comp in labels, f"component {comp!r} not found; got {sorted(labels)}"

    def test_plantuml_finds_inheritance(self):
        assert "inheritance" in self._edge_types()

    def test_plantuml_finds_association(self):
        assert "association" in self._edge_types()

    def test_plantuml_finds_dependency(self):
        assert "dependency" in self._edge_types()

    def test_plantuml_finds_composition(self):
        assert "composition" in self._edge_types()

    def test_plantuml_finds_aggregation(self):
        assert "aggregation" in self._edge_types()


# ── extract_yaml_dispatch tests ──────────────────────────────────────────────


class TestYamlDispatch:
    def test_yaml_dispatch_openapi(self):
        result = extract_yaml_dispatch(PETSTORE)
        direct = extract_openapi(PETSTORE)
        assert result == direct

    def test_yaml_dispatch_asyncapi(self):
        result = extract_yaml_dispatch(STREETLIGHTS)
        direct = extract_asyncapi(STREETLIGHTS)
        assert result == direct

    def test_yaml_dispatch_plain_yaml(self, tmp_path):
        plain = tmp_path / "config.yaml"
        plain.write_text("name: test\nversion: 1\n")
        result = extract_yaml_dispatch(plain)
        assert result == {"nodes": [], "edges": []}
