"""Vector index tests with a fake embedding model (no download) and a temporary Chroma folder."""

import chromadb
import numpy as np

from rag import config, index


class FakeModel:
    """Two-dimensional 'embeddings': texts about flaring point one way, everything else the other."""

    def __init__(self):
        self.seen = []

    def encode(self, texts, **kwargs):
        self.seen += list(texts)
        return np.array([[1.0, 0.0] if "flaring" in t else [0.0, 1.0] for t in texts])


def test_query_gets_the_bge_prefix():
    model = FakeModel()
    index._model = model
    try:
        index.encode_query("what is flaring")
    finally:
        index._model = None
    assert model.seen == [config.EMBED_QUERY_PREFIX + "what is flaring"]


def test_collections_differ_per_prefix_setting():
    assert index.collection_name(True) != index.collection_name(False)


def test_search_returns_similarity_and_split_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "VECTOR_INDEX_DIR", tmp_path)
    monkeypatch.setattr(index, "get_model", lambda: FakeModel())
    client = chromadb.PersistentClient(path=str(tmp_path))
    collection = client.create_collection(index.collection_name(True), metadata={"hnsw:space": "cosine"})
    collection.add(
        ids=["d:0", "d:1"],
        embeddings=[[1.0, 0.0], [0.0, 1.0]],
        documents=["flaring text", "other text"],
        metadatas=[{"doc_id": "d", "page": 7, "heading_path": "A > B", "section_ids": "d:1"},
                   {"doc_id": "d", "page": 8, "heading_path": "C", "section_ids": "d:2"}],
    )
    hits = index.search_vector("flaring", k=2, prefix=True)
    assert [h.chunk_id for h in hits] == ["d:0", "d:1"]  # nearest first
    assert round(hits[0].score, 3) == 1.0 and round(hits[1].score, 3) == 0.0  # similarity = 1 - distance
    assert (hits[0].doc_id, hits[0].page, hits[0].heading_path, hits[0].text) == ("d", 7, "A > B", "flaring text")
