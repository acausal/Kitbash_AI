"""tools.unit_conversion package.

Library:
    from tools.unit_conversion import convert_units
    convert_units(100, "celsius", "fahrenheit")  # -> {"status":"success","result":212.0,...}

CLI:
    python -m tools.unit_conversion convert 100 celsius fahrenheit
    python -m tools.unit_conversion convert 1 kilometers meters

Converts across 6 categories (temperature, distance, weight, volume, time,
area) with full-name + alias support (C/F, km/m...). Temperature is absolute
(C<->F<->K); others factor-to-base. Unknown unit returns a "did you mean?"
hint; incompatible categories error. Errors returned as dicts, never raised.
Pure stdlib.
"""
from .core import convert_units

__all__ = ["convert_units"]
