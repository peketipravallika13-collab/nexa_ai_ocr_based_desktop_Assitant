"""
Calculator Plugin for Nexa AI (No API Key Required)
---------------------------------------------------
Performs mathematical calculations, scientific formulas, statistical analysis,
unit conversions, and financial calculations completely offline.
"""

import math
import statistics
import logging

logger = logging.getLogger("calculator_plugin")

PLUGIN_SCHEMA = {
    "name": "calculator",
    "description": "Perform mathematical evaluations, scientific calculations, statistical analysis, unit conversions, and financial math without needing any external API key.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "expression": {
                "type": "STRING",
                "description": "The math expression to evaluate (e.g. '2 ** 10 + sqrt(144)', 'sin(radians(30))', '1500 * (1 + 0.05)**5')."
            },
            "operation_type": {
                "type": "STRING",
                "description": "Optional operation type: 'calculate' (default), 'statistics', 'unit_convert', or 'finance'."
            },
            "data": {
                "type": "STRING",
                "description": "Comma-separated numerical values for statistics (e.g. '12, 15, 23, 45, 67, 89') or conversion string (e.g. '100 km to miles', '75 kg to lbs', '32 C to F')."
            }
        },
        "required": ["expression"]
    }
}

# Unit conversion ratios to standard base units (SI base)
LENGTH_TO_METERS = {
    "km": 1000.0, "kilometer": 1000.0, "kilometers": 1000.0,
    "m": 1.0, "meter": 1.0, "meters": 1.0,
    "cm": 0.01, "centimeter": 0.01, "centimeters": 0.01,
    "mm": 0.001, "millimeter": 0.001, "millimeters": 0.001,
    "mi": 1609.344, "mile": 1609.344, "miles": 1609.344,
    "yd": 0.9144, "yard": 0.9144, "yards": 0.9144,
    "ft": 0.3048, "foot": 0.3048, "feet": 0.3048,
    "in": 0.0254, "inch": 0.0254, "inches": 0.0254
}

WEIGHT_TO_KG = {
    "kg": 1.0, "kilogram": 1.0, "kilograms": 1.0,
    "g": 0.001, "gram": 0.001, "grams": 0.001,
    "mg": 0.000001, "milligram": 0.000001, "milligrams": 0.000001,
    "lb": 0.45359237, "lbs": 0.45359237, "pound": 0.45359237, "pounds": 0.45359237,
    "oz": 0.028349523125, "ounce": 0.028349523125, "ounces": 0.028349523125,
    "ton": 1000.0, "tons": 1000.0, "tonne": 1000.0
}

DATA_TO_BYTES = {
    "b": 1, "byte": 1, "bytes": 1,
    "kb": 1024, "kilobyte": 1024, "kilobytes": 1024,
    "mb": 1024**2, "megabyte": 1024**2, "megabytes": 1024**2,
    "gb": 1024**3, "gigabyte": 1024**3, "gigabytes": 1024**3,
    "tb": 1024**4, "terabyte": 1024**4, "terabytes": 1024**4,
    "pb": 1024**5, "petabyte": 1024**5, "petabytes": 1024**5
}


