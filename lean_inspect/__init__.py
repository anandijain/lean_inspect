"""Tools for extracting Lean goal traces and wiring them into doc-gen output."""

from importlib.metadata import version, PackageNotFoundError


def __getattr__(name: str):
    if name == "__version__":
        try:
            return version("lean-inspect")
        except PackageNotFoundError:
            return "0.0.0"
    raise AttributeError(name)
