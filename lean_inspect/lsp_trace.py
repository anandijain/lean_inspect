from __future__ import annotations

import asyncio
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.request import pathname2url


def path_to_uri(p: Path) -> str:
    return "file://" + pathname2url(str(p.resolve()))


def lsp_frame(payload: dict) -> bytes:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body


async def read_msg(stdout: asyncio.StreamReader) -> dict:
    headers: dict[str, str] = {}
    while True:
        line = await stdout.readline()
        if not line:
            raise EOFError("LSP server closed stdout")
        s = line.decode("ascii", errors="replace").strip()
        if s == "":
            break
        k, v = s.split(":", 1)
        headers[k.strip().lower()] = v.strip()

    n = int(headers["content-length"])
    body = await stdout.readexactly(n)
    return json.loads(body.decode("utf-8"))


class LspClient:
    def __init__(self, proc: asyncio.subprocess.Process):
        self.proc = proc
        self.next_id = 1

    async def send(self, msg: dict) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(lsp_frame(msg))
        await self.proc.stdin.drain()

    async def notify(self, method: str, params: dict) -> None:
        await self.send({"jsonrpc": "2.0", "method": method, "params": params})

    async def request(self, method: str, params: dict) -> Any:
        rid = self.next_id
        self.next_id += 1
        await self.send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})

        while True:
            resp = await read_msg(self.proc.stdout)  # type: ignore[arg-type]
            if resp.get("id") == rid:
                if "error" in resp:
                    raise RuntimeError(resp["error"])
                return resp.get("result")
            # Ignore notifications / other responses for now.


async def start_lean_lsp(lake_path: str) -> asyncio.subprocess.Process:
    """
    Start Lean language server via `lake serve`.
    """
    proc = await asyncio.create_subprocess_exec(
        lake_path,
        "serve",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=os.getcwd(),
    )
    return proc


async def wait_for_diagnostics(c: LspClient, uri: str, version: int) -> None:
    # Lean-specific; requires the Lean server to provide this request.
    await c.request("textDocument/waitForDiagnostics", {"uri": uri, "version": version})


async def plain_goal(c: LspClient, uri: str, line: int, col: int) -> Optional[dict]:
    return await c.request(
        "$/lean/plainGoal",
        {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": col},
        },
    )


def goal_key(goal: Optional[dict]) -> Optional[str]:
    if goal is None:
        return None
    # In Lean output this is typically a ```lean ...``` fenced string; hashing it is enough.
    return goal.get("rendered", "")


def short_hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


@dataclass
class Occurrence:
    h: str
    line: int
    col_start: int
    col_end: int

    def to_json(self) -> dict:
        return {
            "hash": self.h,
            "line": self.line,
            "col_start": self.col_start,
            "col_end": self.col_end,
            "sample_pos": {"line": self.line, "character": self.col_start},
        }


async def scan_line_dense(
    c: LspClient, uri: str, line_idx: int, line_text: str
) -> list[tuple[int, Optional[str]]]:
    """
    Return a list of transitions: [(col, goal_key_at_col)] where goal_key changes at col.
    Includes the starting state at col=0.
    """
    transitions: list[tuple[int, Optional[str]]] = []
    prev: Optional[str] = None

    for col in range(0, len(line_text) + 1):
        g = await plain_goal(c, uri, line_idx, col)
        k = goal_key(g)
        if col == 0:
            transitions.append((0, k))
            prev = k
            continue
        if k != prev:
            transitions.append((col, k))
            prev = k

    return transitions


async def scan_line_adaptive(
    c: LspClient, uri: str, line_idx: int, line_text: str
) -> list[tuple[int, Optional[str]]]:
    """
    Adaptive scanning to reduce number of plainGoal calls.
    Strategy:
      - Sample at exponentially spaced columns.
      - When a change is detected between two samples, binary-search boundary.
      - Finally, gather all boundaries to produce transitions.
    """
    n = len(line_text)
    if n == 0:
        g0 = await plain_goal(c, uri, line_idx, 0)
        return [(0, goal_key(g0))]

    # Memoize samples to avoid repeated queries
    memo: dict[int, Optional[str]] = {}

    async def get(col: int) -> Optional[str]:
        col = max(0, min(n, col))
        if col in memo:
            return memo[col]
        g = await plain_goal(c, uri, line_idx, col)
        k = goal_key(g)
        memo[col] = k
        return k

    # Exponential samples
    samples = [0]
    step = 1
    while samples[-1] < n:
        samples.append(min(n, samples[-1] + step))
        step *= 2
    # Ensure last sample at n
    if samples[-1] != n:
        samples.append(n)

    # Fetch sample keys
    keys = []
    for col in samples:
        keys.append(await get(col))

    # Collect boundaries by refining intervals where keys differ
    boundaries = {0}
    for i in range(len(samples) - 1):
        a, b = samples[i], samples[i + 1]
        ka, kb = keys[i], keys[i + 1]
        if ka == kb:
            continue

        # binary search for earliest col where key becomes kb
        lo, hi = a, b
        # invariant: key(lo)=ka, key(hi)=kb, lo < hi
        while hi - lo > 1:
            mid = (lo + hi) // 2
            km = await get(mid)
            if km == ka:
                lo = mid
            else:
                hi = mid
        boundaries.add(hi)

    # Now compute transitions by walking boundaries in order and querying at each boundary
    trans_cols = sorted(boundaries)
    transitions: list[tuple[int, Optional[str]]] = []
    prev: object = object()
    for col in trans_cols:
        k = await get(col)
        if k != prev:
            transitions.append((col, k))
            prev = k

    # Ensure we end at n so segment-closing is easy downstream
    if transitions and transitions[-1][0] != n:
        k_end = await get(n)
        if k_end != transitions[-1][1]:
            transitions.append((n, k_end))

    return transitions


