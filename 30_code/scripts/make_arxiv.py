"""Build the arXiv source package of a paper version (paper_v6 by default): the authored single-column paper with the supplement appended, comments stripped, with its .bbl.

    PYTHONPATH=30_code/src python 30_code/scripts/make_arxiv.py [--paper paper_v7] [--tectonic PATH] [--draft]

Refuses while any judge's runs are pending (``\\EComplete`` is 0) unless ``--draft`` is given; a draft package is for
checking only and must not be uploaded. Writes ``70_papers/arxiv/surya_arxiv_src.tar.gz`` and the PDF it compiles to;
for any other version, into ``70_papers/arxiv/<version>/``.
"""

import argparse
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

from suryabench.paths import ROOT

PAPERS = ROOT / "60_paper_drafts"
ARXIV = ROOT / "70_papers" / "arxiv"
SKIP = {"main_2col.tex", "main_anon.tex", "main_full.tex", "supplement.tex", "supplement_anon.tex", "README.md",
        "references.bib", "numbers_placeholder.tex"}  # .bbl is shipped; one top-level file (main.tex) for arXiv


def strip_comments(tex: str) -> str:
    """Remove % comments (not \\%), drop lines that were only a comment; verbatim blocks are left as they are."""
    out, verbatim = [], False
    for line in tex.splitlines():
        if "\\begin{verbatim}" in line:
            verbatim = True
        if verbatim:
            out.append(line)
            verbatim = "\\end{verbatim}" not in line
            continue
        m = re.search(r"(?<!\\)%", line)
        if m is None:
            out.append(line)
        elif line[:m.start()].strip():  # keep a bare % so the line still ends without a space
            out.append(line[:m.start() + 1])
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--paper", default="paper_v6", help="folder under 60_paper_drafts")
    ap.add_argument("--tectonic", default="tectonic")
    ap.add_argument("--draft", action="store_true")
    a = ap.parse_args()
    PAPER = PAPERS / a.paper
    OUT = ARXIV if a.paper == "paper_v6" else ARXIV / a.paper
    if "\\EComplete}{0}" in (PAPER / "generated" / "numbers_e123.tex").read_text(encoding="utf-8") and not a.draft:
        raise SystemExit("runs pending (\\EComplete = 0): finish them, regenerate, or pass --draft for a check only")
    open_items = [f"{f.relative_to(PAPER)}" for f in PAPER.rglob("*.tex") if "[AUTHORS:" in f.read_text(encoding="utf-8")]
    if open_items and not a.draft:
        raise SystemExit(f"author placeholders still printed in: {open_items}")
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "src"
        skip = shutil.ignore_patterns("*.log", "*.blg", "*.aux", ".DS_Store", *SKIP)
        # Build PDFs at the top level are not shipped; figure PDFs in generated/ are.
        shutil.copytree(PAPER, src, ignore=lambda d, names: set(skip(d, names)) | (
            {n for n in names if n.endswith(".pdf")} if Path(d) == PAPER else set()))
        shutil.copy(PAPER / "references.bib", src)
        for f in src.rglob("*.tex"):
            f.write_text(strip_comments(f.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
        main_tex = src / "main.tex"
        # arXiv: pdflatex; \withsupplement appends the case study in full (as main_full.tex does), one PDF.
        main_tex.write_text("\\ifdefined\\XeTeXrevision\\else\\pdfoutput=1\\fi\n\\def\\withsupplement{}\n"
                            + main_tex.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
        r = subprocess.run([a.tectonic, "-X", "compile", "--keep-intermediates", "main.tex"], cwd=src,
                           capture_output=True, text=True)
        if r.returncode:
            raise SystemExit("compile failed:\n" + "\n".join((r.stdout + r.stderr).splitlines()[-25:]))
        (src / "references.bib").unlink()
        for f in src.glob("main.*"):
            if f.suffix not in {".tex", ".bbl"}:
                f.rename(Path(tmp) / f.name)  # the PDF is kept for checking; intermediates are not uploaded
        OUT.mkdir(parents=True, exist_ok=True)
        name = "surya_arxiv_src_DRAFT.tar.gz" if a.draft else "surya_arxiv_src.tar.gz"
        with tarfile.open(OUT / name, "w:gz") as t:
            for f in sorted(src.rglob("*")):
                if f.is_file():
                    t.add(f, arcname=str(f.relative_to(src)))
        shutil.copy(Path(tmp) / "main.pdf", OUT / name.replace("_src", "").replace(".tar.gz", ".pdf"))
        print(f"wrote {OUT / name}")


if __name__ == "__main__":
    main()
