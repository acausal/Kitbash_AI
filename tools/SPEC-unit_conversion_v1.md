# SPEC: Unit Conversion Tool v1

**Version:** 1.0  
**Status:** Ready for implementation  
**Target:** Kitbash tool registry (standalone tool)  
**Depends:** stdlib only

---

## Purpose

Convert numeric values between different units of measurement. Common units only; no exotic or historical units.

---

## Interface

### Tool Call

```
convert_units(
    value: float,           # e.g., 100
    from_unit: str,         # e.g., "celsius"
    to_unit: str,           # e.g., "fahrenheit"
    precision: int = 2,     # decimal places (default 2)
)
```

### Return Value

```json
{
  "value": 100.0,
  "from_unit": "celsius",
  "to_unit": "fahrenheit",
  "result": 212.0,
  "precision": 2,
  "status": "success"
}
```

### Error Cases

```json
{
  "status": "error",
  "reason": "Unknown unit: 'fahrenheight' (did you mean 'fahrenheit'?)",
  "from_unit": "celsius",
  "to_unit": "fahrenheight"
}
```

```json
{
  "status": "error",
  "reason": "Incompatible units: cannot convert from 'celsius' (temperature) to 'meters' (distance)",
  "from_unit": "celsius",
  "to_unit": "meters"
}
```

---

## Semantics

### Categories & Supported Units

**Temperature:**
- `celsius` (C)
- `fahrenheit` (F)
- `kelvin` (K)

**Distance / Length:**
- `millimeters` (mm)
- `centimeters` (cm)
- `meters` (m)
- `kilometers` (km)
- `inches` (in)
- `feet` (ft)
- `yards` (yd)
- `miles` (mi)
- `nautical_miles` (nmi)

**Weight / Mass:**
- `milligrams` (mg)
- `grams` (g)
- `kilograms` (kg)
- `metric_tons` (t)
- `ounces` (oz)
- `pounds` (lb)
- `tons` (US short tons)

**Volume:**
- `milliliters` (ml)
- `liters` (l)
- `fluid_ounces` (fl oz)
- `cups` (cup)
- `pints` (pt)
- `quarts` (qt)
- `gallons` (gal)

**Time:**
- `milliseconds` (ms)
- `seconds` (s)
- `minutes` (min)
- `hours` (h)
- `days` (d)
- `weeks` (wk)

**Area:**
- `square_millimeters` (mm²)
- `square_centimeters` (cm²)
- `square_meters` (m²)
- `square_kilometers` (km²)
- `square_inches` (in²)
- `square_feet` (ft²)
- `acres` (ac)
- `square_miles` (mi²)

### Unit Aliases

Users can use either full name or common alias:

```
convert_units(100, "celsius", "fahrenheit")    # ✓
convert_units(100, "C", "F")                   # ✓
convert_units(100, "celsius", "F")             # ✓
```

All forms are accepted and equivalent.

### Special Cases: Temperature

Temperature conversions are **absolute** (not relative/delta):
- Celsius ↔ Fahrenheit ↔ Kelvin: absolute conversion
- 0°C = 32°F = 273.15K

If you need *delta* conversion (e.g., "a 10°C change = how many °F change?"), the tool still works correctly (10°C delta = 18°F delta).

### Precision

Rounds result to specified decimal places (default 2).

```
convert_units(1, "meters", "feet", precision=2)   # 3.28
convert_units(1, "meters", "feet", precision=6)   # 3.280839
```

---

## Implementation Notes

### Conversion Tables

Store as a hierarchical dict or flat table. Each unit maps to a base unit + conversion factor:

```python
CONVERSIONS = {
    "distance": {
        "meters": ("meters", 1.0),
        "kilometers": ("meters", 1000.0),
        "miles": ("meters", 1609.34),
        "feet": ("meters", 0.3048),
        # ...
    },
    "weight": {
        "kilograms": ("kilograms", 1.0),
        "pounds": ("kilograms", 0.453592),
        # ...
    },
    "temperature": {
        # Special handling (not a simple factor)
    },
    # ...
}
```

### Algorithm

