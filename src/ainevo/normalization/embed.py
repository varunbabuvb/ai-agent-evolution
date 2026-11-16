"""Event embeddings + clustering prototype (owner: TS, plan T7 / Day 8).

Turns each event into a vector so that events about the same thing end up close together. It is the
"embedding similarity" part of the Day 9 linking rules (date window + entities + embedding similarity).

Two interchangeable embedders, both returning L2-normalised rows (cosine similarity = dot product):
  - 'tfidf' : TF-IDF in plain numpy. No download, no extra install. Default and the test fallback.
  - 'sbert' : sentence-transformers (default model all-MiniLM-L6-v2). Needs `pip install sentence-transformers`
              and a one-off model download; imported only when requested.
Clustering is average-linkage hierarchical clustering on cosine distance (scipy, already installed via datasketch).
"""
from __future__ import annotations

import re
from collections import Counter

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage

SBERT_MODEL = "all-MiniLM-L6-v2"


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", str(text).lower())


def event_text(row) -> str:
    """Text that represents an event: who, what, how. Works for dict / Series / Event-like rows.
    A `title` is used when the row has one (documents do, seed events do not).
    The category is deliberately NOT included: it is the label we check the clusters against."""
    g = (lambda k: row.get(k, "")) if hasattr(row, "get") else (lambda k: getattr(row, k, ""))
    parts = [g("model_agent"), g("organization"), g("action"), g("capability"), g("title")]
    return " ".join(str(p) for p in parts if p is not None and str(p) != "nan" and str(p).strip())


class TfidfEmbedder:
    """Sublinear-tf, smooth-idf TF-IDF, L2-normalised. fit() on training texts only (no leakage)."""

    name = "tfidf"

    def fit(self, texts) -> "TfidfEmbedder":
        docs = [set(tokenize(t)) for t in texts]
        df = Counter(tok for d in docs for tok in d)
        self.vocab_ = {tok: i for i, tok in enumerate(sorted(df))}
        n = len(docs)
        self.idf_ = np.array([np.log((1 + n) / (1 + df[t])) + 1.0 for t in sorted(df)])
        return self

    def transform(self, texts) -> np.ndarray:
        X = np.zeros((len(texts), len(self.vocab_)))
        for r, t in enumerate(texts):
            for tok, c in Counter(tokenize(t)).items():
                j = self.vocab_.get(tok)
                if j is not None:
                    X[r, j] = (1.0 + np.log(c)) * self.idf_[j]
        return _l2(X)

    def fit_transform(self, texts) -> np.ndarray:
        return self.fit(texts).transform(texts)


class SentenceEmbedder:
    """sentence-transformers wrapper (optional dependency, imported lazily)."""

    name = "sbert"

    def __init__(self, model_name: str = SBERT_MODEL):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:  # pragma: no cover - depends on the environment
            raise ImportError("pip install sentence-transformers (or use embedder='tfidf')") from e
        self.model = SentenceTransformer(model_name)

    def fit(self, texts) -> "SentenceEmbedder":
        return self

    def transform(self, texts) -> np.ndarray:
        return _l2(np.asarray(self.model.encode(list(texts), show_progress_bar=False)))

    def fit_transform(self, texts) -> np.ndarray:
        return self.transform(texts)


def get_embedder(name: str = "tfidf"):
    if name == "tfidf":
        return TfidfEmbedder()
    if name == "sbert":
        return SentenceEmbedder()
    raise ValueError(f"unknown embedder {name!r} (use 'tfidf' or 'sbert')")


def _l2(X: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(X, axis=1, keepdims=True)
    return X / np.where(n == 0, 1.0, n)


# ----------------------------------------------------------------------------- similarity and clustering
def similarity_matrix(X: np.ndarray) -> np.ndarray:
    """Cosine similarity of L2-normalised rows."""
    return X @ X.T


def cluster(X: np.ndarray, threshold: float = 0.6) -> np.ndarray:
    """Average-linkage clustering on cosine distance. Items closer than `threshold` (distance) may merge.
    Lower threshold = more, smaller clusters. Returns 0-based labels."""
    if len(X) < 2:
        return np.zeros(len(X), dtype=int)
    Z = linkage(X, method="average", metric="cosine")
    return fcluster(Z, t=threshold, criterion="distance") - 1


def nearest_pairs(X: np.ndarray, k: int = 15) -> list[tuple[int, int, float]]:
    """The k most similar distinct pairs (i < j, similarity), most similar first."""
    S = similarity_matrix(X)
    iu = np.triu_indices(len(X), k=1)
    order = np.argsort(-S[iu])[:k]
    return [(int(iu[0][o]), int(iu[1][o]), float(S[iu][o])) for o in order]


def purity(labels, truth) -> float:
    """Share of items whose cluster's most common truth value equals their own (1.0 = perfectly pure)."""
    df = pd.DataFrame({"c": list(labels), "t": list(truth)})
    return float(df.groupby("c")["t"].agg(lambda s: s.value_counts().iloc[0]).sum() / max(len(df), 1))


def sweep(X: np.ndarray, truths: dict[str, list], thresholds=(0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)) -> pd.DataFrame:
    """For each distance threshold: number of clusters, singletons, largest cluster and purity per truth column."""
    rows = []
    for t in thresholds:
        lab = cluster(X, t)
        sizes = Counter(lab)
        row = {"threshold": t, "clusters": len(sizes), "singletons": sum(1 for v in sizes.values() if v == 1),
               "largest": max(sizes.values())}
        for name, tr in truths.items():
            row[f"purity_{name}"] = round(purity(lab, tr), 3)
        rows.append(row)
    return pd.DataFrame(rows)