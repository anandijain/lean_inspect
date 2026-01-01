## lean-inspect

Tools for extracting Lean goal traces via the Lean LSP and wiring them into doc-gen output.

### Usage

- Trace a single file:
  - `uv run lean-inspect trace-file /path/to/File.lean --out traces/File.trace.json --mode adaptive --progress`
- Trace an entire project (all `.lean` files under `PROJECT_ROOT/PROJECT/`):
  - `uv run lean-inspect trace-project /path/to/PROJECT --out-dir traces --mode adaptive --html --progress`
  - JSON is written with `.trace.json`; if `--html` is set, a companion `.trace.html` viewer is emitted.
- Inject trace links into doc-gen HTML (adds a “trace” link next to the source link):
  - `uv run lean-inspect inject-doc /path/to/docbuild/.lake/build/doc /path/to/PROJECT /path/to/TRACES --progress`

The `lake` binary is auto-discovered (`lake` on PATH or `~/.elan/bin/lake`). Use `--lake /custom/path` to override.

