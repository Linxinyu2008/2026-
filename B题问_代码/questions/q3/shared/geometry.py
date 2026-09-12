"""基于多次 BEARING 观测的二维角域置信区域摘要。

这里使用与第一问相同的有界角误差半平面模型，不读取场景真值。
"""

from __future__ import annotations

from typing import Iterable

from questions.q1.localization_region import solve_localization_region
from .models import Measurement, Point


def region_summary(measurements: Iterable[Measurement], epsilon_deg: float = 1.0) -> dict:
    positive = [item for item in measurements if item.signal == "BEARING" and item.bearing_deg is not None]
    if not positive:
        return {"status": "UNBOUNDED_REGION", "center": None, "radius_m": None, "area_m2": None, "vertices": ()}
    result = solve_localization_region(
        [measurement.point for measurement in positive],
        [float(measurement.bearing_deg) for measurement in positive],
        epsilon_deg,
    )
    if result["status"] != "OK":
        return {"status": result["status"], "center": None, "radius_m": None, "area_m2": None, "vertices": tuple(result.get("vertices", ())) }
    return {
        "status": "OK", "center": result["mec_center"], "radius_m": result["mec_radius"],
        "area_m2": result["area"], "vertices": tuple(result["vertices"]),
    }
