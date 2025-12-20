import pytest
from adalflow.core.types import Document
from api.tools.line_aware_splitter import LineAwareTextSplitter

class TestLineAwareSplitter:
    def test_basic_splitting(self):
        # Create a document with 10 lines
        text = "\n".join([f"Line {i}" for i in range(1, 11)])
        doc = Document(text=text, meta_data={"file_path": "test.txt"})
        
        # Split with size 4, overlap 1
        # step = size - overlap = 4 - 1 = 3.
        # Start indices (0-based): 0, 3, 6, 9
        # Chunk 1: 0-4 (Lines 1-4)
        # Chunk 2: 3-7 (Lines 4-7)
        # Chunk 3: 6-10 (Lines 7-10)
        # Chunk 4: 9-10 (Lines 10) - clipped to len
        
        splitter = LineAwareTextSplitter(chunk_size=4, chunk_overlap=1)
        chunks = splitter([doc])
        
        assert len(chunks) == 4
        
        # Check Chunk 1
        assert chunks[0].meta_data["start_line"] == 1
        assert chunks[0].meta_data["end_line"] == 4
        assert "Line 1" in chunks[0].text
        assert "Line 4" in chunks[0].text
        assert "Line 5" not in chunks[0].text
        
        # Check Chunk 2 (Overlap check)
        assert chunks[1].meta_data["start_line"] == 4
        assert chunks[1].meta_data["end_line"] == 7
        assert "Line 4" in chunks[1].text  # Overlap
        
        # Check Chunk 4 (Last chunk)
        assert chunks[3].meta_data["start_line"] == 10
        assert chunks[3].meta_data["end_line"] == 10
        assert chunks[3].text.strip() == "Line 10"

    def test_metadata_preservation(self):
        doc = Document(text="L1\nL2", meta_data={"file_path": "src/main.py", "author": "me"})
        splitter = LineAwareTextSplitter(chunk_size=2, chunk_overlap=0)
        chunks = splitter([doc])
        
        assert len(chunks) == 1
        assert chunks[0].meta_data["file_path"] == "src/main.py"
        assert chunks[0].meta_data["author"] == "me"
        assert chunks[0].meta_data["splitter_version"] == 2

    def test_empty_document(self):
        doc = Document(text="", meta_data={})
        splitter = LineAwareTextSplitter()
        chunks = splitter([doc])
        assert len(chunks) == 0

    def test_invalid_config(self):
        with pytest.raises(ValueError):
            LineAwareTextSplitter(chunk_size=0)
        with pytest.raises(ValueError):
            LineAwareTextSplitter(chunk_size=10, chunk_overlap=10)
