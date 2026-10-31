"""The vectorised cosine matches the scalar one, including zero vectors."""
import numpy as np

from suryabench.gate0.retriever import cosine_scores, cosine_similarity


def test_cosine_scores_match_scalar() -> None:
    rng = np.random.default_rng(0)
    m = rng.normal(size=(50, 16))
    m[3] = 0.0
    q = rng.normal(size=16)
    got = cosine_scores(q, m)
    want = [cosine_similarity(list(q), list(row)) for row in m]
    assert np.allclose(got, want, atol=1e-12)
    assert got[3] == 0.0
    assert list(np.argsort(-got)) == list(np.argsort(-np.array(want)))
