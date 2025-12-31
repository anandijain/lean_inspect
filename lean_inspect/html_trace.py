from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Mapping


def _trace_from_input(trace_json: Path | Mapping[str, Any]) -> tuple[Mapping[str, Any], Path]:
    if isinstance(trace_json, Path):
        trace = json.loads(trace_json.read_text(encoding="utf-8"))
    else:
        trace = trace_json
    lean_file = Path(trace["file"])
    return trace, lean_file


def build_trace_html(trace_json: Path | Mapping[str, Any], out_path: Path) -> None:
    trace, lean_file = _trace_from_input(trace_json)
    src_text = lean_file.read_text(encoding="utf-8")

    # Safe embed of JSON
    data_json = json.dumps(trace, ensure_ascii=False).replace("<", "\\u003c")

    html_out = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<title>Lean goal trace: {html.escape(str(lean_file))}</title>

<!-- highlight.js -->
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.11.1/styles/github.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.11.1/highlight.min.js"></script>

<style>
:root {{
  color-scheme: light;
  --bg: #f6f7fb;
  --panel: #ffffff;
  --text: #1f2937;
  --muted: #6b7280;
  --code-bg: #f8fafc;
  --goal-bg: #f2f4f8;
  --accent: rgba(255, 208, 96, 0.45);
  --accent-strong: rgba(255, 184, 36, 0.7);
  --cursor: #0f172a;
  --border: #e5e7eb;
  --kw: #7c3aed;
  --const: #2563eb;
  --str: #dc2626;
  --comment: #6b7280;
  --num: #b45309;
}}
body.theme-dark {{
  color-scheme: dark;
  --bg: #0b0f19;
  --panel: #0f172a;
  --text: #e5e7eb;
  --muted: #9ca3af;
  --code-bg: #0a1020;
  --goal-bg: #0c1224;
  --accent: rgba(255, 214, 102, 0.35);
  --accent-strong: rgba(255, 198, 68, 0.55);
  --cursor: #f8fafc;
  --border: #1f2937;
  --kw: #c084fc;
  --const: #93c5fd;
  --str: #fb7185;
  --comment: #9ca3af;
  --num: #fbbf24;
}}

  body {{
    margin: 0; padding: 0;
    font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
    display: grid;
    grid-template-columns: 1.4fr 1fr;
    height: 100vh;
    background: var(--bg);
    color: var(--text);
  }}
  #left {{
    border-right: 1px solid var(--border);
    overflow: auto;
    padding: 12px;
    background: var(--panel);
  }}
  #right {{
    overflow: auto;
    padding: 12px;
    background: var(--panel);
  }}
  .meta {{ color: var(--muted); font-size: 12px; margin-bottom: 10px; }}
  #toolbar {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 8px; flex-wrap: wrap; }}
  #metaRow {{ display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }}
  .metaItem {{ color: var(--muted); font-size: 12px; }}
  .button {{
    border: 1px solid var(--border);
    background: transparent;
    color: var(--text);
    padding: 6px 10px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 12px;
  }}
  .button:hover {{
    background: var(--goal-bg);
  }}

  /* Code pane */
  #codewrap {{
    position: relative;
    background: var(--code-bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 10px;
  }}
  pre {{
    margin: 0;
    font-size: 13px;
    line-height: 1.42;
    white-space: normal;
  }}
  code {{
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
    display: block;
    white-space: pre;
  }}

  /* Cursor + selection */
  .line {{
    display: flex;
    align-items: flex-start;
    position: relative;
    padding-left: 0;
    white-space: pre;
  }}
  .ln {{
    flex: 0 0 4.2em;
    color: var(--muted);
    user-select: none;
    text-align: right;
    padding-right: 0.7em;
  }}
  .codeText {{
    flex: 1;
    min-height: 1.2em;
    white-space: pre;
  }}
  .seg {{
    border-radius: 0;
    padding: 0;
    background: none;
    box-shadow: none;
  }}
  .seg.hasGoal {{
    background: none;
    box-shadow: none;
  }}
  .seg.active {{
    outline: none;
    background: none;
  }}
  .seg.fallback {{
    box-shadow: none;
  }}

  /* Fake cursor */
  #cursor {{
    position: absolute;
    width: 2px;
    background: var(--cursor);
    pointer-events: none;
    display: none;
  }}

  #goal {{
    white-space: pre-wrap;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
    font-size: 13px;
    line-height: 1.4;
    background: var(--goal-bg);
    border-radius: 8px;
    padding: 10px;
    border: 1px solid var(--border);
    color: var(--text);
  }}

  /* Syntax highlighting */
  .hljs-keyword {{ color: var(--kw); font-weight: 600; }}
  .hljs-title, .hljs-type, .hljs-built_in {{ color: var(--const); }}
  .hljs-string {{ color: var(--str); }}
  .hljs-number {{ color: var(--num); }}
  .hljs-comment {{ color: var(--comment); font-style: italic; }}
