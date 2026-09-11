"""B题第一问：有界示向误差下的二维交会定位。

只使用 Python 标准库，核心流程为：
角域 -> 半平面 -> 边界交点筛选 -> 凸包 -> 直径/覆盖圆/MEC。
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import cos, hypot, pi, sin
from typing import Iterable, Optional, Sequence


Point = tuple[float, float]
EPS = 1e-10


@dataclass(frozen=True)
class HalfPlane:
    """统一表示为 a*x + b*y <= c。"""

    a: float
    b: float
    c: float


def _cross(u: Point, v: Point) -> float:
    return u[0] * v[1] - u[1] * v[0]


def _sub(p: Point, q: Point) -> Point:
    return p[0] - q[0], p[1] - q[1]


def _dot(u: Point, v: Point) -> float:
    return u[0] * v[0] + u[1] * v[1]


def _distance(p: Point, q: Point) -> float:
    return hypot(p[0] - q[0], p[1] - q[1])


def build_halfplanes(
    stations: Sequence[Point],
    bearings_deg: Sequence[float],
    epsilon_deg: float = 1.0,
) -> list[HalfPlane]:
    """把每个检测点的 ±epsilon 角域转换为两个半平面。

    角度按数学坐标系解释：0° 沿 x 轴正向，90° 沿 y 轴正向。
    角度不强制归一化，因此天然支持跨越 0°/360° 的角域。
    """
    if len(stations) != len(bearings_deg):
        raise ValueError("stations 和 bearings_deg 的长度必须一致")
    if epsilon_deg <= 0 or epsilon_deg >= 90:
        raise ValueError("epsilon_deg 应满足 0 < epsilon_deg < 90")

    halfplanes: list[HalfPlane] = []
    for (sx, sy), bearing in zip(stations, bearings_deg):
        alpha = (bearing - epsilon_deg) * pi / 180.0
        beta = (bearing + epsilon_deg) * pi / 180.0

        sa, ca = sin(alpha), cos(alpha)
        sb, cb = sin(beta), cos(beta)

        # u_minus × (G-S) >= 0
        halfplanes.append(HalfPlane(sa, -ca, sa * sx - ca * sy))
        # u_plus × (G-S) <= 0
        halfplanes.append(HalfPlane(-sb, cb, -sb * sx + cb * sy))
    return halfplanes


def _line_intersection(h1: HalfPlane, h2: HalfPlane) -> Optional[Point]:
    det = h1.a * h2.b - h2.a * h1.b
    scale = max(1.0, abs(h1.a), abs(h1.b), abs(h2.a), abs(h2.b))
    if abs(det) <= 1e-12 * scale:
        return None
    x = (h1.c * h2.b - h2.c * h1.b) / det
    y = (h1.a * h2.c - h2.a * h1.c) / det
    return x, y


def _satisfies(point: Point, halfplanes: Sequence[HalfPlane], tol: float) -> bool:
    x, y = point
    return all(h.a * x + h.b * y <= h.c + tol for h in halfplanes)


def _deduplicate(points: Iterable[Point], tol: float) -> list[Point]:
    result: list[Point] = []
    for point in points:
        if not any(_distance(point, old) <= tol for old in result):
            result.append(point)
    return result


def _has_recession_direction(halfplanes: Sequence[HalfPlane], tol: float) -> bool:
    """检测是否存在非零 d，使所有 a*d_x+b*d_y <= 0。

    在二维中，若齐次可行锥非空，其边界方向必位于某个约束的边界线上，
    因此枚举每个法向量的两个垂直方向即可完成稳定的小规模检测。
    """
    if not halfplanes:
        return True
    directions: list[Point] = []
    for h in halfplanes:
        norm = hypot(h.a, h.b)
        if norm <= tol:
            continue
        d = (-h.b / norm, h.a / norm)
        directions.extend((d, (-d[0], -d[1])))
    return any(
        all(h.a * dx + h.b * dy <= tol for h in halfplanes)
        for dx, dy in directions
    )


def _feasible_point(halfplanes: Sequence[HalfPlane], tol: float) -> Optional[Point]:
    """返回任一可行点；先确认非空，避免把空集误判为无界。"""
    if not halfplanes:
        return (0.0, 0.0)
    candidates: list[Point] = [(0.0, 0.0)]
    for halfplane in halfplanes:
        norm2 = halfplane.a * halfplane.a + halfplane.b * halfplane.b
        if norm2 > EPS:
            candidates.append((halfplane.a * halfplane.c / norm2, halfplane.b * halfplane.c / norm2))
    candidates.extend(
        point
        for first, second in combinations(halfplanes, 2)
        if (point := _line_intersection(first, second)) is not None
    )
    return next((point for point in candidates if _satisfies(point, halfplanes, tol)), None)


def convex_hull(points: Sequence[Point], tol: float = 1e-10) -> list[Point]:
    """Andrew 单调链凸包；返回逆时针顶点，不重复首点。"""
    pts = sorted(set((float(x), float(y)) for x, y in points))
    if len(pts) <= 1:
        return pts

    def turn(o: Point, a: Point, b: Point) -> float:
        return _cross(_sub(a, o), _sub(b, o))

    lower: list[Point] = []
    for p in pts:
        while len(lower) >= 2 and turn(lower[-2], lower[-1], p) <= tol:
            lower.pop()
        lower.append(p)

    upper: list[Point] = []
    for p in reversed(pts):
        while len(upper) >= 2 and turn(upper[-2], upper[-1], p) <= tol:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def polygon_area(vertices: Sequence[Point]) -> float:
    if len(vertices) < 3:
        return 0.0
    return abs(
        sum(
            vertices[i][0] * vertices[(i + 1) % len(vertices)][1]
            - vertices[(i + 1) % len(vertices)][0] * vertices[i][1]
            for i in range(len(vertices))
        )
    ) / 2.0


def polygon_diameter(vertices: Sequence[Point]) -> tuple[float, Point, Point]:
    if len(vertices) < 2:
        raise ValueError("至少需要两个顶点才能计算直径")
    best = (-1.0, vertices[0], vertices[1])
    for p, q in combinations(vertices, 2):
        distance = _distance(p, q)
        if distance > best[0]:
            best = distance, p, q
    return best


def diameter_circle_covers(
    vertices: Sequence[Point],
    diameter_endpoints: tuple[Point, Point],
    tol: float = 1e-8,
) -> bool:
    """用 Thales 判据检查以最远点对为直径的圆是否覆盖所有顶点。"""
    a, b = diameter_endpoints
    scale = max(1.0, _distance(a, b) ** 2)
    return all(_dot(_sub(v, a), _sub(v, b)) <= tol * scale for v in vertices)


def _circle_from_two(a: Point, b: Point) -> tuple[Point, float]:
    center = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
    return center, _distance(a, b) / 2.0


def _circle_from_three(
    a: Point, b: Point, c: Point, tol: float = 1e-12
) -> Optional[tuple[Point, float]]:
    ax, ay = a
    bx, by = b
    cx, cy = c
    det = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    scale = max(1.0, _distance(a, b), _distance(a, c), _distance(b, c)) ** 2
    if abs(det) <= tol * scale:
        return None
    aa, bb, cc = ax * ax + ay * ay, bx * bx + by * by, cx * cx + cy * cy
    ux = (aa * (by - cy) + bb * (cy - ay) + cc * (ay - by)) / det
    uy = (aa * (cx - bx) + bb * (ax - cx) + cc * (bx - ax)) / det
    center = (ux, uy)
    return center, _distance(center, a)


def minimum_enclosing_circle(vertices: Sequence[Point]) -> tuple[Point, float]:
    """有限点集的最小覆盖圆：枚举两点圆和三点外接圆。"""
    points = list(vertices)
    if not points:
        raise ValueError("空点集没有最小覆盖圆")

    # 若直径圆已经覆盖全部顶点，它就是有限点集的最小覆盖圆（Thales 判据）。
    # 这条快速路径对典型四边形/六边形区域可以跳过 O(n^3) 的三点枚举。
    if len(points) >= 2:
        diameter, a, b = polygon_diameter(points)
        if diameter_circle_covers(points, (a, b)):
            return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0), diameter / 2.0

    candidates: list[tuple[Point, float]] = [((points[0][0], points[0][1]), 0.0)]
    candidates.extend(_circle_from_two(a, b) for a, b in combinations(points, 2))
    for a, b, c in combinations(points, 3):
        circle = _circle_from_three(a, b, c)
        if circle is not None:
            candidates.append(circle)

    def covers(circle: tuple[Point, float]) -> bool:
        center, radius = circle
        tol = 1e-8 * max(1.0, radius)
        return all(_distance(center, p) <= radius + tol for p in points)

    valid = [circle for circle in candidates if covers(circle)]
    return min(valid, key=lambda item: item[1])


def solve_localization_region(
    stations: Sequence[Point],
    bearings_deg: Sequence[float],
    epsilon_deg: float = 1.0,
    tol: Optional[float] = None,
) -> dict:
    """求解第一问，返回状态、定位区域顶点及几何评价指标。"""
    if not stations:
        return {"status": "EMPTY_REGION", "reason": "没有检测点"}

    scale = max(1.0, *(abs(v) for p in stations for v in p))
    feas_tol = tol if tol is not None else 1e-9 * scale
    merge_tol = 1e-8 * scale
    halfplanes = build_halfplanes(stations, bearings_deg, epsilon_deg)

    feasible_point = _feasible_point(halfplanes, feas_tol)
    if feasible_point is None:
        return {"status": "EMPTY_REGION", "halfplanes": halfplanes}

    candidates: list[Point] = []
    for h1, h2 in combinations(halfplanes, 2):
        point = _line_intersection(h1, h2)
        if point is not None and _satisfies(point, halfplanes, feas_tol):
            candidates.append(point)
    candidates = _deduplicate(candidates, merge_tol)

    # 没有有限候选点时，仍需区分空集和无界集。
    if not candidates:
        if _has_recession_direction(halfplanes, 1e-10):
            return {"status": "UNBOUNDED_REGION", "halfplanes": halfplanes}
        return {"status": "DEGENERATE_REGION", "vertices": [feasible_point]}

    if _has_recession_direction(halfplanes, 1e-10):
        return {
            "status": "UNBOUNDED_REGION",
            "halfplanes": halfplanes,
            "finite_vertices": candidates,
        }

    vertices = convex_hull(candidates)
    if len(vertices) < 3 or polygon_area(vertices) <= 1e-10 * scale * scale:
        return {"status": "DEGENERATE_REGION", "vertices": vertices}

    diameter, a, b = polygon_diameter(vertices)
    center = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
    mec_center, mec_radius = minimum_enclosing_circle(vertices)
    return {
        "status": "OK",
        "vertices": vertices,
        "area": polygon_area(vertices),
        "diameter": diameter,
        "diameter_endpoints": (a, b),
        "diameter_circle_center": center,
        "diameter_circle_radius": diameter / 2.0,
        "diameter_circle_covers": diameter_circle_covers(vertices, (a, b)),
        "mec_center": mec_center,
        "mec_radius": mec_radius,
        "eta": 2.0 * mec_radius / diameter,
    }


if __name__ == "__main__":
    # 一个围绕原点的人工示例：四个检测点分别朝向目标区域。
    stations = [(0.0, -10.0), (10.0, 0.0), (0.0, 10.0), (-10.0, 0.0)]
    bearings = [90.0, 180.0, 270.0, 0.0]
    result = solve_localization_region(stations, bearings)
    print("status:", result["status"])
    if result["status"] == "OK":
        print("vertices:", result["vertices"])
        print("area:", result["area"])
        print("diameter:", result["diameter"])
        print("diameter_circle_covers:", result["diameter_circle_covers"])
        print("mec_radius:", result["mec_radius"])
        print("eta:", result["eta"])
