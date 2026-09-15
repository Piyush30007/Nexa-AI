import os
import sys

# Prevent Logfire from prompting interactively during tests without credentials
os.environ["LOGFIRE_SEND_TO_LOGFIRE"] = "false"
os.environ["LOGFIRE_NON_INTERACTIVE"] = "true"
os.environ["LOGFIRE_IGNORE_NO_CONFIG"] = "1"

import unittest
from unittest.mock import patch, MagicMock

# Ensure workspace root and backend directory are in sys.path
workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
backend_dir = os.path.join(workspace_root, "backend")
myenv2_site = r"C:\Users\Piyush Singh\anaconda3\envs\myenv2\Lib\site-packages"
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)
if backend_dir not in sys.path:
    sys.path.insert(1, backend_dir)
if os.path.exists(myenv2_site) and myenv2_site not in sys.path:
    sys.path.append(myenv2_site)

from app.ingestion.Preprocessing.cleaner import preprocess_text


class TestPreprocessor(unittest.TestCase):

    def test_1_normal_text(self):
        sample = "Nexa AI Enterprise is an agentic RAG solution for enterprise workflows."
        result = preprocess_text(sample)
        self.assertEqual(result, sample)

    def test_2_multiple_spaces(self):
        sample = "This    sentence   has     excessive    spaces   between words."
        expected = "This sentence has excessive spaces between words."
        self.assertEqual(preprocess_text(sample), expected)

    def test_3_tabs(self):
        sample = "Column1\t\tColumn2\tColumn3"
        expected = "Column1 Column2 Column3"
        self.assertEqual(preprocess_text(sample), expected)

    def test_4_excessive_blank_lines(self):
        sample = "Paragraph 1\n\n\n\n\n\nParagraph 2\n\n\nParagraph 3"
        expected = "Paragraph 1\n\nParagraph 2\n\nParagraph 3"
        self.assertEqual(preprocess_text(sample), expected)

    def test_5_heading_preservation(self):
        sample = "# System Overview\n\n## Component Details\n\n### Ingestion Pipeline"
        self.assertEqual(preprocess_text(sample), sample)

    def test_6_bullet_preservation(self):
        sample = "- Standard hyphen bullet\n* Asterisk bullet\n• Unicode round bullet"
        self.assertEqual(preprocess_text(sample), sample)

    def test_7_numbered_list_preservation(self):
        sample = "1. First step\n2. Second step\n3. Final step"
        self.assertEqual(preprocess_text(sample), sample)

    def test_8_punctuation_preservation(self):
        sample = "Hello, world! Is this working? Yes; it's 100% verified (and checked: 'done')."
        self.assertEqual(preprocess_text(sample), sample)

    def test_9_empty_string(self):
        self.assertEqual(preprocess_text(""), "")
        self.assertEqual(preprocess_text("    \n\t   \n  "), "")

    def test_10_none_input(self):
        self.assertEqual(preprocess_text(None), "")

    def test_11_technical_content_preservation(self):
        sample = "Run `kubectl get pods -n kube-system` or call `http://127.0.0.1:8000/api/v1`."
        self.assertEqual(preprocess_text(sample), sample)

    def test_12_processor_integration(self):
        """Verify processor.py calls preprocess_text before chunk_text."""
        from backend.app.ingestion import processor

        with patch.object(processor, "parse_pdf", return_value="Raw  text   with   spaces") as mock_parse, \
             patch.object(processor, "preprocess_text", wraps=preprocess_text) as mock_preprocess, \
             patch.object(processor, "chunk_text", return_value=["chunk1"]) as mock_chunk, \
             patch.object(processor, "save_processed_locally", return_value="dummy_path"), \
             patch.object(processor, "embed_texts", return_value=[[0.1] * 10]), \
             patch.object(processor.qdrant_client, "upsert"):

            processor.process_file("dummy.pdf", "dummy.pdf", "test_source")

            # Verify parse_pdf was called
            mock_parse.assert_called_once_with("dummy.pdf")
            # Verify preprocess_text was called with raw text
            mock_preprocess.assert_called_once_with("Raw  text   with   spaces")
            # Verify chunk_text received cleaned text (multiple spaces collapsed)
            mock_chunk.assert_called_once_with("Raw text with spaces")


if __name__ == "__main__":
    unittest.main(verbosity=2)
