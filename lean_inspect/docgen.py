from __future__ import annotations

import html
import os
import re
from pathlib import Path
from typing import Iterable, Optional


SOURCE_RE = re.compile(r'<p class="gh_nav_link">\s*<a [^>]*href="vscode://file/([^"]+)"[^>]*>\s*source\s*</a>\s*</p>', re.IGNORECASE)
TRACE_RE = re.compile(r'<p class="gh_nav_link">[^<]*<a [^>]*>\s*trace\s*</a>\s*</p>', re.IGNORECASE)


def _find_source_path(html_text: str) -> Optional[Path]:
    m = SOURCE_RE.search(html_text)
    if not m:
        return None
    raw = m.group(1)
    # doc-gen writes vscode://file//abs/path, so trim leading slashes.
    return Path(raw.lstrip("/"))


def _insert_trace_link(html_text: str, trace_href: str, label: str = "trace") -> tuple[str, bool]:
    if TRACE_RE.search(html_text):
        return html_text, False

    m = SOURCE_RE.search(html_text)
    if not m:
        return html_text, False

    snippet = m.group(0)
    extra = f'<p class="gh_nav_link"><a href="{html.escape(trace_href)}">{html.escape(label)}</a></p>'
    new = html_text.replace(snippet, snippet + extra, 1)
    return new, True


def inject_trace_link_for_file(
    html_path: Path,
    *,
    project_root: Path,
    trace_root: Path,
    label: str = "trace",
) -> bool:
    text = html_path.read_text(encoding="utf-8")
    src_path = _find_source_path(text)
    if src_path is None:
        return False

    try:
        rel_src = src_path.relative_to(project_root)
    except ValueError:
        return False

    trace_html = trace_root / rel_src.with_suffix(".trace.html")
    if not trace_html.exists():
        return False

    rel_href = os.path.relpath(trace_html, start=html_path.parent)
    rel_href = Path(rel_href).as_posix()

    new_text, changed = _insert_trace_link(text, rel_href, label=label)
    if changed:
        html_path.write_text(new_text, encoding="utf-8")
    return changed


def iter_doc_html(doc_root: Path) -> Iterable[Path]:
    for p in doc_root.rglob("*.html"):
        # Skip shared assets so we only touch declaration pages.
        if p.name in {"index.html", "search.html", "navbar.html"}:
            continue
        yield p


def inject_doc_tree(
    doc_root: Path,
    *,
    project_root: Path,
    trace_root: Path,
    label: str = "trace",
) -> list[Path]:
    changed: list[Path] = []
    for p in iter_doc_html(doc_root):
        if inject_trace_link_for_file(p, project_root=project_root, trace_root=trace_root, label=label):
            changed.append(p)
    return changed
