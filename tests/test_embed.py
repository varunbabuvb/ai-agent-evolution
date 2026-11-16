import numpy as np
import pytest

from ainevo.normalization.embed import (TfidfEmbedder, cluster, event_text, get_embedder, nearest_pairs, purity,
                                        similarity_matrix, sweep, tokenize)

TEXTS = ["GPT-4 OpenAI releases GPT-4", "GPT-4o OpenAI releases GPT-4o",
         "Claude 3 Anthropic releases Claude 3", "Claude 3.5 Sonnet Anthropic releases Claude 3.5 Sonnet",
         "Stargate OpenAI data centre joint venture"]


def test_tokenize_and_event_text():
    assert tokenize("GPT-4o, v0.4") == ["gpt", "4o", "v0", "4"]
    row = {"model_agent": "GPT-4", "organization": "OpenAI", "action": "", "capability": None, "category": "x"}
    assert event_text(row) == "GPT-4 OpenAI"   # category is excluded on purpose


def test_tfidf_rows_are_unit_length_and_similar_events_are_closer():
    X = TfidfEmbedder().fit_transform(TEXTS)
    assert np.allclose(np.linalg.norm(X, axis=1), 1.0)
    S = similarity_matrix(X)
    assert S[0, 1] > S[0, 2]          # GPT-4 closer to GPT-4o than to Claude 3
    assert S[2, 3] > S[2, 0]


def test_unseen_text_gives_zero_vector_not_nan():
    e = TfidfEmbedder().fit(TEXTS)
    v = e.transform(["zzz qqq"])
    assert np.all(v == 0)


def test_cluster_groups_by_family_and_threshold_controls_size():
    X = TfidfEmbedder().fit_transform(TEXTS)
    lab = cluster(X, 0.8)
    assert lab[0] == lab[1] and lab[2] == lab[3] and lab[0] != lab[2]
    assert len(set(cluster(X, 0.05))) >= len(set(cluster(X, 0.95)))
    assert list(cluster(X[:1], 0.5)) == [0]


def test_nearest_pairs_and_purity_and_sweep():
    X = TfidfEmbedder().fit_transform(TEXTS)
    i, j, s = nearest_pairs(X, 1)[0]
    assert i < j and 0 <= s <= 1
    assert purity([0, 0, 1, 1], ["a", "a", "b", "a"]) == 0.75
    sw = sweep(X, {"org": ["o", "o", "a", "a", "o"]}, thresholds=(0.3, 0.9))
    assert list(sw["threshold"]) == [0.3, 0.9] and "purity_org" in sw.columns


def test_unknown_embedder_name():
    with pytest.raises(ValueError):
        get_embedder("nope")