def transitions_to_occurrences(
    line_idx: int, line_text: str, transitions: list[tuple[int, Optional[str]]]
) -> list[Occurrence]:
    """
    Convert transitions [(col, key)] into segment occurrences for non-null key.
    """
    occs: list[Occurrence] = []
    if not transitions:
        return occs

    # Ensure transitions sorted
    transitions = sorted(transitions, key=lambda x: x[0])

    # Make sure we have an end marker at len(line)
    if transitions[-1][0] != len(line_text):
        transitions = transitions + [(len(line_text), transitions[-1][1])]

    for i in range(len(transitions) - 1):
        col, k = transitions[i]
        next_col, _ = transitions[i + 1]
        if k is None:
            continue
        h = short_hash(k)
        occs.append(Occurrence(h=h, line=line_idx, col_start=col, col_end=next_col))

    return occs


def shutil_which(cmd: str) -> Optional[str]:
    # Tiny local which() to avoid importing shutil if you want to keep imports minimal.
    for p in os.environ.get("PATH", "").split(os.pathsep):
        c = Path(p) / cmd
        if c.exists() and os.access(c, os.X_OK):
            return str(c)
    return None


def resolve_lake_path(lake_path: Optional[str]) -> str:
    if lake_path is not None:
        return lake_path
    found = shutil_which("lake")
    if found is not None:
        return found
    return str(Path.home() / ".elan" / "bin" / "lake")


async def init_client(lake_path: str, root_uri: str, print_init: bool = False) -> tuple[LspClient, asyncio.subprocess.Process]:
    proc = await start_lean_lsp(lake_path)
    c = LspClient(proc)

    init_result = await c.request(
        "initialize",
        {
            "processId": None,
            "rootUri": root_uri,
            "capabilities": {},
        },
    )
    await c.notify("initialized", {})

    if print_init:
        print(json.dumps(init_result, indent=2))

    return c, proc


async def trace_open_file(
    c: LspClient,
    file_path: Path,
    *,
    mode: str = "adaptive",
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
    progress: bool = False,
) -> dict:
    text = file_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    uri = path_to_uri(file_path)
    version = 1
    await c.notify(
        "textDocument/didOpen",
        {
            "textDocument": {
                "uri": uri,
                "languageId": "lean",
                "version": version,
                "text": text,
            }
        },
    )

    await wait_for_diagnostics(c, uri, version)

    unique_states: dict[str, str] = {}
    occurrences: list[Occurrence] = []

    scanner = scan_line_adaptive if mode == "adaptive" else scan_line_dense

    start_line = start_line if start_line is not None else 0
    end_line = end_line if end_line is not None else len(lines)
    start_line = max(0, min(len(lines), start_line))
    end_line = max(start_line, min(len(lines), end_line))

    for ln in range(start_line, end_line):
        s = lines[ln]
        transitions = await scanner(c, uri, ln, s)
        occs = transitions_to_occurrences(ln, s, transitions)
        for oc in occs:
            if oc.h not in unique_states:
                g = await plain_goal(c, uri, ln, oc.col_start)
                k = goal_key(g)
                if k is not None:
                    unique_states[oc.h] = k
        occurrences.extend(occs)

        if progress and (ln - start_line) % 20 == 0:
            print(f"scanned {file_path}:{ln}/{end_line - 1}  uniques={len(unique_states)} occs={len(occurrences)}")

    await c.notify("textDocument/didClose", {"textDocument": {"uri": uri}})

    return {
        "file": str(file_path),
        "uri": uri,
        "mode": mode,
        "unique_states": unique_states,
        "occurrences": [o.to_json() for o in occurrences],
    }


def iter_lean_files(root: Path) -> Iterable[Path]:
    """
    Yield Lean source files under root, skipping common build/doc output directories.
    """
    skip_dirs = {".git", ".lake", "lake-packages", "docbuild", "build"}
    for p in root.rglob("*.lean"):
        if any(part in skip_dirs for part in p.parts):
            continue
        yield p


async def trace_project(
    src_root: Path,
    *,
    lake_path: Optional[str] = None,
    mode: str = "adaptive",
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
    out_dir: Path,
    progress: bool = False,
) -> list[Path]:
    """
    Trace all Lean files under src_root. Returns list of written JSON paths.
    """
    lake = resolve_lake_path(lake_path)
    root_uri = path_to_uri(src_root)
    client, proc = await init_client(lake, root_uri, print_init=False)

    try:
        results: list[Path] = []
        for file_path in iter_lean_files(src_root):
            rel = file_path.relative_to(src_root)
            out_path = out_dir / rel.with_suffix(".trace.json")
            out_path.parent.mkdir(parents=True, exist_ok=True)

            res = await trace_open_file(
                client,
                file_path,
                mode=mode,
                start_line=start_line,
                end_line=end_line,
                progress=progress,
            )
            out_path.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
            results.append(out_path)
            if progress:
                print(f"wrote {out_path}")
        return results
    finally:
        proc.terminate()
