"""Regression tests that API mode does not require local ML packages."""

import builtins

from backend.config import settings
from backend.rag import embeddings, reranker
from backend.triage.features import ClinicalFeatures
from backend.triage.semantic_feature_detector import apply_semantic_feature_detection


def test_api_mode_selects_openai_embeddings_and_unique_collection(monkeypatch):
    monkeypatch.setattr(settings, "inference_mode", "api")
    monkeypatch.setattr(settings, "embedding_backend", "auto")
    monkeypatch.setattr(settings, "collection_name", "")
    assert settings.active_embedding_backend == "openai"
    assert settings.active_collection_name == "medimama_api"
    assert embeddings.embedding_dimension() == settings.openai_embedding_dimensions


def test_api_mode_skips_local_reranker(monkeypatch):
    monkeypatch.setattr(settings, "inference_mode", "api")
    monkeypatch.setattr(settings, "reranker_enabled", False)
    sample = [object()]
    assert reranker.rerank("question", sample) is sample


def test_api_mode_skips_semantic_sentence_transformer(monkeypatch):
    monkeypatch.setattr(settings, "inference_mode", "api")
    monkeypatch.setattr(settings, "semantic_models_enabled", False)
    features = ClinicalFeatures(raw_text="test", text="test", age_months=24)

    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.startswith("sentence_transformers") or name == "torch":
            raise AssertionError(f"API mode tried to import a local ML package: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    result = apply_semantic_feature_detection(features, "test")
    assert result is features
