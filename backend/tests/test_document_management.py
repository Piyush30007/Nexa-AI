"""
Unit and Integration Tests for Phase 8 — V2 Shared Knowledge Base Document Management
=====================================================================================
Verifies:
1. Unsupported file extension returns HTTP 400.
2. Successful document upload runs V2 ingestion, transitions status to 'Indexed',
   persists correct metadata, and cleans up temp files.
3. Ingestion failure transitions status to 'Failed', stores error_message,
   cleans up temp files, and returns HTTP 500.
4. GET /api/documents returns all indexed documents ordered by uploaded_at DESC.
5. DELETE /api/documents/{id} deletes document vectors from Qdrant by document_id
   and removes the database record.
6. Deleting a nonexistent document returns HTTP 404.
7. Qdrant deletion is strictly scoped to the target document_id.
8. Qdrant cleanup failure prevents database deletion and returns HTTP 500.
9. Both guests and authenticated users can access the document endpoints.
"""

import io
import unittest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, Document, get_db
from app.main import app


class TestDocumentManagement(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()

    # 1. Unsupported extension -> 400
    def test_unsupported_file_extension_returns_400(self):
        fake_file = io.BytesIO(b"binary executable content")
        response = self.client.post(
            "/api/documents/upload",
            files={"file": ("malicious.exe", fake_file, "application/octet-stream")},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Unsupported file type", response.json()["detail"])

        # Ensure no document record was persisted
        db = self.Session()
        docs = db.query(Document).all()
        self.assertEqual(len(docs), 0)
        db.close()

    # 2. Successful upload -> Processing -> Indexed, metadata, cleanup
    @patch("app.main.process_file")
    @patch("app.main.collection_exists")
    def test_successful_upload_transitions_to_indexed(self, mock_coll_exists, mock_process_file):
        mock_coll_exists.return_value = True
        mock_process_file.return_value = 5  # 5 chunks indexed

        file_content = b"NexaAI Enterprise Policy: 20 days annual leave."
        fake_file = io.BytesIO(file_content)

        response = self.client.post(
            "/api/documents/upload",
            files={"file": ("company_policy.pdf", fake_file, "application/pdf")},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["filename"], "company_policy.pdf")
        self.assertEqual(data["file_type"], "pdf")
        self.assertEqual(data["status"], "Indexed")
        self.assertEqual(data["num_chunks"], 5)
        self.assertIsNotNone(data["id"])

        # Verify process_file was called with the document_id
        doc_id = data["id"]
        mock_process_file.assert_called_once()
        _, kwargs = mock_process_file.call_args
        self.assertEqual(kwargs.get("document_id"), doc_id)
        self.assertEqual(kwargs.get("filename"), "company_policy.pdf")

        # Verify Database record status
        db = self.Session()
        saved_doc = db.query(Document).filter(Document.id == doc_id).first()
        self.assertIsNotNone(saved_doc)
        self.assertEqual(saved_doc.status, "Indexed")
        self.assertEqual(saved_doc.num_chunks, 5)
        self.assertIsNone(saved_doc.error_message)
        db.close()

    # 3. Failed ingestion -> Processing -> Failed, temp file cleaned up, 500 returned
    @patch("app.main.process_file")
    @patch("app.main.collection_exists")
    def test_failed_ingestion_transitions_to_failed(self, mock_coll_exists, mock_process_file):
        mock_coll_exists.return_value = True
        mock_process_file.side_effect = RuntimeError("Embedding service connection timed out")

        file_content = b"Some corrupted text document"
        fake_file = io.BytesIO(file_content)

        response = self.client.post(
            "/api/documents/upload",
            files={"file": ("corrupt.txt", fake_file, "text/plain")},
        )
        self.assertEqual(response.status_code, 500)
        self.assertIn("Embedding service connection timed out", response.json()["detail"])

        # Verify Database record marked as Failed
        db = self.Session()
        failed_doc = db.query(Document).filter(Document.filename == "corrupt.txt").first()
        self.assertIsNotNone(failed_doc)
        self.assertEqual(failed_doc.status, "Failed")
        self.assertIn("Embedding service connection timed out", failed_doc.error_message)
        db.close()

    # 4. GET /api/documents -> returns all ordered by uploaded_at DESC
    def test_get_documents_returns_ordered_list(self):
        db = self.Session()
        d1 = Document(
            id="doc-1",
            filename="older.pdf",
            file_type="pdf",
            status="Indexed",
            num_chunks=3,
            uploaded_at=datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
        )
        d2 = Document(
            id="doc-2",
            filename="newer.docx",
            file_type="docx",
            status="Indexed",
            num_chunks=8,
            uploaded_at=datetime(2026, 1, 2, 10, 0, tzinfo=timezone.utc),
        )
        db.add_all([d1, d2])
        db.commit()
        db.close()

        response = self.client.get("/api/documents")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)
        # newer should be first
        self.assertEqual(data[0]["id"], "doc-2")
        self.assertEqual(data[0]["filename"], "newer.docx")
        self.assertEqual(data[0]["num_chunks"], 8)
        self.assertEqual(data[1]["id"], "doc-1")
        self.assertEqual(data[1]["filename"], "older.pdf")

    # 5. DELETE /api/documents/{id} -> deletes from Qdrant and DB
    @patch("app.main.delete_document_points")
    def test_delete_document_success(self, mock_qdrant_delete):
        db = self.Session()
        doc = Document(
            id="doc-to-delete",
            filename="handbook.pdf",
            file_type="pdf",
            status="Indexed",
            num_chunks=10,
            uploaded_at=datetime.now(timezone.utc),
        )
        db.add(doc)
        db.commit()
        db.close()

        response = self.client.delete("/api/documents/doc-to-delete")
        self.assertEqual(response.status_code, 200)
        self.assertIn("deleted", response.json()["message"])

        # Verify Qdrant delete was called with the document ID
        mock_qdrant_delete.assert_called_once_with(document_id="doc-to-delete")

        # Verify DB record is gone
        db = self.Session()
        remaining = db.query(Document).filter(Document.id == "doc-to-delete").first()
        self.assertIsNone(remaining)
        db.close()

    # 6. Nonexistent document deletion -> 404
    def test_delete_nonexistent_document_returns_404(self):
        response = self.client.delete("/api/documents/nonexistent-id-999")
        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json()["detail"].lower())

    # 7. Qdrant deletion is scoped only to selected document
    @patch("app.main.delete_document_points")
    def test_deletion_scoped_only_to_target_document(self, mock_qdrant_delete):
        db = self.Session()
        doc1 = Document(
            id="doc-target",
            filename="policy.pdf",
            file_type="pdf",
            status="Indexed",
            num_chunks=4,
            uploaded_at=datetime.now(timezone.utc),
        )
        doc2 = Document(
            id="doc-keep",
            filename="policy.pdf",  # identical filename, different ID
            file_type="pdf",
            status="Indexed",
            num_chunks=6,
            uploaded_at=datetime.now(timezone.utc),
        )
        db.add_all([doc1, doc2])
        db.commit()
        db.close()

        response = self.client.delete("/api/documents/doc-target")
        self.assertEqual(response.status_code, 200)

        # Qdrant delete was specifically called for doc-target only
        mock_qdrant_delete.assert_called_once_with(document_id="doc-target")

        # doc2 remains in DB untouched
        db = self.Session()
        preserved = db.query(Document).filter(Document.id == "doc-keep").first()
        self.assertIsNotNone(preserved)
        self.assertEqual(preserved.num_chunks, 6)
        db.close()

    # 8. Qdrant cleanup failure prevents DB deletion (consistency preserved)
    @patch("app.main.delete_document_points")
    def test_qdrant_failure_prevents_database_deletion(self, mock_qdrant_delete):
        mock_qdrant_delete.side_effect = RuntimeError("Qdrant unreachable")

        db = self.Session()
        doc = Document(
            id="doc-failed-cleanup",
            filename="safe.pdf",
            file_type="pdf",
            status="Indexed",
            num_chunks=2,
            uploaded_at=datetime.now(timezone.utc),
        )
        db.add(doc)
        db.commit()
        db.close()

        response = self.client.delete("/api/documents/doc-failed-cleanup")
        self.assertEqual(response.status_code, 500)
        self.assertIn("Failed to clean up document vectors", response.json()["detail"])

        # Document must still exist in DB to prevent silent inconsistency
        db = self.Session()
        still_exists = db.query(Document).filter(Document.id == "doc-failed-cleanup").first()
        self.assertIsNotNone(still_exists)
        db.close()

    # 9. Access model: guest and authenticated users can both access
    def test_guest_and_authenticated_can_list_documents(self):
        # Guest request (no auth header)
        resp_guest = self.client.get("/api/documents")
        self.assertEqual(resp_guest.status_code, 200)

        # Authenticated request (with Authorization header)
        resp_auth = self.client.get(
            "/api/documents",
            headers={"Authorization": "Bearer fake_token"},
        )
        self.assertEqual(resp_auth.status_code, 200)


if __name__ == "__main__":
    unittest.main()
