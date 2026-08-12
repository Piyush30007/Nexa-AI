from pathlib import Path

from database import SessionLocal, Document, Chunk
from config import settings


def reset_rag():
    db = SessionLocal()

    try:
        # ---------------------------------------------
        # 1. Delete all uploaded documents
        # ---------------------------------------------
        # Because Document.chunks has:
        # cascade="all, delete-orphan"
        #
        # deleting Documents also deletes their Chunks.

        documents = db.query(Document).all()

        print(f"Found {len(documents)} documents.")

        for document in documents:
            print(f"Deleting: {document.filename}")
            db.delete(document)

        db.commit()

        print("SQLite documents and chunks deleted.")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

    # ---------------------------------------------
    # 2. Delete persisted FAISS index
    # ---------------------------------------------

    index_path = Path(settings.index_dir) / "faiss.index"

    if index_path.exists():
        index_path.unlink()
        print(f"Deleted FAISS index: {index_path}")
    else:
        print("FAISS index does not exist.")

    print("\nRAG reset complete.")


if __name__ == "__main__":
    reset_rag()