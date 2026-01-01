from __future__ import annotations

import html
import shutil
import os
import re
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlparse


SOURCE_RE = re.compile(r'<p class="gh_nav_link">\s*<a [^>]*href="([^"]+)"[^>]*>\s*source\s*</a>\s*</p>', re.IGNORECASE)
TRACE_RE = re.compile(r'<p class="gh_nav_link">[^<]*<a [^>]*>\s*trace\s*</a>\s*</p>', re.IGNORECASE)


def _find_source_path(html_text: str, *, project_root: Path) -> Optional[Path]:
    m = SOURCE_RE.search(html_text)
    if not m:
        return None

    href = html.unescape(m.group(1))
    parsed = urlparse(href)

    # doc-gen writes vscode://file//abs/path, so normalize while keeping absolute.
    if parsed.scheme == "vscode" and parsed.netloc == "file":
        return Path("/" + parsed.path.lstrip("/"))

    # GitHub/GitLab blob links: .../blob/<rev>/path/to/File.lean
    parts = parsed.path.lstrip("/").split("/")
    if "blob" in parts:
        blob_idx = parts.index("blob")
        rel_parts = parts[blob_idx + 2 :]
        if rel_parts:
            return (project_root / Path(*rel_parts)).resolve()

    # Fallback: treat the href path as a project-relative file path.
    if parsed.scheme in {"", "file"} and parsed.path:
        return (project_root / Path(parsed.path.lstrip("/"))).resolve()

    return None


def _insert_trace_link(html_text: str, trace_href: str, label: str = "trace") -> tuple[str, bool]:
    repl = f'<p class="gh_nav_link"><a href="{html.escape(trace_href)}">{html.escape(label)}</a></p>'
    # If a trace link already exists, rewrite it to the new href.
    m_trace = TRACE_RE.search(html_text)
    if m_trace:
        new_text = TRACE_RE.sub(repl, html_text, count=1)
        return new_text, new_text != html_text

    m = SOURCE_RE.search(html_text)
    if not m:
        return html_text, False

    snippet = m.group(0)
    new = html_text.replace(snippet, snippet + repl, 1)
    return new, True


def inject_trace_link_for_file(
    html_path: Path,
    *,
    project_root: Path,
    trace_root: Path,
    label: str = "trace",
    copy_into: Optional[Path] = None,
    copy_dirname: str = "_traces",
    debug: bool = False,
) -> bool:
    text = html_path.read_text(encoding="utf-8")
    src_path = _find_source_path(text, project_root=project_root)
    if src_path is None:
        if debug:
            print(f"[inject-doc] skip {html_path}: no source link found")
        return False

    try:
        rel_src = src_path.relative_to(project_root)
    except ValueError:
        if debug:
            print(f"[inject-doc] skip {html_path}: source outside project root ({src_path})")
        return False

    trace_html = trace_root / rel_src.with_suffix(".trace.html")
    if not trace_html.exists():
        # Fallback to legacy double-suffix path (.trace.trace.html) in case traces were generated earlier.
        legacy = trace_html.with_name(trace_html.stem + ".trace.html")
        if legacy.exists():
            trace_html = legacy
        else:
            if debug:
                print(f"[inject-doc] skip {html_path}: missing trace {trace_html}")
            return False

    # If the trace file is outside the served doc_root, optionally copy it inside.
    if copy_into is not None:
        target = copy_into / copy_dirname / rel_src.with_suffix(".trace.html")
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copy2(trace_html, target)
        trace_html = target

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
    copy_into_doc: bool = True,
    copy_dirname: str = "_traces",
    debug: bool = False,
) -> list[Path]:
    project_root = project_root.resolve()
    trace_root = trace_root.resolve()
    doc_root = doc_root.resolve()

    changed: list[Path] = []
    for p in iter_doc_html(doc_root):
        copied_root: Optional[Path] = doc_root if copy_into_doc else None
        if inject_trace_link_for_file(
            p,
            project_root=project_root,
            trace_root=trace_root,
            label=label,
            copy_into=copied_root,
            copy_dirname=copy_dirname,
            debug=debug,
        ):
            changed.append(p)
    return changed
