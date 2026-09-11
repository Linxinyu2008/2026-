# 第四问：三角网格搜索与稳健定位代码实施规划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> 本轮只交付规划，不执行实现。后续实现可使用 executing-plans 在当前任务逐项完成；不自动启动子代理、不自动连接平台或推送仓库。

**Goal:** 在任意固定发射朝向下发现全部目标，并通过有限次定位尝试和光学覆盖清除形成有限步完成机制，再优化总虚拟耗时。

**Architecture:** 新增独立的 `B题问_代码/q4_directional` 包。复用前三问的协议客户端、观测数据结构和公开几何函数，第四问独立维护定向仿真、保守位置域、覆盖证据及控制状态；同一策略通过适配器运行于本地或官方接口。

**Tech Stack:** Python、标准库 unittest/dataclasses/math/json；复用现有 Python 几何计算，不引入训练依赖。先实现确定性基线，再做参数比较。

**Spec:** `建模过程/B题问题4_路线A_三角网格保证搜索与稳健定位.md`，并纳入本次评审修正：再捕获不等于严格收缩；有限次触发光学回退；逐覆盖点直接清除；几何近似必须保守。

## 全局约束与完成标准

- 目标位于原点为圆心、半径1800米的圆内，机器人允许到圆外；频道1—20，每频道至多一个源，总数10—16。
- 每源接收半径1000—1500米；定向接收要求距离满足且 `(station-source)·orientation >= 0`，半平面边界包含在内。
- 示向误差有界±1°、同位置固定；为兼容两位小数返回，规划默认几何角容差1.005°，这是保守计算参数，不是修改仿真中的原始误差范围。
- 接收覆盖内、距离不超过5米为NEAR；清除只要求目标距离不超过20米，不要求有无线电信号。
- 移动5米/秒，测量5秒，换频1秒，清除成功5秒、失败3秒；清除不改变测向机频道。
- 不用NONE排除某个位置圆，不由一次NONE推断目标类型或频道不存在。
- 本轮不创建第四问程序。未来实现先本地测试；未获后续授权不进入平台，不提交或推送。
- 不删除已有文件；若未来确需删除，先送回收站。
- 理想有效响应下的有限步保证与平台时间约束分别报告；预算耗尽只能标记未完成。

## 1. 目录与复用边界

以下均为待创建文件，本计划不创建这些程序：

```text
B题问_代码/q4_directional/
    __init__.py
    config.py               # 规则、算法参数及合法性检查
    models.py               # 频道档案、网格、位置域、动作、运行结果
    scenario.py             # 仅仿真端使用的源位置/朝向/误差场
    simulator.py            # 定向和全向源的本地观测及计时
    geometry.py             # 保守外包位置域、裁剪、覆盖半径
    triangular_grid.py      # 全局/局部三角单元、顶点编号、覆盖集
    local_policy.py         # 快速选点、再捕获、光学回退及退出条件
    controller.py           # 全局扫描进度、频道状态机、调度与停止证据
    adapters.py             # 本地/官方接口向统一观测对象转换
    run.py                  # 默认本地执行；官方执行必须显式选择
    backtest.py             # 固定场景、批量对比和统计输出
    README.md
    tests/
        __init__.py
        test_simulator.py
        test_geometry.py
        test_grid.py
        test_local_policy.py
        test_controller.py
        test_adapters.py
        test_end_to_end.py
```

可直接引用 `q3_common.public.models.Measurement/ClearResult/Point`、`q3_common.public.official_client.OfficialSimulatorClient`；接口异常不得伪装为NONE。几何模块可引用 `q1_localization.localization_region` 的公开 `build_halfplanes`、`minimum_enclosing_circle` 等函数，实现前核对签名和容差语义。

现有 `q3_common.public.geometry.region_summary` 不包含完整圆形约束，不能当作本方案完整位置域直接使用。Q3仿真源没有朝向字段，因此定向仿真独立实现；Q2的全向可靠接收判据不能作为Q4的保证条件。

