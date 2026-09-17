import unittest

from app.ingestion.Chunking.splitter import chunk_text


class TestChunkText(unittest.TestCase):

    def test_empty_text(self):
        result = chunk_text("")
        self.assertEqual(result, [])

    def test_short_text(self):
        text = "This is a short document."
        result = chunk_text(text)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], text)

    def test_text_smaller_than_chunk_size(self):
        text = "A" * 100
        result = chunk_text(text, chunk_size=1500, overlap=200)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], text)

    def test_long_text(self):
        text = "A" * 3000
        result = chunk_text(text, chunk_size=1500, overlap=200)

        self.assertGreater(len(result), 1)

        for chunk in result:
            self.assertLessEqual(len(chunk), 1500)

    def test_overlap(self):
        text = "A" * 3000
        result = chunk_text(text, chunk_size=1000, overlap=200)

        self.assertEqual(result[0][-200:], result[1][:200])

    def test_no_empty_chunks(self):
        text = "A" * 3000
        result = chunk_text(text, chunk_size=1000, overlap=200)

        for chunk in result:
            self.assertTrue(chunk)

    def test_invalid_chunk_size(self):
        with self.assertRaises(ValueError):
            chunk_text("hello", chunk_size=0)

    def test_invalid_overlap(self):
        with self.assertRaises(ValueError):
            chunk_text("hello", chunk_size=100, overlap=100)


if __name__ == "__main__":
    unittest.main()