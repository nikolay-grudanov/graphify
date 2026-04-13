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
KFUL_SCHEMA = FIXTURES / "kful_schema.dbml"
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


# ── extract_dbml enterprise tests (quoted identifiers, inline refs, named FKs) ──


class TestExtractDbmlEnterprise:
    """Test DBML parser against a real enterprise schema with quoted identifiers,
    inline column refs, named foreign keys, and 30 tables."""

    @pytest.fixture(autouse=True)
    def _parse(self):
        self.result = extract_dbml(KFUL_SCHEMA)
        self.tables = {n["label"] for n in self.result["nodes"] if n["type"] == "table"}
        self.columns = {n["label"] for n in self.result["nodes"] if n["type"] == "column"}
        self.fk_edges = [e for e in self.result["edges"] if e["type"] == "foreign_key"]
        self.col_edges = [e for e in self.result["edges"] if e["type"] == "has_column"]

    def test_finds_all_30_tables(self):
        expected_tables = {
            "amounts_for_routing", "auto_routing_settings",
            "autoclose_opportunity_settings", "branch_exception_for_routing",
            "databasechangelog", "databasechangeloglock",
            "document_groups", "document_types", "documents",
            "idp_answers", "idp_arisk_condition_answer",
            "idp_shareholder_risk_types",
            "kful_category_types", "kful_deal_types",
            "kful_opportunities", "kful_opportunity_categories",
            "kful_opportunity_desks", "kful_opportunity_folders",
            "kful_opportunity_processing_state_types",
            "kful_opportunity_products", "kful_opportunity_team_members",
            "kful_product_state_types", "kful_product_types",
            "kful_sales_method_types", "kful_state_types",
            "kful_team_role_types",
            "outbox", "retirement_reason_types",
            "routing_product_groups", "routing_product_types",
        }
        assert self.tables == expected_tables, (
            f"Missing: {expected_tables - self.tables}, "
            f"Extra: {self.tables - expected_tables}"
        )

    def test_quoted_table_names_parsed(self):
        # All tables in kful_schema.dbml use quoted names like Table "name"
        assert "kful_opportunities" in self.tables
        assert "amounts_for_routing" in self.tables
        assert "databasechangeloglock" in self.tables

    def test_quoted_column_names_parsed(self):
        # Columns use "quoted" names: "code" varchar(64)
        for col in (
            "amounts_for_routing.code",
            "amounts_for_routing.desk_code",
            "kful_opportunities.pprb_id",
            "kful_opportunities.shareholder_risk_criteria_type_code",
            "documents.document_type_code",
        ):
            assert col in self.columns, f"{col!r} not found"

    def test_large_table_columns_count(self):
        # kful_opportunities has 42 columns
        opp_cols = [c for c in self.columns if c.startswith("kful_opportunities.")]
        assert len(opp_cols) >= 40, f"Expected >=40 columns for kful_opportunities, got {len(opp_cols)}"

    def test_databasechangelog_no_indexes_section(self):
        # databasechangelog has no Indexes block — 14 columns, all should be found
        cols = [c for c in self.columns if c.startswith("databasechangelog.") and not c.startswith("databasechangeloglock.")]
        assert len(cols) >= 14, f"Expected >=14 columns for databasechangelog, got {len(cols)}"

    def test_standalone_named_quoted_fk_refs(self):
        # Ref "fk_document_types2document_groups":"document_groups"."code" < "document_types"."document_group_code"
        fk_labels = {e["label"] for e in self.fk_edges}
        expected_fks = [
            "document_groups.code -> document_types.document_group_code",
            "document_types.code -> documents.document_type_code",
            "kful_opportunity_folders.object_id -> documents.kful_opportunities_folder_id",
            "documents.object_id -> idp_answers.document_id",
            "retirement_reason_types.code -> kful_state_types.retirement_reason_type_code",
            "routing_product_groups.code -> routing_product_types.group_code",
        ]
        for fk in expected_fks:
            assert fk in fk_labels, f"FK {fk!r} not found; got {sorted(fk_labels)}"

    def test_kful_opportunities_standalone_fk_refs(self):
        # Multiple FKs pointing to/from kful_opportunities
        fk_labels = {e["label"] for e in self.fk_edges}
        expected = [
            "kful_state_types.code -> kful_opportunities.kful_state_type_code",
            "kful_opportunity_processing_state_types.code -> kful_opportunities.processing_state_type_code",
            "retirement_reason_types.code -> kful_opportunities.retirement_reason_type_code",
            "kful_opportunities.object_id -> kful_opportunity_categories.kful_opportunity_id",
            "kful_opportunities.object_id -> kful_opportunity_desks.kful_opportunity_id",
            "kful_opportunities.object_id -> kful_opportunity_products.kful_opportunity_id",
            "kful_opportunities.object_id -> kful_opportunity_team_members.kful_opportunity_id",
        ]
        for fk in expected:
            assert fk in fk_labels, f"FK {fk!r} not found"

    def test_inline_refs_extracted(self):
        # kful_opportunities has inline refs:
        #   ref: > idp_shareholder_risk_types.code
        #   ref: > kful_deal_types.code
        fk_labels = {e["label"] for e in self.fk_edges}
        assert "kful_opportunities.ai_agent_shareholder_risk_code -> idp_shareholder_risk_types.code" in fk_labels
        assert "kful_opportunities.kful_deal_type_code -> kful_deal_types.code" in fk_labels

    def test_total_fk_count(self):
        # 17 standalone Ref lines + 2 inline refs = 19 total
        assert len(self.fk_edges) == 19, f"Expected 19 FK edges, got {len(self.fk_edges)}"

    def test_has_column_edges_match_columns(self):
        assert len(self.col_edges) == len(self.columns), (
            f"has_column edges ({len(self.col_edges)}) != columns ({len(self.columns)})"
        )


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