</style>
</head>
<body class="theme-light">
  <div id="left">
    <div id="toolbar">
      <div id="metaRow">
        <span class="metaItem"><b>File:</b> {html.escape(str(lean_file))}</span>
        <span class="metaItem"><b>Unique states:</b> {len(trace["unique_states"])}</span>
        <span class="metaItem"><b>Occurrences:</b> {len(trace["occurrences"])}</span>
        <span class="metaItem">Click to place cursor. Use arrow keys to move. (Read-only)</span>
      </div>
      <button class="button" id="themeToggle" type="button">Toggle theme</button>
    </div>

    <div id="codewrap" tabindex="0" aria-label="Code view (read-only)">
      <div id="cursor"></div>
      <!-- code will be injected -->
    </div>
  </div>

  <div id="right">
    <div class="meta"><b>Goal state</b></div>
    <div id="where" class="meta">No selection.</div>
    <div id="goal">(click in the code pane)</div>
  </div>

<script id="trace-data" type="application/json">{data_json}</script>
<script>
  // ---- Data ----
  const trace = JSON.parse(document.getElementById("trace-data").textContent);
  const unique = trace.unique_states;
  const occs = trace.occurrences;
  const sortedOccs = [...occs].sort((a, b) => (a.line - b.line) || (a.col_start - b.col_start));

  // Build per-line occurrence lists for fast lookup
  const byLine = new Map();
  for (const o of occs) {{
    const ln = o.line;
    if (!byLine.has(ln)) byLine.set(ln, []);
    byLine.get(ln).push(o);
  }}
  for (const [ln, arr] of byLine.entries()) {{
    arr.sort((a,b) => (a.col_start - b.col_start) || (a.col_end - b.col_end));
  }}

  // ---- Render code with line numbers + spans ----
  const codewrap = document.getElementById("codewrap");
  const cursorEl = document.getElementById("cursor");

  const src = {json.dumps(src_text, ensure_ascii=False).replace("<", "\\u003c")};
  const lines = src.split(/\\n/);

  function escapeHtml(s) {{
    return s.replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;")
            .replaceAll('"',"&quot;").replaceAll("'","&#039;");
  }}

  // Register a small Lean grammar for highlight.js if not bundled
  (function registerLean() {{
    if (window.hljs && !hljs.getLanguage("lean")) {{
      hljs.registerLanguage("lean", function(hljs) {{
        return {{
          name: "Lean",
          aliases: ["lean4"],
          keywords: {{
            keyword:
              "theorem lemma def example structure class instance inductive mutual namespace end open section variable variables abbrev macro notation do fun match with if then else by simp rw intro intros exact apply refine have let in where forall exists return continue break cases constructor revert rename_i repeat try first focus set_option axiom constant",
            built_in:
              "Type Sort Prop true false Bool Nat Int Rat Real List Array Set Option",
          }},
          contains: [
            hljs.COMMENT("--", "$"),
            hljs.COMMENT("/-", "-/"),
            hljs.QUOTE_STRING_MODE,
            hljs.NUMBER_MODE,
          ],
        }};
      }});
    }}
  }})();

  function highlightLean(text, opts = {{}}) {{
    if (opts.forceComment) {{
      return `<span class="hljs-comment">${{escapeHtml(text)}}</span>`;
    }}
    if (!window.hljs) return escapeHtml(text);
    try {{
      const res = hljs.highlight(text, {{ language: "lean", ignoreIllegals: true }});
      return res.value || "";
    }} catch (e) {{
      return escapeHtml(text);
    }}
  }}

  function nextBlockState(text, inBlock) {{
    let state = inBlock;
    for (let i = 0; i < text.length; i++) {{
      if (!state && text[i] === "/" && text[i + 1] === "-") {{
        state = true;
        i++;
      }} else if (state && text[i] === "-" && text[i + 1] === "/") {{
        state = false;
        i++;
      }}
    }}
    return state;
  }}

  function renderLine(ln, text, inBlockComment) {{
    const trimmed = text.trimStart();
    const isLineComment = trimmed.startsWith("--");
    const forceComment = inBlockComment || isLineComment;

    const occList = byLine.get(ln) || [];
    const safeHighlight = (snippet) => {{
      if (snippet.length === 0) return " ";
      return highlightLean(snippet, {{ forceComment }});
    }};

    if (occList.length === 0) {{
      return {{
        html: `<span class="line" data-ln="${{ln}}"><span class="ln">${{(ln+1).toString().padStart(4,' ')}}</span><span class="codeText">${{safeHighlight(text)}}</span></span>`,
        nextBlock: nextBlockState(text, inBlockComment),
      }};
    }}

    let cur = 0;
    let out = "";
    for (const o of occList) {{
      const a = Math.max(0, Math.min(text.length, o.col_start));
      const b = Math.max(0, Math.min(text.length, o.col_end));
      if (a > cur) out += safeHighlight(text.slice(cur, a));
      const segText = safeHighlight(text.slice(a, b));
      const hasGoal = unique[o.hash] && unique[o.hash] !== "no goals";
      out += `<span class="seg ${{hasGoal ? "hasGoal" : ""}}" data-h="${{o.hash}}" data-ln="${{ln}}" data-a="${{a}}" data-b="${{b}}">${{segText || " "}}</span>`;
      cur = b;
    }}
    if (cur < text.length) out += safeHighlight(text.slice(cur));

    return {{
      html: `<span class="line" data-ln="${{ln}}"><span class="ln">${{(ln+1).toString().padStart(4,' ')}}</span><span class="codeText">${{out}}</span></span>`,
      nextBlock: nextBlockState(text, inBlockComment),
    }};
  }}

  // Inject all lines, tracking block comments so comment text stays un-highlighted
  const pre = document.createElement("pre");
  const code = document.createElement("code");
  code.className = "language-lean"; // may fall back, still fine
  let blockComment = false;
  const rendered = [];
  for (let i = 0; i < lines.length; i++) {{
    const res = renderLine(i, lines[i], blockComment);
    rendered.push(res.html);
    blockComment = res.nextBlock;
  }}
  code.innerHTML = rendered.join("");
  pre.appendChild(code);
  codewrap.appendChild(pre);

  // ---- Cursor model ----
  let curLine = 0;
  let curCol = 0;
  let activeSeg = null;
  let activeFallback = false;

  function setActiveSeg(seg, isFallback=false) {{
    if (activeSeg) activeSeg.classList.remove("active", "fallback");
    activeSeg = seg;
    activeFallback = isFallback;
    if (activeSeg) {{
      activeSeg.classList.add("active");
      if (isFallback) activeSeg.classList.add("fallback");
    }}
  }}

  function lookupOccurrence(line, col) {{
    const arr = byLine.get(line);
    if (!arr) return null;
    // Linear scan is OK for small lists; can binary-search later.
    for (const o of arr) {{
      if (col >= o.col_start && col < o.col_end) return o;
    }}
    return null;
  }}

  function lookupWithFallback(line, col) {{
    const hit = lookupOccurrence(line, col);
    if (hit) return {{ occ: hit, viaFallback: false }};

    // binary search across all occurrences to find the last one that starts before (line,col)
    let lo = 0, hi = sortedOccs.length;
    while (lo < hi) {{
      const mid = (lo + hi) >> 1;
      const o = sortedOccs[mid];
      if (o.line < line || (o.line === line && o.col_start <= col)) {{
        lo = mid + 1;
      }} else {{
        hi = mid;
      }}
    }}
    if (lo === 0) return null;
    return {{ occ: sortedOccs[lo - 1], viaFallback: true }};
  }}

  function renderGoalForPos(line, col) {{
    const res = lookupWithFallback(line, col);
    if (!res) {{
      document.getElementById("where").textContent = `line=${{line+1}} col=${{col}} (no cached goal here)`;
      document.getElementById("goal").textContent = "(no cached goal here)";
      setActiveSeg(null);
      return;
    }}
    const o = res.occ;
    const txt = unique[o.hash] ?? "(missing)";
    const whereLabel = res.viaFallback
      ? `cursor=(${{line+1}},${{col}})  fallback-> line=${{o.line+1}} cols=[${{o.col_start}},${{o.col_end}}) hash=${{o.hash}}`
      : `hash=${{o.hash}}  line=${{o.line+1}}  cols=[${{o.col_start}},${{o.col_end}})  cursor=(${{line+1}},${{col}})`;
    document.getElementById("where").textContent = whereLabel;
    document.getElementById("goal").textContent = txt;

    const seg = document.querySelector(`.seg[data-h="${{o.hash}}"][data-ln="${{o.line}}"][data-a="${{o.col_start}}"][data-b="${{o.col_end}}"]`);
    setActiveSeg(seg, res.viaFallback);
  }}

  function colFromClick(lineEl, clientX, clientY) {{
    const caretPos = (document.caretPositionFromPoint && document.caretPositionFromPoint(clientX, clientY))
      || (document.caretRangeFromPoint && document.caretRangeFromPoint(clientX, clientY));
    if (!caretPos) return 0;
    const node = caretPos.offsetNode || caretPos.startContainer;
    const offset = caretPos.offset ?? caretPos.startOffset ?? 0;
    if (!node || !lineEl.contains(node)) return 0;

    let col = 0;
    const walker = document.createTreeWalker(lineEl, NodeFilter.SHOW_TEXT, null);
    while (walker.nextNode()) {{
      const n = walker.currentNode;
      if (n === node) {{
        col += Math.min(offset, n.nodeValue.length);
        break;
      }}
      col += n.nodeValue.length;
    }}
    return col;
  }}

  function placeCursor(line, col) {{
    curLine = Math.max(0, Math.min(lines.length - 1, line));
    curCol = Math.max(0, col);

    const lineEl = document.querySelector(`.line[data-ln="${{curLine}}"] .codeText`);
    if (!lineEl) return;

    const text = lines[curLine] || "";
    const clamped = Math.min(curCol, text.length);

    const range = document.createRange();

    let remaining = clamped;
    let foundNode = null;
    let foundOffset = 0;

    const walker = document.createTreeWalker(lineEl, NodeFilter.SHOW_TEXT, null);
    while (walker.nextNode()) {{
      const node = walker.currentNode;
      const len = node.nodeValue.length;
      if (remaining <= len) {{
        foundNode = node;
        foundOffset = remaining;
        break;
      }}
      remaining -= len;
    }}

    if (!foundNode) {{
      foundNode = lineEl.lastChild;
      foundOffset = (foundNode && foundNode.nodeType === Node.TEXT_NODE) ? foundNode.nodeValue.length : 0;
    }}

    try {{
      range.setStart(foundNode, foundOffset);
      range.setEnd(foundNode, foundOffset);
      const rects = range.getClientRects();
      const rect = rects.length ? rects[0] : lineEl.getBoundingClientRect();

      const wrapRect = codewrap.getBoundingClientRect();
      cursorEl.style.left = (rect.left - wrapRect.left + codewrap.scrollLeft) + "px";
      cursorEl.style.top = (rect.top - wrapRect.top + codewrap.scrollTop) + "px";
      cursorEl.style.height = rect.height + "px";
      cursorEl.style.display = "block";
    }} catch (e) {{
      cursorEl.style.display = "none";
    }}

    renderGoalForPos(curLine, curCol);
  }}

  // ---- Mouse: click places cursor ----
  codewrap.addEventListener("click", (ev) => {{
    codewrap.focus();
    const lineEl = ev.target.closest(".line");
    if (lineEl) {{
      const ln = parseInt(lineEl.dataset.ln);
      const codeEl = lineEl.querySelector(".codeText");
      const col = codeEl ? colFromClick(codeEl, ev.clientX, ev.clientY) : 0;
      placeCursor(ln, col);
    }}
  }});

  // ---- Keyboard: arrow keys move cursor ----
  codewrap.addEventListener("keydown", (ev) => {{
    const key = ev.key;
    if (key === "ArrowUp") {{
      ev.preventDefault();
      const newLine = Math.max(0, curLine - 1);
      const newCol = Math.min(curCol, (lines[newLine] || "").length);
      placeCursor(newLine, newCol);
    }} else if (key === "ArrowDown") {{
      ev.preventDefault();
      const newLine = Math.min(lines.length - 1, curLine + 1);
      const newCol = Math.min(curCol, (lines[newLine] || "").length);
      placeCursor(newLine, newCol);
    }} else if (key === "ArrowLeft") {{
      ev.preventDefault();
      if (curCol > 0) {{
        placeCursor(curLine, curCol - 1);
      }} else if (curLine > 0) {{
        const newLine = curLine - 1;
        placeCursor(newLine, (lines[newLine] || "").length);
      }}
    }} else if (key === "ArrowRight") {{
      ev.preventDefault();
      const lineText = lines[curLine] || "";
      if (curCol < lineText.length) {{
        placeCursor(curLine, curCol + 1);
      }} else if (curLine < lines.length - 1) {{
        placeCursor(curLine + 1, 0);
      }}
    }}
  }});

  placeCursor(0, 0);

  const body = document.body;
  const toggle = document.getElementById("themeToggle");
  function applyTheme(t) {{
    body.classList.remove("theme-light", "theme-dark");
    body.classList.add(`theme-${{t}}`);
    localStorage.setItem("lean-theme", t);
  }}
  const savedTheme = localStorage.getItem("lean-theme");
  if (savedTheme === "dark" || savedTheme === "light") {{
    applyTheme(savedTheme);
  }} else {{
    applyTheme(window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  }}
  toggle.addEventListener("click", () => {{
    const next = body.classList.contains("theme-dark") ? "light" : "dark";
    applyTheme(next);
  }});
</script>
</body>
</html>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_out, encoding="utf-8")