def _safe_math_eval(expr: str) -> float:
    """Evaluate mathematical expression within a sandboxed math scope."""
    allowed = {
        "abs": abs, "round": round, "min": min, "max": max, "sum": sum, "pow": pow,
        "math": math, "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "asin": math.asin, "acos": math.acos, "atan": math.atan, "atan2": math.atan2,
        "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
        "sqrt": math.sqrt, "isqrt": math.isqrt, "cbrt": lambda x: x ** (1/3),
        "log": math.log, "log10": math.log10, "log2": math.log2, "exp": math.exp,
        "pi": math.pi, "e": math.e, "tau": math.tau, "inf": math.inf,
        "ceil": math.ceil, "floor": math.floor, "factorial": math.factorial,
        "gcd": math.gcd, "lcm": math.lcm if hasattr(math, "lcm") else (lambda a, b: abs(a * b) // math.gcd(a, b)),
        "comb": math.comb if hasattr(math, "comb") else None,
        "perm": math.perm if hasattr(math, "perm") else None,
        "radians": math.radians, "degrees": math.degrees
    }
    return eval(expr.strip(), {"__builtins__": {}}, allowed)


def _convert_units(query: str) -> str:
    """Parse and convert length, weight, data, or temperature units."""
    # Pattern e.g. "100 km to miles" or "32 C to F"
    parts = query.lower().replace("into", "to").replace("in", "to").split("to")
    if len(parts) != 2:
        return f"Could not parse conversion '{query}'. Format example: '100 km to miles' or '32 c to f'."
    
    left = parts[0].strip().split()
    target_unit = parts[1].strip()
    
    if len(left) < 2:
        return f"Invalid source value and unit in '{parts[0]}'."
    
    try:
        val = float(left[0])
    except ValueError:
        return f"Invalid number '{left[0]}'."
        
    src_unit = left[1].lower().strip()
    target_unit = target_unit.lower().strip()
    
    # Temperature conversions
    if src_unit in ("c", "celsius", "°c") and target_unit in ("f", "fahrenheit", "°f"):
        converted = (val * 9/5) + 32
        return f"🌡️ **Temperature Conversion:**\n{val}°C = **{round(converted, 4)}°F**"
    elif src_unit in ("f", "fahrenheit", "°f") and target_unit in ("c", "celsius", "°c"):
        converted = (val - 32) * 5/9
        return f"🌡️ **Temperature Conversion:**\n{val}°F = **{round(converted, 4)}°C**"
    elif src_unit in ("c", "celsius", "°c") and target_unit in ("k", "kelvin"):
        converted = val + 273.15
        return f"🌡️ **Temperature Conversion:**\n{val}°C = **{round(converted, 4)} K**"
    elif src_unit in ("k", "kelvin") and target_unit in ("c", "celsius", "°c"):
        converted = val - 273.15
        return f"🌡️ **Temperature Conversion:**\n{val} K = **{round(converted, 4)}°C**"
        
    # Length conversions
    if src_unit in LENGTH_TO_METERS and target_unit in LENGTH_TO_METERS:
        meters = val * LENGTH_TO_METERS[src_unit]
        converted = meters / LENGTH_TO_METERS[target_unit]
        return f"📏 **Length Conversion:**\n{val} {src_unit} = **{round(converted, 6)} {target_unit}**"
        
    # Weight conversions
    if src_unit in WEIGHT_TO_KG and target_unit in WEIGHT_TO_KG:
        kg = val * WEIGHT_TO_KG[src_unit]
        converted = kg / WEIGHT_TO_KG[target_unit]
        return f"⚖️ **Weight Conversion:**\n{val} {src_unit} = **{round(converted, 6)} {target_unit}**"
        
    # Data conversions
    if src_unit in DATA_TO_BYTES and target_unit in DATA_TO_BYTES:
        bytes_val = val * DATA_TO_BYTES[src_unit]
        converted = bytes_val / DATA_TO_BYTES[target_unit]
        return f"💾 **Digital Storage Conversion:**\n{val} {src_unit.upper()} = **{round(converted, 6)} {target_unit.upper()}**"
        
    return f"Unsupported unit conversion from '{src_unit}' to '{target_unit}'."


def _compute_statistics(data_str: str) -> str:
    """Compute summary statistics for a dataset."""
    try:
        numbers = [float(x.strip()) for x in data_str.replace(";", ",").split(",") if x.strip()]
    except ValueError as e:
        return f"Error parsing data values: {e}"
        
    if not numbers:
        return "Error: No numbers provided for statistical analysis."
        
    n = len(numbers)
    mean_val = statistics.mean(numbers)
    median_val = statistics.median(numbers)
    try:
        mode_val = statistics.mode(numbers)
    except statistics.StatisticsError:
        mode_val = "No unique mode"
        
    stdev_val = statistics.stdev(numbers) if n > 1 else 0.0
    variance_val = statistics.variance(numbers) if n > 1 else 0.0
    min_val = min(numbers)
    max_val = max(numbers)
    sum_val = sum(numbers)
    range_val = max_val - min_val
    
    return (
        f"📊 **Statistical Summary (Sample Count: {n}):**\n\n"
        f"- **Sum:** `{round(sum_val, 4)}`\n"
        f"- **Mean (Average):** `**{round(mean_val, 4)}**`\n"
        f"- **Median:** `{round(median_val, 4)}`\n"
        f"- **Mode:** `{mode_val}`\n"
        f"- **Min / Max:** `{min_val}` / `{max_val}` (Range: `{round(range_val, 4)}`)\n"
        f"- **Standard Deviation:** `{round(stdev_val, 4)}`\n"
        f"- **Variance:** `{round(variance_val, 4)}`"
    )


def run(expression: str = "", operation_type: str = "calculate", data: str = "") -> str:
    """Execute mathematical computation, unit conversion, or statistical analysis."""
    op = (operation_type or "calculate").lower().strip()
    expr = (expression or "").strip()
    
    # Auto-detect conversion or stats if mentioned
    if op in ("unit_convert", "convert") or (" to " in expr.lower() and any(u in expr.lower() for u in ["km", "miles", "kg", "lbs", "c", "f", "gb", "mb", "meters", "feet"])):
        target = data if data else expr
        return _convert_units(target)
        
    if op in ("statistics", "stats") or (data and not expr):
        target_data = data if data else expr
        return _compute_statistics(target_data)
        
    if not expr:
        return "Error: Mathematical expression was not provided."
        
    # Standard or advanced calculation
    try:
        result = _safe_math_eval(expr)
        
        # Format floating points cleanly
        if isinstance(result, float):
            if result.is_integer():
                formatted_res = int(result)
            else:
                formatted_res = round(result, 8)
        else:
            formatted_res = result
            
        return (
            f"🧮 **Calculation Result:**\n\n"
            f"- **Input:** `{expr}`\n"
            f"- **Result:** **`{formatted_res}`**\n"
            f"*(Computed locally via Nexa Offline Math Engine)*"
        )
    except Exception as e:
        logger.error(f"Calculator execution error on '{expr}': {e}")
        return f"Error evaluating expression `{expr}`: {str(e)}"