## 2. 跨模块契约

所有坐标单位米、时间秒、角度度，二维点使用现有Point。

```python
class ChannelStatus(Enum):
    UNKNOWN = "unknown"
    FOUND = "found"
    TRACKING = "tracking"
    CLEARABLE = "clearable"
    CLEARED = "cleared"
    ABSENT = "absent"

class LocalMode(Enum):
    FAST = "fast"
    REACQUIRE = "reacquire"
    OPTICAL = "optical"

@dataclass(frozen=True)
class Action:
    kind: Literal["MEASURE", "CLEAR"]
    point: Point
    channel: int
    reason: str
    coverage_id: tuple[int, int] | None = None
```

`Region`存储有序凸多边形顶点（允许退化为线段或点）、状态OK/INCONSISTENT、覆盖圆心、保守半径、面积和直径。频道档案`Track`保存状态、正观测、全局NONE顶点编号、region、local_mode、局部累计动作数、连续NONE数、无进展次数、再捕获队列及光学队列索引。不得包含真实坐标、真实半径、朝向或真实源数。

`Grid`保存三角单元顶点编号、去重顶点坐标和扫描顺序。顶点以整数格点编号去重，不以浮点字符串去重。`RunResult`保存结束原因、已清除/证明不存在/未解决频道、成本分项、实际轨迹、动作数和现实耗时。

```python
# 所有签名均为待实现接口，不是本轮新增的运行代码。
def initial_region(radius_m: float, sides: int) -> Region: ...
def update_region(region: Region, measurement: Measurement,
                  angle_margin_deg: float, max_range_m: float) -> Region: ...
def grid_for_region(region: Region, spacing_m: float) -> Grid: ...
def optical_cover(region: Region, clear_radius_m: float,
                  margin_m: float) -> tuple[Point, ...]: ...
def next_local_action(track: Track, robot: RobotState, config: Config) -> Action: ...

class Backend(Protocol):
    def measure(self, point: Point, channel: int) -> Measurement: ...
    def clear(self, point: Point, channel: int) -> ClearResult: ...

class Controller:
    def next_action(self) -> Action | None: ...
    def accept(self, action: Action, result: Measurement | ClearResult) -> None: ...
    def result(self) -> RunResult: ...
```

接口中的RobotState沿用现有定义；Config在config.py，其他第四问类型在models.py。Backend只提供观测，Controller不得持有仿真Scenario。NONE观测只更新计数/覆盖记录，不裁剪Region。

## Task 1：先实现可核对的本地定向环境

**Files:** 新增config.py、models.py、scenario.py、simulator.py及tests/test_simulator.py；初始化包。

**输入/输出:** Scenario中的源使用channel、point、reception_radius_m、orientation_deg（None代表全向）；Simulator实现Backend，返回现有Measurement和ClearResult。

- [ ] 先写半平面内、外和边界测试，以及背面20米内清除测试；再运行确认新模块尚未实现导致失败。
- [ ] 实现距离和朝向联合判断，再判断NEAR。误差使用按源/坐标稳定生成的确定性场，不在每次测量时重新抽样；误差函数允许注入±1°的对抗场。
- [ ] 实现移动、测量、换频、成功/失败清除分别计数；非法坐标、频道和非有限数直接拒绝。
- [ ] 验证测试通过后保留该阶段变更，未经授权不推送。

核心断言示例（在测试内建立单源环境，接口层面不向控制器泄露真值）：

```python
sim = Simulator(Scenario.single(channel=1, point=(0., 0.),
                               radius_m=1000., orientation_deg=0.))
assert sim.measure((-10., 0.), 1).signal == "NONE"
assert sim.clear((-10., 0.), 1).success
```

