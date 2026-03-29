from __future__ import annotations

from prosperity.dsl.schema import StrategySpec

SUPPORTED_FAIR_VALUE_KINDS = {"constant", "mid", "microprice", "wall_mid", "ema"}
SUPPORTED_SIGNAL_KINDS = {"mean_reversion", "momentum", "imbalance", "trade_pressure", "volatility"}


def validate_spec(spec: StrategySpec) -> list[str]:
    errors: list[str] = []
    if not spec.scope.products:
        errors.append("Strategy must target at least one product")
    for component in spec.fair_value_models:
        if component.kind not in SUPPORTED_FAIR_VALUE_KINDS:
            errors.append(f"Unsupported fair value component: {component.kind}")
    for signal in spec.signal_models:
        if signal.kind not in SUPPORTED_SIGNAL_KINDS:
            errors.append(f"Unsupported signal component: {signal.kind}")
    for parameter in spec.parameter_space:
        if parameter.lower > parameter.upper:
            errors.append(f"Invalid bounds for parameter {parameter.name}")
        if not (parameter.lower <= parameter.default <= parameter.upper):
            errors.append(f"Default outside bounds for parameter {parameter.name}")
    return errors
