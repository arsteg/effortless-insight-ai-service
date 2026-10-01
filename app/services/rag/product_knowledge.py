"""
Product knowledge loader for the in-app assistant.

Reads the markdown files in knowledge/product/ (frontmatter + body),
upserts them into the knowledge base as source_type=product_guide,
and exposes the structured screen-map / tool-registry JSON files.

The markdown frontmatter is a controlled flat format authored in this
repo (no nested YAML), so a minimal parser is used instead of adding
a YAML dependency.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import select

from app.core.database import get_session_maker
from app.models.knowledge_base import KnowledgeBaseEntry, KnowledgeSourceType
from app.services.rag.knowledge_builder import KnowledgeBuilder
from app.services.rag.vector_store import VectorStore

logger = structlog.get_logger()

# knowledge/product lives at the repo root, next to app/
PRODUCT_KNOWLEDGE_DIR = Path(__file__).resolve().parents[3] / "knowledge" / "product"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


@dataclass
class ProductDoc:
    """A parsed product-knowledge markdown file."""

    reference: str
    title: str
    summary: str
    content: str
    keywords: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    source_file: str = ""

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()


def _parse_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1]
    return value.strip()


def _parse_list(value: str) -> List[str]:
    value = value.strip()
    if not (value.startswith("[") and value.endswith("]")):
        raise ValueError(f"expected inline list, got: {value!r}")
    inner = value[1:-1].strip()
    if not inner:
        return []
    return [_parse_scalar(item) for item in inner.split(",") if item.strip()]


def parse_product_markdown(text: str, source_file: str = "") -> ProductDoc:
    """
    Parse one product-knowledge markdown file (frontmatter + body).

    Raises ValueError on missing frontmatter or required keys.
    """
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError(f"{source_file}: missing frontmatter block")

    raw_frontmatter, body = match.group(1), match.group(2).strip()
    fields: Dict[str, str] = {}
    for line in raw_frontmatter.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"{source_file}: invalid frontmatter line: {line!r}")
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()

    required = ("reference", "title", "summary", "keywords", "categories", "source_type")
    missing = [key for key in required if key not in fields]
    if missing:
        raise ValueError(f"{source_file}: frontmatter missing {missing}")

    source_type = _parse_scalar(fields["source_type"])
    if source_type != KnowledgeSourceType.PRODUCT_GUIDE.value:
        raise ValueError(
            f"{source_file}: source_type must be "
            f"{KnowledgeSourceType.PRODUCT_GUIDE.value!r}, got {source_type!r}"
        )
    if not body:
        raise ValueError(f"{source_file}: empty body")

    return ProductDoc(
        reference=_parse_scalar(fields["reference"]),
        title=_parse_scalar(fields["title"]),
        summary=_parse_scalar(fields["summary"]),
        content=body,
        keywords=_parse_list(fields["keywords"]),
        categories=_parse_list(fields["categories"]),
        source_file=source_file,
    )


def load_product_docs(directory: Optional[Path] = None) -> List[ProductDoc]:
    """Load and parse every knowledge/product/*.md file."""
    directory = directory or PRODUCT_KNOWLEDGE_DIR
    docs: List[ProductDoc] = []
    for path in sorted(directory.glob("*.md")):
        docs.append(parse_product_markdown(path.read_text(encoding="utf-8"), path.name))

    references = [doc.reference for doc in docs]
    duplicates = {ref for ref in references if references.count(ref) > 1}
    if duplicates:
        raise ValueError(f"duplicate references in product knowledge: {sorted(duplicates)}")
    return docs


def plan_upserts(
    docs: List[ProductDoc],
    existing_hashes: Dict[str, str],
) -> Dict[str, List[ProductDoc]]:
    """
    Decide what to do per doc given {reference: content_hash} of existing entries.

    Pure function so the decision logic is unit-testable without a database.
    """
    plan: Dict[str, List[ProductDoc]] = {"create": [], "update": [], "unchanged": []}
    for doc in docs:
        if doc.reference not in existing_hashes:
            plan["create"].append(doc)
        elif existing_hashes[doc.reference] != doc.content_hash:
            plan["update"].append(doc)
        else:
            plan["unchanged"].append(doc)
    return plan


async def upsert_product_knowledge(
    directory: Optional[Path] = None,
    reindex_unchanged: bool = False,
) -> Dict[str, int]:
    """
    Upsert all product-knowledge docs into knowledge_base_entries and
    (re)index their embeddings. Returns counts per outcome.
    """
    docs = load_product_docs(directory)
    builder = KnowledgeBuilder()
    vector_store = VectorStore()
    source_type = KnowledgeSourceType.PRODUCT_GUIDE.value

    session_maker = get_session_maker()
    async with session_maker() as session:
        result = await session.execute(
            select(KnowledgeBaseEntry).where(
                KnowledgeBaseEntry.source_type == source_type
            )
        )
        existing = {entry.reference: entry for entry in result.scalars().all()}

    existing_hashes = {
        ref: (entry.extra_data or {}).get("content_hash", "")
        for ref, entry in existing.items()
    }
    plan = plan_upserts(docs, existing_hashes)

    for doc in plan["create"]:
        async with session_maker() as session:
            entry = KnowledgeBaseEntry(
                source_type=source_type,
                reference=doc.reference,
                title=doc.title,
                content=doc.content,
                summary=doc.summary,
                keywords=doc.keywords,
                categories=doc.categories,
                extra_data={"content_hash": doc.content_hash, "source_file": doc.source_file},
                is_active=True,
                is_indexed=False,
            )
            session.add(entry)
            await session.commit()
            await session.refresh(entry)
        await builder.index_entry(entry)
        logger.info("Product knowledge created", reference=doc.reference)

    for doc in plan["update"]:
        async with session_maker() as session:
            entry = await session.get(KnowledgeBaseEntry, existing[doc.reference].id)
            entry.title = doc.title
            entry.content = doc.content
            entry.summary = doc.summary
            entry.keywords = doc.keywords
            entry.categories = doc.categories
            entry.extra_data = {"content_hash": doc.content_hash, "source_file": doc.source_file}
            entry.is_indexed = False
            entry.version = (entry.version or 1) + 1
            await session.commit()
            await session.refresh(entry)
        # Drop stale chunks before reindexing the new content
        await vector_store.delete_by_source(source_type=source_type, source_id=entry.id)
        await builder.index_entry(entry, force=True)
        logger.info("Product knowledge updated", reference=doc.reference)

    if reindex_unchanged:
        for doc in plan["unchanged"]:
            await builder.index_entry(existing[doc.reference], force=True)

    counts = {key: len(value) for key, value in plan.items()}
    logger.info("Product knowledge upsert complete", **counts)
    return counts


def _load_json(filename: str, directory: Optional[Path] = None) -> Dict[str, Any]:
    directory = directory or PRODUCT_KNOWLEDGE_DIR
    return json.loads((directory / filename).read_text(encoding="utf-8"))


def load_screen_map(directory: Optional[Path] = None) -> Dict[str, Any]:
    """The deterministic navigation map used for assistant 'navigate' actions."""
    return _load_json("screen-map.json", directory)


def load_tool_registry(directory: Optional[Path] = None) -> Dict[str, Any]:
    """The declarative tool registry (read tools + confirm actions)."""
    return _load_json("tools.json", directory)