需同步实现的测试工厂`Scenario.single`允许构造少于10源的单元测试场景；正式批量场景仍限制10—16源。另核对从频道2清除频道1后当前频道仍为2，且失败清除仅增加移动耗时和3秒。

验证命令：在`B题问_代码`运行 `python -m unittest q4_directional.tests.test_simulator -v`。

## Task 2：保守几何域，而不是粒子云代替保证

**Files:** 新增geometry.py、tests/test_geometry.py，补齐models.py的Region。

**输入/输出:** initial_region和update_region；后续模块只使用Region顶点和保守覆盖圆。

- [ ] 写目标必须保留、跨0°角度、单次观测、线段/点退化、矛盾观测测试，运行确认失败。
- [ ] 初始域使用半径1800米圆的外切正多边形。每个圆约束通过均匀法向量n的半平面 `n·(x-center) <= radius` 实现，默认256条；以初始外包盒逐面裁剪，不枚举所有半平面交点。
- [ ] BEARING加入角域及测站1500米外切多边形约束；NEAR加入测站5米外包圆并优先原地清除；NONE不增加位置约束。
- [ ] 用多边形顶点计算覆盖圆，再计算圆心到全部顶点的最大距离并添加数值余量。清除条件为该上界不超过19.75米，先保守留0.25米执行余量。
- [ ] 若裁剪为空，从完整正观测重建一次；仍为空则返回INCONSISTENT并停止该求解链报告异常，禁止丢弃不利观测后声称保证。

关键断言示例：

```python
region = initial_region(1800., 256)
obs = Measurement((0., 0.), 1, "BEARING", 1., 5.)
region = update_region(region, obs, 1.005, 1500.)
assert region.contains((1000., 0.))  # Region.contains(point, tol=1e-7)
assert region.status == "OK"
```

Region.contains按凸多边形/线段/点分别判断。对真实目标位于圆边界、示向误差恰±1°的组合逐项断言包含；随机测试补充但不替代理论证明。

验证：`python -m unittest q4_directional.tests.test_geometry -v`。

## Task 3：三角网格及可审计覆盖证据

**Files:** 新增triangular_grid.py、tests/test_grid.py。

**输入/输出:** grid_for_region输出Grid；optical_cover输出有限点列。

- [ ] 先测试跨目标域边界的单元仍保留圆外顶点、顶点去重及半平面发现性质。
- [ ] 格点取 `p(m,n)=(L*(m+n/2), sqrt(3)*L*n/2)`；每个格平行四边形分成两个等边三角形。由Region包围盒换算整数索引范围并各扩展一格。
- [ ] 使用保守的闭集三角形与凸域相交判定，边/点相切也保留；不确定的数值边界宁可多留。全局对目标圆的外包Region生成网格，只会增加少量点，不损失覆盖。
- [ ] 保留所选单元全部顶点，按行蛇形遍历。全局网格生成后固定；恢复扫描不能改变顶点编号或丢掉已完成证据。
- [ ] optical_cover复用相交单元的全部顶点，默认边长30米，满足 `30/sqrt(3) < 19.75`。光学覆盖点不需要满足发射方向。

测试中的几何性质：

```python
for source in [(0., 0.), (1800., 0.), (-1800., 0.), (0., 1800.)]:
    for angle in range(0, 360):
        u = (cos(radians(angle)), sin(radians(angle)))
        assert any(dist(p, source) <= 1000. + 1e-7 and
                   sum((p[k] - source[k])*u[k] for k in range(2)) >= -1e-7
                   for p in grid_for_region(initial_region(1800., 256), 950.).points)
```

上述Grid.points为顶点坐标元组；测试中从math导入cos/sin/radians/dist。另构造一个相交三角单元的重心，检查光学点列中存在20米内点，并测试退化Region。

验证：`python -m unittest q4_directional.tests.test_grid -v`。

## Task 4：局部策略必须有不可重置的退出上限

**Files:** 新增local_policy.py、tests/test_local_policy.py。

