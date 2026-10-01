"""
Unit tests for the product-knowledge loader (assistant knowledge base).

These are pure tests (no DB, no OpenAI): frontmatter parsing, upsert
planning, and validation of the real shipped knowledge/product files.
"""

import pytest

from app.models.knowledge_base import KnowledgeSourceType
from app.services.rag.product_knowledge import (
    PRODUCT_KNOWLEDGE_DIR,
    ProductDoc,
    load_product_docs,
    load_screen_map,
    load_tool_registry,
    parse_product_markdown,
    plan_upserts,
)

VALID_MD = """---
reference: EI-TEST
title: "Test: a sample doc"
source_type: product_guide
summary: A sample summary.
keywords: [one, two words, "three"]
categories: [cat_a]
---

Body content long enough to be meaningful for the knowledge base entry.
"""


class TestParseProductMarkdown:
    def test_parses_valid_file(self):
        doc = parse_product_markdown(VALID_MD, "test.md")
        assert doc.reference == "EI-TEST"
        assert doc.title == "Test: a sample doc"
        assert doc.summary == "A sample summary."
        assert doc.keywords == ["one", "two words", "three"]
        assert doc.categories == ["cat_a"]
        assert doc.content.startswith("Body content")
        assert doc.source_file == "test.md"

    def test_content_hash_changes_with_body(self):
        doc_a = parse_product_markdown(VALID_MD, "a.md")
        doc_b = parse_product_markdown(VALID_MD + "\nExtra line.", "b.md")
        assert doc_a.content_hash != doc_b.content_hash

    def test_rejects_missing_frontmatter(self):
        with pytest.raises(ValueError, match="missing frontmatter"):
            parse_product_markdown("no frontmatter here", "bad.md")

    def test_rejects_missing_required_key(self):
        text = VALID_MD.replace("summary: A sample summary.\n", "")
        with pytest.raises(ValueError, match="missing"):
            parse_product_markdown(text, "bad.md")

    def test_rejects_wrong_source_type(self):
        text = VALID_MD.replace("product_guide", "gst_rule")
        with pytest.raises(ValueError, match="source_type"):
            parse_product_markdown(text, "bad.md")

    def test_rejects_empty_body(self):
        text = VALID_MD.split("---\n\nBody")[0] + "---\n\n"
        with pytest.raises(ValueError, match="empty body"):
            parse_product_markdown(text, "bad.md")


class TestPlanUpserts:
    def _doc(self, reference: str, content: str) -> ProductDoc:
        return ProductDoc(
            reference=reference, title="t", summary="s", content=content
        )

    def test_new_changed_and_unchanged_are_separated(self):
        doc_new = self._doc("EI-NEW", "new content")
        doc_changed = self._doc("EI-CHANGED", "changed content")
        doc_same = self._doc("EI-SAME", "same content")

        existing = {
            "EI-CHANGED": "stale-hash",
            "EI-SAME": doc_same.content_hash,
        }
        plan = plan_upserts([doc_new, doc_changed, doc_same], existing)

        assert plan["create"] == [doc_new]
        assert plan["update"] == [doc_changed]
        assert plan["unchanged"] == [doc_same]

    def test_empty_inputs(self):
        plan = plan_upserts([], {})
        assert plan == {"create": [], "update": [], "unchanged": []}


class TestShippedKnowledgeFiles:
    """Validates the real files in knowledge/product/ (acts as a lint gate)."""

    def test_all_markdown_files_parse(self):
        docs = load_product_docs()
        assert len(docs) >= 20, "expected the full product knowledge set"
        for doc in docs:
            assert doc.reference.startswith("EI-")
            assert len(doc.content) > 200, f"{doc.source_file} body too short"
            assert doc.keywords, f"{doc.source_file} has no keywords"

    def test_references_are_unique(self):
        docs = load_product_docs()
        refs = [d.reference for d in docs]
        assert len(refs) == len(set(refs))

    def test_screen_map_shape(self):
        screen_map = load_screen_map()
        intents = screen_map["intents"]
        assert "notices_list" in intents and "settings_billing" in intents
        for name, intent in intents.items():
            assert intent.get("label"), f"intent {name} missing label"
            assert "web" in intent and "mobile" in intent, f"intent {name} incomplete"
            # web-only intents must explain themselves for mobile users
            if intent["mobile"] is None:
                assert intent.get("webOnlyNote"), f"web-only intent {name} needs webOnlyNote"

    def test_tool_registry_shape(self):
        registry = load_tool_registry()
        read_names = {tool["name"] for tool in registry["read_tools"]}
        assert {"get_notices", "get_notice", "get_upcoming_deadlines"} <= read_names
        for tool in registry["read_tools"]:
            assert tool["method"] == "GET", f"read tool {tool['name']} must be GET"
            assert tool["path"].startswith("/api/v1/")
        kinds = {action["kind"] for action in registry["confirm_actions"]}
        assert {"auto_draft", "create_task"} <= kinds
        # no destructive verbs anywhere in the registry
        for action in registry["confirm_actions"]:
            assert action["method"] in ("POST", "PUT")
            assert "delete" not in action["path"].lower()

    def test_source_type_enum_has_product_guide(self):
        assert KnowledgeSourceType.PRODUCT_GUIDE.value == "product_guide"

    def test_knowledge_dir_exists(self):
        assert PRODUCT_KNOWLEDGE_DIR.is_dir()
