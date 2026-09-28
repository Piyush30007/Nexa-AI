import unittest
from app.services.retrieval.bm25_service import SimpleBM25, _tokenize, BM25SearchService
from app.services.retrieval.hybrid_service import rrf_fuse


class TestHybridRetrieval(unittest.TestCase):

    def test_bm25_exact_keyword_matching(self):
        corpus = [
            "Employees are entitled to 20 days of paid vacation per calendar year.",
            "Document HR-POL-99 describes the remote work equipment reimbursement process.",
            "Security standard ISO-27001 requires password changes every 90 days."
        ]
        bm25 = SimpleBM25(corpus)
        
        # Test exact code query
        scores = bm25.get_scores(_tokenize("HR-POL-99"))
        self.assertGreater(scores[1], scores[0])
        self.assertGreater(scores[1], scores[2])
        
        # Test acronym query
        iso_scores = bm25.get_scores(_tokenize("ISO-27001"))
        self.assertGreater(iso_scores[2], iso_scores[0])

    def test_rrf_fusion(self):
        dense_results = [
            {"content": "Policy on vacation time", "source": "doc1.pdf", "score": 0.89},
            {"content": "Policy on remote work", "source": "doc2.pdf", "score": 0.75},
        ]
        sparse_results = [
            {"content": "Policy on remote work", "source": "doc2.pdf", "score": 4.5},
            {"content": "Policy on IT equipment", "source": "doc3.pdf", "score": 3.2},
        ]
        
        fused = rrf_fuse(dense_results, sparse_results, k=60, limit=5)
        
        # "Policy on remote work" appears in both, so its RRF score should be highest
        self.assertEqual(fused[0]["content"], "Policy on remote work")
        self.assertTrue(len(fused) == 3)


if __name__ == "__main__":
    unittest.main()
