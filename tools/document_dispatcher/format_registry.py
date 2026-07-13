"""Centralized format -> (module, func) mapping for the dispatcher.

Most formats follow the default convention
tools.<format>_extractor / convert_<format>_to_markdown; PDF is the documented
exception (its real package is tools.pdf_to_markdown), so it is overridden
explicitly rather than forcing a rename.
"""
from __future__ import annotations

# format -> (importable module path, callable name)
# Override formats whose package/module name diverges from the default
# tools.<format>_extractor / convert_<format>_to_markdown convention.
EXTRACTOR_OVERRIDES: dict[str, tuple[str, str]] = {
    "pdf": ("tools.pdf_to_markdown", "convert_pdf_to_markdown"),
}


def resolve_extractor(format_name: str) -> tuple[str, str]:
    """Return (module_path, func_name) for a format name.

    Falls back to the default naming convention unless an override exists.
    """
    if format_name in EXTRACTOR_OVERRIDES:
        return EXTRACTOR_OVERRIDES[format_name]
    return (
        f"tools.{format_name}_extractor",
        f"convert_{format_name}_to_markdown",
    )
