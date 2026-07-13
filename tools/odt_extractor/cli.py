"""cli for tools.odt_extractor. Usage:
    python -m tools.odt_extractor input.odt [-o out.md]
Exit 0 on success, 1 on failure (stderr message)."""
from __future__ import annotations
import argparse, os, sys
from . import convert_odt_to_markdown

def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="odt_extractor",
        description="ODT -> clean text (odfpy).")
    p.add_argument("input")
    p.add_argument("-o", "--output", default=None)
    a = p.parse_args(argv)
    out = a.output or os.path.join(os.path.dirname(os.path.abspath(a.input)),
                                    os.path.splitext(os.path.basename(a.input))[0] + ".md")
    try:
        convert_odt_to_markdown(a.input, out)
    except (FileNotFoundError, ValueError, RuntimeError, IOError) as e:
        print(f"error: {e}", file=sys.stderr); return 1
    except Exception as e:
        print(f"error: unexpected failure: {e}", file=sys.stderr); return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