**输入/输出:** next_local_action返回MEASURE或CLEAR；Track保存全部进度，观测处理由Controller.accept完成。

- [ ] 先写“所有新增测量无信息仍能进入光学模式”和“NONE后仍执行光学CLEAR”测试。
- [ ] FAST候选取覆盖圆心、位置域顶点及其外扩点；去重并避免已测点。按可行域顶点所代表位置的最小测向夹角改善排序，除以预计移动与测量成本；此评分只是效率启发，不构成接收保证。
- [ ] 连续2次NONE进入REACQUIRE；局部三角边长取 `min(950, max(30, 0.4*D))`，D为当前保守域直径，全部仍满足不超过1000米。候选为空直接转入REACQUIRE。
- [ ] 单频道累计局部MEASURE最多8次，或连续4次测量后覆盖半径未比上次有效进展基准缩小5%，即锁定OPTICAL。累计上限不因收到新信号、任务切换、再捕获成功而清零；本地消融中12次与8次结果相同。
- [ ] OPTICAL开始时冻结当时有效Region及其覆盖点列；只按队列执行CLEAR，失败推进索引，不重建队列，不回到FAST。遍历结束仍未清除则报告MODEL_OR_PROTOCOL_ERROR。
- [ ] 任意时刻NEAR优先原地CLEAR；覆盖半径达阈值优先覆盖圆心CLEAR。被保证的CLEAR若失败，不继续当作几何正确，记录异常并停止该链。

核心断言目标：

```python
# make_found_track由该测试文件构造一条有效BEARING及初始位置域。
track = make_found_track()
track.local_measure_count = 12
action = next_local_action(track, RobotState(), Config())
assert track.local_mode == LocalMode.OPTICAL
assert action.kind == "CLEAR"
```

Config必须校验global_spacing_m<=1000、光学边长的覆盖条件以及所有动作上限为正整数；测试里验证超界配置被拒绝。

验证：`python -m unittest q4_directional.tests.test_local_policy -v`。

## Task 5：先用简单调度跑通完成证明

**Files:** 新增controller.py、tests/test_controller.py。

**输入/输出:** Controller接收Config和初始RobotState，按next_action/accept串行推进；不接收Scenario。

- [ ] 先测试中途发现目标后能够恢复未完成扫描、FOUND永不变ABSENT、预算中止不算完成。
- [ ] 基线按蛇形顶点扫描未知频道；同点优先当前频道后再按编号扫描，减少可避免的换频。首次正观测立即处理该源至清除，再返回保存的扫描游标；该版本不加入复杂任务评分。
- [ ] 仅有效NONE响应可登记对应顶点证据。频道从未正观测、且固定全局顶点全部获得NONE后才能ABSENT；FOUND但失联仍保持待解决。
- [ ] 只有已成功清除16个不同频道，或者全部20频道为CLEARED/ABSENT才能完成。若后者清除数少于10，报告规则/覆盖异常而非成功。
- [ ] 执行每个动作都更新实际位置；只有MEASURE更新当前接收频道。记录局部绕行及返回路程，保证成本按实际动作累加。

关键断言：

```python
assert not track.can_mark_absent(all_grid_ids)  # 该频道已有正观测
assert result.stop_reason != "COMPLETE"        # 预算耗尽的测试场景
```

`Track.can_mark_absent(all_grid_ids)`严格检查未曾正观测与NONE集合覆盖；Controller.result返回上述RunResult。端到端另用恰10源、恰16源和20频道中空频道穿插的场景验证终止分支。

验证：`python -m unittest q4_directional.tests.test_controller -v`。

## Task 6：接入适配器，但测试不访问平台

**Files:** 新增adapters.py、run.py、tests/test_adapters.py。

**输入/输出:** LocalBackend包装Simulator；OfficialBackend包装现有OfficialSimulatorClient。两者实现同一Backend接口。