1. Parse `from_unit` and `to_unit` (accept full name or alias).
2. Check both units are known.
3. Check both units are in the same category (distance ↔ distance, not distance ↔ weight).
4. If temperature: use special conversion formulas. Else:
5. Convert from `from_unit` to base unit, then base unit to `to_unit`.
6. Round to precision and return.

### Temperature Conversions

```python
def celsius_to_fahrenheit(c):
    return c * 9/5 + 32

def fahrenheit_to_celsius(f):
    return (f - 32) * 5/9

def celsius_to_kelvin(c):
    return c + 273.15

def kelvin_to_celsius(k):
    return k - 273.15
```

---

## Data Structure

### Input Schema

```json
{
  "value": 100.0,
  "from_unit": "celsius",
  "to_unit": "fahrenheit",
  "precision": 2
}
```

### Output Schema

**Success:**
```json
{
  "status": "success",
  "value": 100.0,
  "from_unit": "celsius",
  "to_unit": "fahrenheit",
  "result": 212.0,
  "precision": 2
}
```

**Error:**
```json
{
  "status": "error",
  "reason": "Unknown unit: 'fahrenheight'",
  "from_unit": "celsius",
  "to_unit": "fahrenheight"
}
```

---

## Testing

### Unit Test Examples

```python
def test_distance():
    result = convert_units(1, "kilometers", "meters")
    assert result["result"] == 1000.0

def test_distance_imperial():
    result = convert_units(1, "miles", "kilometers", precision=2)
    assert abs(result["result"] - 1.61) < 0.01

def test_weight():
    result = convert_units(1, "kilograms", "pounds", precision=2)
    assert abs(result["result"] - 2.20) < 0.01

def test_temperature():
    result = convert_units(0, "celsius", "fahrenheit")
    assert result["result"] == 32.0
    
    result = convert_units(100, "celsius", "fahrenheit")
    assert result["result"] == 212.0
    
    result = convert_units(0, "celsius", "kelvin")
    assert result["result"] == 273.15

def test_aliases():
    result1 = convert_units(1, "kilometers", "meters")
    result2 = convert_units(1, "km", "m")
    assert result1["result"] == result2["result"]

def test_precision():
    result = convert_units(1, "meters", "feet", precision=4)
    assert abs(result["result"] - 3.2808) < 0.0001

def test_unknown_unit():
    error = convert_units(1, "meters", "foobar")
    assert error["status"] == "error"
    assert "Unknown unit" in error["reason"]

def test_incompatible_units():
    error = convert_units(1, "meters", "kilograms")
    assert error["status"] == "error"
    assert "Incompatible" in error["reason"]
```

---

## CLI

```bash
python -m tools.unit_conversion convert 100 celsius fahrenheit
# Output:
# {
#   "status": "success",
#   "value": 100.0,
#   "from_unit": "celsius",
#   "to_unit": "fahrenheit",
#   "result": 212.0,
#   "precision": 2
# }

python -m tools.unit_conversion convert 1 kilometers meters
# Output:
# {
#   "status": "success",
#   "value": 1.0,
#   "from_unit": "kilometers",
#   "to_unit": "meters",
#   "result": 1000.0,
#   "precision": 2
# }

python -m tools.unit_conversion convert 1 meters kilograms
# Output:
# {
#   "status": "error",
#   "reason": "Incompatible units: cannot convert from 'meters' (distance) to 'kilograms' (weight)",
#   "from_unit": "meters",
#   "to_unit": "kilograms"
# }
```

---

## Non-Goals

- **Exotic units:** No historical units (cubit, furlong), no specialized scientific units (parsec, barn), no regional units (pood, tael).
- **Currency conversion:** Requires real-time data. Deferred to post-1.0 (v2).
- **Custom units:** Can't define new units. Only predefined set.
- **Compound units:** No complex units like km/h or kg/m³. Single dimension only.
- **Uncertainties / ranges:** No error bars or tolerances. Single scalar only.

---

## Related Components

- **Math Evaluation** — can use converted values in calculations
- **CSV Operations** — can batch-convert columns of numbers
- **Data Validation** — can validate unit fields in structured data
