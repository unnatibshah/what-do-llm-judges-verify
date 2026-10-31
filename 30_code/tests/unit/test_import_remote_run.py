"""D49: a remote run is imported only if every block ran the sealed file, the preregistered weights and this code."""

import json
import sys
from pathlib import Path

from suryabench.paths import CODE_DIR

sys.path.insert(0, str(CODE_DIR / "scripts"))
sys.path.insert(0, str(CODE_DIR / "scripts" / "kaggle"))
import import_remote_run as imp  # noqa: E402


def _block(root: Path, model: str, **h: object) -> None:
    d = root / model.replace(":", "_") / "blocks"
    d.mkdir(parents=True, exist_ok=True)
    (d / "validity__S-both.json").write_text(json.dumps({"rows": [], "model": model, **h}), encoding="utf-8")


def test_checks(tmp_path: Path) -> None:
    digests = imp.prereg_digests()
    assert set(digests) == {"llama3.1:8b", "qwen2.5:7b", "qwen2.5:14b"}
    good = {"allow_test": True, "dataset_sha256": "S", "code_hash": "C", "model_digest": digests["llama3.1:8b"]}
    src, dest = tmp_path / "src", tmp_path / "dest"
    _block(src, "llama3.1:8b", **good)
    assert imp.check(src, "S", digests, "C", dest)[0] == []
    _block(src, "qwen2.5:7b", **{**good, "model_digest": "sha256:" + "0" * 64})
    _block(dest, "llama3.1:8b", **good)
    problems = imp.check(src, "S", digests, "X", dest)[0]
    assert any("already has blocks" in p for p in problems) and any("digest" in p for p in problems)
    assert any("code hash" in p for p in problems)
    assert len(imp.local_code_hash()) == 12
