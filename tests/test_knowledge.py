from tlamatini.knowledge import KnowledgeBase


def test_lexical_fallback_returns_relevant_document(tmp_path):
    knowledge = KnowledgeBase(
        "data/historia_mexica.json",
        "unused-in-test",
        str(tmp_path / "qdrant"),
        3,
    )
    knowledge.initialize_semantic_index = lambda: False
    results = knowledge.search("chinampas agricultura lago")
    assert results[0]["id"] == "DOC-04"
    assert results[0]["source"]
