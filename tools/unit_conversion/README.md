# unit_conversion

Convert numeric values between units of measurement across 6 categories
(temperature, distance, weight, volume, time, area). No real-time data; common
units only. `tools.unit_conversion`.

## Interface

```python
convert_units(100, "celsius", "fahrenheit")   # {"status":"success","result":212.0,...}
convert_units(1, "kilometers", "meters")       # result 1000.0
convert_units(1, "km", "m")                     # aliases work
convert_units(1, "meters", "kilograms")        # {"status":"error","reason":"Incompatible units:..."}
```

| Function | Purpose |
|----------|---------|
| `convert_units(value, from_unit, to_unit, precision=2)` | Convert; return result/error dict |

**Supported units:** see `SPEC-unit_conversion_v1.md` (full names + aliases:
C/F/K, km/m, kg/lb, l/ml, s/min/h, m²/ft², …). Temperature is absolute
(C↔F↔K). Unknown unit returns a `did you mean?` hint; incompatible category
errors. Errors returned as dicts, never raised.

## CLI

```bash
python -m tools.unit_conversion convert 100 celsius fahrenheit
python -m tools.unit_conversion convert 1 kilometers meters --precision 4
```

JSON to stdout, summary to stderr. Exit 0 = success, 1 = error. Pure stdlib;
same `PYTHONPATH= ` prefix rule in the Kitbash `.venv`.

**Spec:** `SPEC-unit_conversion_v1.md` · **Test:** `TEST-unit_conversion_examples.json`
