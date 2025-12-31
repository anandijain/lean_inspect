from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Sequence

from .docgen import inject_doc_tree
from .html_trace import build_trace_html
from .lsp_trace import (
    init_client,
    path_to_uri,
    resolve_lake_path,
    trace_open_file,
    trace_project,
)


def cmd_trace_file(args: argparse.Namespace) -> None:
    file_path = Path(args.file)
    if not file_path.exists():
        raise SystemExit(f"file not found: {file_path}")

    root = Path(args.root) if args.root else file_path.parent
    lake = resolve_lake_path(args.lake)

    async def run() -> None:
        client, proc = await init_client(lake, path_to_uri(root), print_init=args.print_init)
        try:
            res = await trace_open_file(
                client,
                file_path,
                mode=args.mode,
                start_line=args.start_line,
                end_line=args.end_line,
                progress=args.progress,
            )
        finally:
            proc.terminate()

        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
        if args.progress or args.print_summary:
            print(f"wrote {out_path}")
            print(f"unique goal states: {len(res['unique_states'])}")
            print(f"occurrences: {len(res['occurrences'])}")

    asyncio.run(run())


def cmd_trace_project(args: argparse.Namespace) -> None:
    src_root = Path(args.src_root)
    out_dir = Path(args.out_dir)
    lake = resolve_lake_path(args.lake)

    async def run() -> None:
        json_paths = await trace_project(
            src_root,
            lake_path=lake,
            mode=args.mode,
            start_line=args.start_line,
            end_line=args.end_line,
            out_dir=out_dir,
            progress=args.progress,
        )
        if args.html:
            for p in json_paths:
                html_out = p.with_suffix(".trace.html")
                build_trace_html(p, html_out)
                if args.progress:
                    print(f"wrote {html_out}")

    asyncio.run(run())


def cmd_build_html(args: argparse.Namespace) -> None:
    build_trace_html(Path(args.trace_json), Path(args.out))
    if args.progress:
        print(f"wrote {args.out}")


def cmd_inject_doc(args: argparse.Namespace) -> None:
    doc_root = Path(args.doc_root)
    project_root = Path(args.project_root)
    trace_root = Path(args.trace_root)
    changed = inject_doc_tree(
        doc_root,
        project_root=project_root,
        trace_root=trace_root,
        label=args.label,
    )
    if args.progress:
        for p in changed:
            print(f"patched {p}")
    print(f"updated {len(changed)} files")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="lean-inspect")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_trace = sub.add_parser("trace-file", help="Trace a single Lean file")
    ap_trace.add_argument("file", help="Path to .lean file")
    ap_trace.add_argument("--out", default="trace.json", help="Output JSON path")
    ap_trace.add_argument("--root", default=None, help="Project root (used for LSP initialize rootUri)")
    ap_trace.add_argument("--mode", choices=["dense", "adaptive"], default="dense", help="dense=every column; adaptive=fewer queries")
    ap_trace.add_argument("--lake", default=None, help="Path to lake binary (default: lake or ~/.elan/bin/lake)")
    ap_trace.add_argument("--start-line", type=int, default=None, help="Scan starting at this 0-based line")
    ap_trace.add_argument("--end-line", type=int, default=None, help="Scan up to (but not including) this 0-based line")
    ap_trace.add_argument("--print-init", action="store_true", help="Print initialize result")
    ap_trace.add_argument("--print-summary", action="store_true", help="Print a short summary at end")
    ap_trace.add_argument("--progress", action="store_true", help="Print progress")
    ap_trace.set_defaults(func=cmd_trace_file)

    ap_proj = sub.add_parser("trace-project", help="Trace all Lean files under a directory")
    ap_proj.add_argument("src_root", help="Path that contains Lean sources (e.g., LeanProjectRoot/LeanProject)")
    ap_proj.add_argument("--out-dir", default="traces", help="Directory to write trace JSON (and HTML if requested)")
    ap_proj.add_argument("--mode", choices=["dense", "adaptive"], default="adaptive", help="dense=every column; adaptive=fewer queries")
    ap_proj.add_argument("--lake", default=None, help="Path to lake binary (default: lake or ~/.elan/bin/lake)")
    ap_proj.add_argument("--start-line", type=int, default=None, help="Scan starting at this 0-based line")
    ap_proj.add_argument("--end-line", type=int, default=None, help="Scan up to (but not including) this 0-based line")
    ap_proj.add_argument("--progress", action="store_true", help="Print progress")
    ap_proj.add_argument("--html", action="store_true", help="Also emit HTML viewers next to JSON outputs")
    ap_proj.set_defaults(func=cmd_trace_project)

    ap_html = sub.add_parser("html", help="Render a trace.json to trace.html")
    ap_html.add_argument("trace_json", help="trace.json produced by trace-file/trace-project")
    ap_html.add_argument("--out", default="trace.html", help="Output HTML path")
    ap_html.add_argument("--progress", action="store_true", help="Print output path")
    ap_html.set_defaults(func=cmd_build_html)

    ap_doc = sub.add_parser("inject-doc", help="Inject trace links into doc-gen4 HTML output")
    ap_doc.add_argument("doc_root", help="Root of doc-gen output (e.g., docbuild/.lake/build/doc)")
    ap_doc.add_argument("project_root", help="Lean project root that contains the source files")
    ap_doc.add_argument("trace_root", help="Directory containing generated *.trace.html (same layout as sources)")
    ap_doc.add_argument("--label", default="trace", help="Link label to insert")
    ap_doc.add_argument("--progress", action="store_true", help="Print modified files")
    ap_doc.set_defaults(func=cmd_inject_doc)

    return ap


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
