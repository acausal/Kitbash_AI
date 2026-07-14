"""tools.unit_conversion core (stdlib only).

Convert numeric values between units across 6 categories. Factor-to-base for
linear units; absolute formulas for temperature. See SPEC-unit_conversion_v1.md.
"""
from typing import Any, Dict, List, Optional, Tuple

# category -> {unit: (base_unit, factor_to_base)}
_UNITS: Dict[str, Dict[str, Tuple[str, float]]] = {
    "temperature": {},  # handled specially
    "distance": {
        "millimeters": ("meters", 0.001), "mm": ("meters", 0.001),
        "centimeters": ("meters", 0.01), "cm": ("meters", 0.01),
        "meters": ("meters", 1.0), "m": ("meters", 1.0),
        "kilometers": ("meters", 1000.0), "km": ("meters", 1000.0),
        "inches": ("meters", 0.0254), "in": ("meters", 0.0254),
        "feet": ("meters", 0.3048), "ft": ("meters", 0.3048),
        "yards": ("meters", 0.9144), "yd": ("meters", 0.9144),
        "miles": ("meters", 1609.34), "mi": ("meters", 1609.34),
        "nautical_miles": ("meters", 1852.0), "nmi": ("meters", 1852.0),
    },
    "weight": {
        "milligrams": ("kilograms", 0.000001), "mg": ("kilograms", 0.000001),
        "grams": ("kilograms", 0.001), "g": ("kilograms", 0.001),
        "kilograms": ("kilograms", 1.0), "kg": ("kilograms", 1.0),
        "metric_tons": ("kilograms", 1000.0), "t": ("kilograms", 1000.0),
        "ounces": ("kilograms", 0.0283495), "oz": ("kilograms", 0.0283495),
        "pounds": ("kilograms", 0.453592), "lb": ("kilograms", 0.453592),
        "tons": ("kilograms", 907.185), "tons": ("kilograms", 907.185),
    },
    "volume": {
        "milliliters": ("liters", 0.001), "ml": ("liters", 0.001),
        "liters": ("liters", 1.0), "l": ("liters", 1.0),
        "fluid_ounces": ("liters", 0.0295735), "fl oz": ("liters", 0.0295735),
        "cups": ("liters", 0.236588), "cup": ("liters", 0.236588),
        "pints": ("liters", 0.473176), "pt": ("liters", 0.473176),
        "quarts": ("liters", 0.946353), "qt": ("liters", 0.946353),
        "gallons": ("liters", 3.78541), "gal": ("liters", 3.78541),
    },
    "time": {
        "milliseconds": ("seconds", 0.001), "ms": ("seconds", 0.001),
        "seconds": ("seconds", 1.0), "s": ("seconds", 1.0),
        "minutes": ("seconds", 60.0), "min": ("seconds", 60.0),
        "hours": ("seconds", 3600.0), "h": ("seconds", 3600.0),
        "days": ("seconds", 86400.0), "d": ("seconds", 86400.0),
        "weeks": ("seconds", 604800.0), "wk": ("seconds", 604800.0),
    },
    "area": {
        "square_millimeters": ("square_meters", 0.000001), "mm2": ("square_meters", 0.000001),
        "square_centimeters": ("square_meters", 0.0001), "cm2": ("square_meters", 0.0001),
        "square_meters": ("square_meters", 1.0), "m2": ("square_meters", 1.0),
        "square_kilometers": ("square_meters", 1000000.0), "km2": ("square_meters", 1000000.0),
        "square_inches": ("square_meters", 0.00064516), "in2": ("square_meters", 0.00064516),
        "square_feet": ("square_meters", 0.092903), "ft2": ("square_meters", 0.092903),
        "acres": ("square_meters", 4046.86), "ac": ("square_meters", 4046.86),
        "square_miles": ("square_meters", 2589988.0), "mi2": ("square_meters", 2589988.0),
    },
}

# Friendly display aliases (superset of the above canonical keys).
_ALIASES = {
    "celsius": "celsius", "c": "celsius",
    "fahrenheit": "fahrenheit", "f": "fahrenheit",
    "kelvin": "kelvin", "k": "kelvin",
}
_CATEGORY_OF: Dict[str, str] = {}
for _cat, _tbl in _UNITS.items():
    for _u in _tbl:
        _CATEGORY_OF[_u] = _cat
for _a, _canon in _ALIASES.items():
    _CATEGORY_OF[_a] = "temperature"


def _norm(unit: str) -> Optional[str]:
    u = unit.strip().lower()
    if u in _CATEGORY_OF:
        return u
    return None


def _did_you_mean(unit: str, category: Optional[str] = None) -> Optional[str]:
    pool = [u for u in _CATEGORY_OF if (category is None or _CATEGORY_OF[u] == category)]
    best = None
    best_d = 99
    for u in pool:
        d = _lev(unit.lower(), u)
        if d < best_d:
            best_d, best = d, u
    return best if best_d <= 3 else None


def _lev(a: str, b: str) -> int:
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la
    prev = list(range(lb + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[lb]


def _temp_to_base(v: float, unit: str) -> float:
    # base = celsius
    if unit == "celsius":
        return v
    if unit == "fahrenheit":
        return (v - 32) * 5 / 9
    if unit == "kelvin":
        return v - 273.15
    raise ValueError(f"unknown temperature unit: {unit}")


def _temp_from_base(v: float, unit: str) -> float:
    if unit == "celsius":
        return v
    if unit == "fahrenheit":
        return v * 9 / 5 + 32
    if unit == "kelvin":
        return v + 273.15
    raise ValueError(f"unknown temperature unit: {unit}")


def convert_units(value: float, from_unit: str, to_unit: str, precision: int = 2) -> Dict[str, Any]:
    """Convert `value` from `from_unit` to `to_unit`. Returns result/error dict."""
    try:
        val = float(value)
    except (TypeError, ValueError):
        return {"status": "error", "reason": f"invalid value: {value!r}", "from_unit": from_unit, "to_unit": to_unit}
    fu = _norm(from_unit)
    tu = _norm(to_unit)
    if fu is None:
        sug = _did_you_mean(from_unit)
        hint = f" (did you mean '{sug}'?)" if sug else ""
        return {"status": "error", "reason": f"Unknown unit: '{from_unit}'{hint}", "from_unit": from_unit, "to_unit": to_unit}
    if tu is None:
        sug = _did_you_mean(to_unit)
        hint = f" (did you mean '{sug}'?)" if sug else ""
        return {"status": "error", "reason": f"Unknown unit: '{to_unit}'{hint}", "from_unit": from_unit, "to_unit": to_unit}
    cat_f = _CATEGORY_OF[fu]
    cat_t = _CATEGORY_OF[tu]
    if cat_f != cat_t:
        return {"status": "error", "reason":
                f"Incompatible units: cannot convert from '{from_unit}' ({cat_f}) to '{to_unit}' ({cat_t})",
                "from_unit": from_unit, "to_unit": to_unit}
    if cat_f == "temperature":
        base = _temp_to_base(val, fu)
        result = _temp_from_base(base, tu)
    else:
        _, f_factor = _UNITS[cat_f][fu]
        _, t_factor = _UNITS[cat_t][tu]
        base = val * f_factor
        result = base / t_factor
    rounded = round(result, precision)
    return {
        "status": "success",
        "value": val,
        "from_unit": from_unit,
        "to_unit": to_unit,
        "result": rounded,
        "precision": precision,
    }
