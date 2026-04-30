"""Backfill embeddings for existing memory_items.

Usage:
    cd backend && python -m scripts.backfill_memory_embeddings
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys

# Add parent directory to path so imports work when run as script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.core.config import settings
from app.memory.embedder import MemoryEmbedder
from app.storage.database import SessionLocal
from app.storage.models import MemoryItem

logger = logging.getLogger("chatchat.backfill")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


async def main() -> int:
    if not settings.memory_embedding_enabled:
        print("memory_embedding_enabled is False, nothing to do.")
        return 0

    embedder = MemoryEmbedder(settings)
    db = SessionLocal()
    try:
        items = db.scalars(
            select(MemoryItem).where(
                MemoryItem.embedding.is_(None),
                MemoryItem.status == "active",
                MemoryItem.active.is_(True),
            )
        ).all()

        if not items:
            print("No memory items need backfilling.")
            return 0

        print(f"Backfilling {len(items)} memory items...")
        success = 0
        failed = 0
        for item in items:
            try:
                embedding = await embedder.embed_memory(
                    title=item.title,
                    detail=item.detail,
                    tags=item.tags,
                )
                item.embedding = embedding
                db.add(item)
                db.flush()
                success += 1
                if success % 10 == 0:
                    db.commit()
                    print(f"  ...{success} done")
            except Exception as exc:
                failed += 1
                logger.warning("Failed to embed memory %d: %s", item.id, exc)

        db.commit()
        print(f"Done. Success: {success}, Failed: {failed}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
