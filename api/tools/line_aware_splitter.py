from __future__ import annotations

from copy import deepcopy
from typing import Sequence, List

from adalflow.core.component import DataComponent
from adalflow.core.types import Document


SPLITTER_VERSION = 2


class LineAwareTextSplitter(DataComponent):
    """Split documents into line-based chunks while preserving line ranges.

    This splitter is intentionally simple and deterministic:
    - `chunk_size` and `chunk_overlap` are interpreted as *number of lines*
    - `start_line`/`end_line` are 1-indexed and inclusive
    - Adds `chunk_index` and `splitter_version` to meta_data
    """

    def __init__(self, chunk_size: int = 120, chunk_overlap: int = 30, **_: object) -> None:
        super().__init__()
        if chunk_size <= 0:
            raise ValueError("chunk_size must be > 0")
        if chunk_overlap < 0:
            raise ValueError("chunk_overlap must be >= 0")
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be < chunk_size")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def __call__(self, documents: Sequence[Document]) -> Sequence[Document]:
        output: List[Document] = []

        for doc in documents:
            if not getattr(doc, "text", None):
                continue

            # Keep line endings so the chunk text matches original formatting.
            lines = doc.text.splitlines(keepends=True)
            if not lines:
                continue

            base_meta = deepcopy(getattr(doc, "meta_data", {}) or {})
            file_path = base_meta.get("file_path")

            step = self.chunk_size - self.chunk_overlap
            chunk_index = 0
            start = 0
            while start < len(lines):
                end = min(start + self.chunk_size, len(lines))

                chunk_text = "".join(lines[start:end])
                # Convert to 1-indexed inclusive line numbers.
                start_line = start + 1
                end_line = end

                meta = deepcopy(base_meta)
                meta.update(
                    {
                        "file_path": file_path,
                        "start_line": start_line,
                        "end_line": end_line,
                        "chunk_index": chunk_index,
                        "splitter_version": SPLITTER_VERSION,
                    }
                )

                output.append(Document(text=chunk_text, meta_data=meta))

                chunk_index += 1
                start += step

        return output
