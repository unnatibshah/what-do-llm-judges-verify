"""Every repository path, in one place.

The repository uses numbered folders (see ``CLAUDE.md`` at the root):

    00_tracking/  10_admin/  20_method/  30_code/  40_data/  50_analysis/
    60_paper_drafts/  70_papers/  80_review/  90_archive/

Code must take paths from here rather than building them from ``__file__`` or from strings
relative to the working directory.

Saved artefacts written before the 2026-09-29 restructure record paths in the old layout
(``results/runs/...``, ``benchmark/test_cases_100.json``). Those files are immutable, so they
are never rewritten; :func:`resolve` maps an old-layout path onto its current location when it is
read, and :func:`same_file` compares two paths by the file they point to, not by their spelling.
"""

from pathlib import Path


def _find_root() -> Path:
    """The repository root: the nearest directory above this file, or above the working
    directory, that holds ``pyproject.toml``."""
    for start in (Path(__file__).resolve(), Path.cwd().resolve()):
        for candidate in (start, *start.parents):
            if (candidate / "pyproject.toml").is_file() and (candidate / "30_code").is_dir():
                return candidate
    raise RuntimeError("SuryaBench repository root not found (no pyproject.toml beside 30_code/)")


ROOT = _find_root()

TRACKING_DIR = ROOT / "00_tracking"
DECISIONS_MD = TRACKING_DIR / "decisions" / "DECISIONS.md"
METHOD_DIR = ROOT / "20_method"
CODE_DIR = ROOT / "30_code"
DATA_DIR = ROOT / "40_data"
CORPUS_DIR = DATA_DIR / "corpus"
# Staging corpus r3 (D19): r2 plus the staged documents; not frozen, documents UNVERIFIED.
CORPUS_R3_DIR = DATA_DIR / "corpus_r3"
CORPUS_STAGING_DIR = DATA_DIR / "corpus_staging"
ANNOTATION_DIR = METHOD_DIR / "annotation"
BENCHMARK_DIR = DATA_DIR / "benchmark"
ANALYSIS_DIR = ROOT / "50_analysis"
RESULTS_DIR = ANALYSIS_DIR / "results"
GATE0_RESULT_MD = ANALYSIS_DIR / "GATE0-RESULT.md"
PAPER_DIR = ROOT / "60_paper_drafts" / "paper"
ENV_FILE = ROOT / ".env"
REGISTRIES_DIR = DATA_DIR / "registries"

# Corpus choice (``--corpus``): v2 runs use r3; r2 stays available to reproduce retired results.
CORPORA: dict[str, Path] = {"r2": CORPUS_DIR, "r3": CORPUS_R3_DIR}
DEFAULT_CORPUS = "r3"
# Dense-embedding caches (git-ignored), one per corpus so an r3 run never rewrites the r2 cache.
EMBEDDING_CACHES: dict[str, Path] = {
    "r2": RESULTS_DIR / "embeddings_cache.json",
    "r3": RESULTS_DIR / "embeddings_cache_r3.json",
}


def corpus_dir(name: str) -> Path:
    """Directory of corpus ``name`` (``r2`` or ``r3``)."""
    if name not in CORPORA:
        raise ValueError(f"Unknown corpus '{name}'; choose one of {sorted(CORPORA)}")
    return CORPORA[name]


def corpus_name(path: str | Path) -> str | None:
    """``r2``/``r3`` for a known corpus directory, else None (a test fixture)."""
    return next((n for n, d in CORPORA.items() if same_file(path, d)), None)


def embeddings_cache(corpus: str | Path) -> Path:
    """Embedding cache for a corpus name or directory; a fixture corpus keeps its cache beside itself."""
    name = corpus if isinstance(corpus, str) and corpus in CORPORA else corpus_name(corpus)
    return EMBEDDING_CACHES[name] if name else Path(corpus).parent / "results" / "embeddings_cache.json"

# Top-level folders of the pre-restructure layout, and where each now lives.
LEGACY_PREFIXES: dict[str, Path] = {
    "corpus": CORPUS_DIR,
    "benchmark": BENCHMARK_DIR,
    "results": RESULTS_DIR,
    "paper": PAPER_DIR,
    "docs": METHOD_DIR,
    "src": CODE_DIR / "src",
    "tests": CODE_DIR / "tests",
    "scripts": CODE_DIR / "scripts",
}


def resolve(path: str | Path) -> Path:
    """Absolute current-layout path for ``path``.

    Absolute paths are returned unchanged. A relative path whose first component is a
    pre-restructure top-level folder (``results/runs/x``) is mapped onto the numbered layout;
    any other relative path is taken relative to the repository root.
    """
    p = Path(path)
    if p.is_absolute():
        return p
    parts = p.parts
    if parts and parts[0] in LEGACY_PREFIXES:
        return LEGACY_PREFIXES[parts[0]].joinpath(*parts[1:])
    return ROOT / p


def same_file(a: str | Path, b: str | Path) -> bool:
    """True when ``a`` and ``b`` name the same file, whichever layout each is written in."""
    return resolve(a).resolve() == resolve(b).resolve()


def display(path: str | Path) -> str:
    """Stable, OS-independent spelling of ``path`` for reports: repository-relative with
    forward slashes when inside the repository, otherwise the absolute POSIX form."""
    p = resolve(path).resolve()
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()
