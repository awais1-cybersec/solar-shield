"""Shared telemetry contract. Feature order must match the original training pipeline."""
import math
FEATURES = ("DC_voltage", "DC_current", "AC_voltage", "AC_frequency", "output_power", "power_factor", "inverter_temperature", "irradiance")

def extract_features(payload):
    values=[]
    for key in FEATURES:
        value=payload[key]
        if isinstance(value,bool): raise ValueError(f"Boolean feature: {key}")
        value=float(value)
        if not math.isfinite(value): raise ValueError(f"Non-finite feature: {key}")
        values.append(value)
    return values
