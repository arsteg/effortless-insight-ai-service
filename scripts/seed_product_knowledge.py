"""
Seed/refresh the assistant's product knowledge in the knowledge base.

Reads knowledge/product/*.md, upserts entries (source_type=product_guide),
and indexes embeddings. Safe to re-run: unchanged files are skipped via
content hash; changed files are updated and reindexed.

Run with: python -m scripts.seed_product_knowledge [--reindex]
"""

import argparse
import asyncio

from app.core.database import init_db
from app.services.rag.product_knowledge import (
    PRODUCT_KNOWLEDGE_DIR,
    upsert_product_knowledge,
)


async def main(reindex: bool) -> None:
    print("=" * 60)
    print("Product Knowledge Seeder (assistant)")
    print(f"Source: {PRODUCT_KNOWLEDGE_DIR}")
    print("=" * 60)

    await init_db()
    counts = await upsert_product_knowledge(reindex_unchanged=reindex)

    print(
        f"\nDone. created={counts['create']} "
        f"updated={counts['update']} unchanged={counts['unchanged']}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reindex",
        action="store_true",
        help="Force re-embedding of unchanged entries as well",
    )
    args = parser.parse_args()
    asyncio.run(main(args.reindex))
