"""只在本地复现审查发现，不调用 HTTP，不修改原代码。"""
import json
import sys
from pathlib import Path
from math import hypot

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'B题问_代码'))
sys.dont_write_bytecode = True

from q1_localization.localization_region import solve_localization_region
from q2_second_detection.second_detection_point import (
    sample_first_feasible_region, robust_receive_ratio, select_second_detection_point,
)
from q3_common.public.geometry import region_summary
from q3_common.public.models import Measurement, ActionSpec, RobotState
from q3_common.public.candidates import estimate_time
from q3_common.route_c.core import RouteCEnv, RouteCConfig
from q3_common.route_c.backtest import run_backtest

results = {}
results['q1_empty_misclassified'] = solve_localization_region(
    [(0, 1), (0, -1)], [1, -1]
)['status']

particles = sample_first_feasible_region((0, 0), 0)
results['q2_discrete_receive_not_continuous_guarantee'] = {
    'sample_receive_ratio': robust_receive_ratio((1100, 0), particles),
    'valid_true_target': [5.1, 0],
    'valid_reception_radius': 1000,
    'distance_from_second_point': 1094.9,
}
outside = sample_first_feasible_region((-2500, 0), 0)
results['q2_outside_disk_particles'] = {
    'outside_count': sum(hypot(*p.point) > 1800 + 1e-8 for p in outside),
    'total': len(outside),
}
small = sample_first_feasible_region((0, 0), 0, angle_count=3, range_count=3)
selection = select_second_detection_point((0, 0), 0, particles=small, candidates=[(0, 0)])
results['q2_infinite_solution_reports_ok'] = {
    'status': selection['status'], 'worst_diameter': str(selection['best']['worst_diameter']),
}

stations = [(-35.24933083584688, 2.400589704310894),
            (-98.30400010208645, 9.657155745444513),
            (64.4317012379502, 9.98039576400349)]
bearings = [-0.6061595771781894, -1.1047994366983005, -1.5017171251752286]
summary = region_summary([Measurement(s, 1, 'BEARING', b, 0) for s, b in zip(stations, bearings)])
results['q3_false_bounded_region'] = {
    'stations': stations, 'bearings': bearings,
    'q1_status': solve_localization_region(stations, bearings)['status'],
    'q3_summary': summary,
    'valid_target': [1000, 0],
    'target_distance_from_reported_center': hypot(1000-summary['center'][0], summary['center'][1]),
}

env = RouteCEnv(config=RouteCConfig(profile='mixed'))
env.reset(seed=10001)
first = env.scenario
same = []
for _ in range(10):
    env.reset()
    same.append(env.scenario == first)
results['q3_same_training_scene_on_reset'] = same

rows, _ = run_backtest([61001], RouteCConfig(target_count=None, max_steps=1))
results['q3_unknown_count_wrong_cleared_rate'] = rows
results['clear_estimated_seconds_at_same_point_other_channel'] = estimate_time(
    ActionSpec('audit', 'CLEAR', (0, 0), (2,)), RobotState((0, 0), 1)
)
text = json.dumps(results, ensure_ascii=False, indent=2)
Path(__file__).with_name('边界问题复现结果.json').write_text(text, encoding='utf-8')
print(text)