- [ ] 先写本地与伪官方响应归一化一致、请求失败不记NONE、clear不改频道测试。
- [ ] 对照附件字段及已有Q3官方控制器映射BEARING/NEAR/NONE和清除结果，不猜测键名。官方请求沿用客户端同request_id重试，策略在结果不确定时不重复推进队列。
- [ ] run默认local，显式`--backend official`才构造官方客户端并enter。规划阶段及本地验证绝不调用这一分支。
- [ ] 现实预算使用单调时钟，正常退出留出收尾余量；虚拟预算和异常分别记录。客户端管理enter/exit，策略不生成平台加密日志。

验收断言示例：

```python
with patch.object(OfficialSimulatorClient, "enter") as enter:
    main(["--backend", "local", "--seed", "92001"])
    enter.assert_not_called()
```

这里main在run.py，接受argv列表；测试从unittest.mock导入patch。伪官方响应必须根据附件样例建立fixture，不凭空填写协议结构。

验证：`python -m unittest q4_directional.tests.test_adapters -v`。

## Task 7：本地验收后才优化效率

**Files:** 新增backtest.py、tests/test_end_to_end.py、README.md；实现完成后再更新代码目录README的入口说明。输出放`B题问_代码/outputs/q4_directional/<run_id>/`。

- [ ] 先固定边界场景：源在圆边/三角边/格点，接收半径1000，朝向使两顶点背向，误差±1°，多次重复观测无收缩，20米内背面清除，全部定向及全向/定向混合。
- [ ] 批量场景用同一组种子和真值比较配置；策略始终只看Backend返回，真值仅供仿真和运行结束后的评分。
- [ ] 首先完成全局950米、光学30米、局部12次上限的确定性基线；然后分别比较全局800/900/950/1000米、局部上限4/8/12，而不是同时更换全部机制。
- [ ] 基线通过后才考虑2-opt、局部任务插入排序和更精细候选评分；每次只改变一个机制并报告最坏场景。
- [ ] 输出summary.json、按场景results.csv和actions.jsonl：完成率、遗漏数、总虚拟时间、每个成功清除目标的平均时间、移动距离、测量/换频/清除成功失败次数、光学回退次数、最大单频道动作数、现实耗时及停止原因。
- [ ] 运行第四问测试和既有前三问回归，检查没有改变前三问行为。报告仅为本地规则验证，不称为平台测试通过。

成本一致性断言：

```python
expected = (result.move_distance_m / 5 + result.measure_count * 5
            + result.switch_count + result.clear_success_count * 5
            + result.clear_failure_count * 3)
assert abs(result.virtual_time_s - expected) < 1e-6
```

上述分项作为RunResult明确字段实现。完成场景必须核对真实源全部清除，不能只用控制器自己的COMPLETE标记当作正确性证据。

验证（工作目录为`B题问_代码`）：

```powershell
python -m unittest discover -s q4_directional/tests -v
python -m unittest discover -s q3_common/tests_q3 -v
python -m unittest q1_localization.test_localization_region q2_second_detection.test_second_detection_point -v
python -m q4_directional.backtest --seeds 92001:92020 --output outputs/q4_directional/baseline
```

backtest的seeds参数约定为闭区间。运行前选择已安装项目依赖的Python环境；本计划没有执行这些命令。

## 自查与实施优先级

原思路中的全局发现、边界网格、状态证据、保守定位域、局部再捕获、光学清除、调度、计时、接口复用及实验比较分别对应Task 1—7。最重要的验收不是某次运行快，而是：真实源不被位置域排除；ABSENT具备完整证据；局部预算不能反复重置；光学失败后队列必向前；总成本与实际动作一致。

先完成Task 1—5形成可在本地运行的数学闭合基线，再完成Task 6的伪接口验证与Task 7的批量比较。尚不能预先承诺最优耗时或平台时限内完成，必须以实际本地结果和后续获授权的平台结果分别判断。
