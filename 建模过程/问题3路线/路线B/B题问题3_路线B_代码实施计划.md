# 路线B代码实施计划：从本地规则模拟到主动搜索

> 状态：核心模块已实施并完成本地回测；官方接口和部分增强几何仍需演练核验。本文的代码块保留接口约定和验收标准，当前统一流程请以[问题3统一建模与代码流程](../问题3统一建模与代码流程.md)为准。

**目标：**交付一套不依赖深度学习、具有独立入口的路线B程序，完成模拟、搜索、定位、清除、结束判断与实验统计。

**架构：**公共模块负责规则和观测处理，route_b负责人工动作评分及入口。路线C以后可以导入公共模块，但运行B不需要安装torch，也不需要任何模型文件。

**技术栈：**Python、numpy、shapely、requests；测试优先标准库unittest，出图再安装matplotlib。具体依赖版本实施时锁定。

**方案依据：**[路线B优化方案](B题问题3_路线B_概率置信区域与主动搜索.md)。本计划取代上一份合并规划中的单目录组织建议，采用公共模块＋两套独立入口。

## 1. 最终目录与职责

以下目录均位于工作区的“B题问_代码”中。原有第一、二问文件保留，不移动、不复制整套代码。

~~~text
B题问_代码/
  localization_region.py             现有第一问，作为参考和适配来源
  second_detection_point.py          现有第二问，作为局部选点来源
  q3_common/
    __init__.py
    models.py                        公共数据结构
    config.py                        规则与算法参数
    scenario.py                      隐藏场景与固定误差场
    simulator.py                     本地测量与计时
    geometry.py                      有界误差外包区域
    belief.py                        20频道历史与状态
    coverage.py                      七点覆盖任务和证据
    localizer.py                     单频道下一测点
    candidates.py                    有序候选动作及收益摘要
    session.py                       公共单局状态机和执行器
    metrics.py                       指标与日志
    official_client.py               拿到附件协议后实现
  route_b/
    __init__.py
    policy.py                        人工评分选择
    run.py                           单局独立入口
    batch.py                         批量独立入口
  tests_q3/
    __init__.py
    test_simulator.py
    test_geometry.py
    test_belief.py
    test_coverage.py
    test_candidates.py
    test_session.py
    test_route_b.py
  configs/
    route_b.json
    local_profiles.json
  outputs/route_b/
~~~

初期不要一次创建所有空文件。每个Step增加当轮闭环需要的文件，避免看似完整却不可运行的工程。

## 2. 先冻结内部接口

所有名称是我们自己的Python接口，不是官方API地址。统一米、秒、度；数组内部频道索引0—19，对外频道号1—20，转换只在边界完成。

### 2.1 核心动作与观察

models.py先定义如下基础结构，后续模块直接导入，不各自重新命名。

~~~python
from dataclasses import dataclass
from typing import Literal

Point = tuple[float, float]
Kind = Literal["SCAN", "LOCALIZE", "CLEAR"]
Signal = Literal["NONE", "BEARING", "NEAR"]
Status = Literal["UNKNOWN", "TRACKING", "CLEARABLE", "CLEARED", "ABSENT"]

@dataclass(frozen=True)
class ActionSpec:
    action_id: str
    kind: Kind
    point: Point
    channels: tuple[int, ...]
    coverage_id: int | None = None

@dataclass(frozen=True)
class Measurement:
    point: Point
    channel: int
    signal: Signal
    bearing_deg: float | None
    virtual_time_s: float

@dataclass(frozen=True)
class ClearResult:
    point: Point
    channel: int
    success: bool
    virtual_time_s: float
~~~

规则：channels非空且互异，LOCALIZE/CLEAR必须长度1；action_id按kind、位置和频道稳定生成。BEARING才有角度，NONE/NEAR的bearing_deg为None。通信失败另用异常或错误结果表示，禁止伪造Measurement(signal="NONE")。

覆盖扫描只有确实在对应覆盖点完成有效检测，才由执行器把coverage_id与该Measurement关联交给belief。后端本身不负责判断覆盖证据。

### 2.2 后端与单局接口

| 对象/方法 | 接收 | 返回或副作用 |
|---|---|---|
| LocalSimulator(scenario, rules) | 固定隐藏场景与规则配置 | 初始化原点、频道1、时间0 |
| backend.detect_at(point, channel) | 检测点、频道 | Measurement；累加移动/换频/检测时间 |
| backend.clear_at(point, channel) | 清除点、频道 | ClearResult；按已确认规则计费 |
| backend.virtual_time_s | 无 | 当前虚拟时间，只读 |
| EpisodeSession(backend, rules) | 统一后端 | 创建20频道公开记录 |
| session.can_finish() | 无 | 基于公开证据的bool |
| session.build_candidates() | 无 | 候选列表，顺序稳定 |
| session.execute(action) | ActionSpec | StepResult，更新公开历史与覆盖游标 |
| session.snapshot() | 无 | AgentSnapshot，策略可见摘要 |
| session.finish(reason) | 结束原因 | EpisodeReport并关闭后端会话 |

AgentSnapshot包含position、current_channel、virtual_time_s、remaining_budget_ratio、stagnation_ratio、tracks。tracks按频道1—20排序；每条含status、center或None、cover_radius_m、area_m2、unsearched_ratio、7位coverage_checked和测量历史。

StepResult包含delta_virtual_s、new_found、new_cleared、events、finished、failure_reason。events为本步Measurement/ClearResult序列；每个事件只能计入一次。EpisodeReport含步骤数、终止原因、时间明细、发现/清除数；真实总数由评估器在结束后补充。

Candidates中的每条记录包含action、estimated_time_s、search_gain、localization_gain、guaranteed_clear、valid。数学几何对象只在公共状态内部保存，快照不暴露隐藏目标。

## Step B1：规则、固定场景和准确计时

**新增：**models.py、config.py、scenario.py、simulator.py、test_simulator.py。

先写一个固定场景，不急着让机器狗自主决策。config中的题目常量与算法调参分开；失败清除成本和清除换频行为是协议待核验项。可供本地实验显式传入一个假设计费策略，并在结果标注；未知时遇到失败分支应抛出UnverifiedRuleError，不默默按成功5秒计算。

scenario.py定义Source(channel, point, reception_radius_m)、Scenario(sources, error_field)，只由模拟器和测试/评估器持有。测试工厂make_fixed_scenario(sources, error_deg=0.0)使用固定角误差；随机生成器下一步再写。

实现detect_at顺序：检查输入→累加直线移动并更新位置→如需要换频则计1秒→检测计5秒→按频道存在与否、距离、5米阈值返回观察。clear_at仅在确认的成功规则下累计相应移动与5秒操作；状态更新不能清除另一个频道。

首先编写下面的行为测试，再实现对应逻辑：

~~~python
def test_known_success_time(self):
    scene = make_fixed_scenario(
        [Source(1, (100.0, 0.0), 1000.0)], error_deg=0.0
    )
    sim = LocalSimulator(scene, Rules())
    obs = sim.detect_at((0.0, 0.0), 1)
    self.assertEqual(obs.signal, "BEARING")
    self.assertAlmostEqual(obs.bearing_deg, 0.0)
    result = sim.clear_at((80.0, 0.0), 1)
    self.assertTrue(result.success)
    self.assertAlmostEqual(sim.virtual_time_s, 26.0)
~~~

另外验收：同地点两次角度相同、两次检测累计10秒；切换空频道新增6秒；距离恰为5、20、1000时分别命中相应边界；清除后再次检测该频道为NONE；坐标NaN和频道21显式拒绝。

- [ ] 写固定场景与上述测试，确认尚未实现时失败。
- [ ] 实现观察和成功计时，不扩展未核实官方字段。
- [ ] 运行：python -m unittest discover -s tests_q3 -p test_simulator.py -v。
- [ ] 输出一条固定动作轨迹，逐项对账26秒，而非只看最终结果。

**完成后得到：**一个可以接收手工动作的本地二维环境。此时尚无自动搜索算法。

## Step B2：可复现随机场景与误差场

**新增/扩充：**scenario.py、configs/local_profiles.json、test_simulator.py。

接口为generate_scenario(seed: int, profile: str) -> Scenario。常规profile取uniform，压力profile取edge、clustered、min_radius；不同profile有独立参数与元数据。

随机流按场景种子派生独立的目标数、频道、位置、半径和误差场子种子，避免添加一个随机调用就改变全部场景。圆域采样用r=1800*sqrt(U)，角度均匀。每局半径固定。

误差场第一版采用节点在[-1,1]的固定网格及双线性插值，覆盖算法实际候选域。可将节点间距200 m作为起始实验假设，再比较50/200/500 m；固定偏置场另外测试。越界查询明确处理，不能随机补一个误差。使用外扩节点以包含边界。

~~~python
def test_error_is_a_fixed_field(self):
    scene = generate_scenario(seed=42, profile="uniform")
    e1 = scene.error_field.value((123.0, 456.0), channel=1)
    e2 = scene.error_field.value((123.0, 456.0), channel=1)
    self.assertEqual(e1, e2)
    self.assertLessEqual(abs(e1), 1.0)
~~~

- [ ] 测试同seed得到相同目标和误差；不同seed不要求每个字段都不同，但场景应可变化。
- [ ] 检查10—16个目标、频道互异、目标在圆内、半径界内。
- [ ] 增加圆域分布诊断：大样本下r²/R²的经验均值应接近0.5；只作采样诊断，容差和样本量固定。

**完成后得到：**批量数据来源。生成场景不是训练网络，也不必把所有场景保存成大文件。

## Step B3：适配第一问几何，先把单目标定位做稳

**新增：**geometry.py、localizer.py、test_geometry.py。

接口：initial_region(rules)产生初始外包域；update_region(region, measurement, rules)产生更新域；summarize_region(region)返回RegionSummary(status, center, cover_radius_m, area_m2, diameter_m)。

实施顺序是相切多边形外包初始圆→BEARING半平面裁剪→外包1500 m接收圆裁剪→求凸包和面积→计算覆盖上界。首版阴性记录到belief但不从凸定位多边形挖孔，避免一开始引入多连通复杂度；这只是保守松弛，不能用阴性忽略来声称信息已充分利用。

复用localization_region.build_halfplanes处理角度。现有solve_localization_region没有目标圆/距离约束适配入口，不能直接原样调用后认为已经包含所有约束。minimum_enclosing_circle先对少量顶点参考计算，大顶点先用包围盒中心及最大顶点距离得到安全上界。

圆外包边数根据R*(sec(pi/m)-1)控制外扩量。第一轮可用m=32作粗区域；接近清除时令容差不超过0.1 m并重新用历史约束构造区域。外包误差会保守增大覆盖半径，不能在事后未经证明减去误差。

~~~python
def test_region_keeps_target_across_zero(self):
    region = initial_region(Rules())
    obs = Measurement((0.0, 0.0), 1, "BEARING", 359.8, 5.0)
    region = update_region(region, obs, Rules())
    self.assertTrue(region.covers(PointGeometry(1000.0, 0.0)))
~~~

此处PointGeometry为测试导入的shapely.geometry.Point别名。另测近共线、圆边界、点/线退化、故意矛盾观察；矛盾不能被随机丢弃后继续声称保证定位。

localizer.choose_measurement(track, robot, rules)先适配第二问候选与接收筛选，再比较移动代价。相同点的同频道重测不计新信息。若无候选，产生可诊断停滞事件交给保守策略，不能输出NaN。

- [ ] 先通过固定几何边界测试。
- [ ] 单目标程序只用观察驱动，测试侧每步检验真实目标包含于外包域。
- [ ] 固定100个诊断场景，保存检测次数、覆盖半径变化与失败原因。

**完成后得到：**从第一次示向度开始自动靠近并清除单个源的模块。100局成功仅为实测结果，不是全场景保证。

## Step B4：20频道状态与七点覆盖证据

**新增：**belief.py、coverage.py、test_belief.py、test_coverage.py。

coverage_points()固定输出7个Point；BeliefTracker初始化20个UNKNOWN。observe(measurement, coverage_id=None)更新频道；record_clear(result)仅在成功时标CLEARED；can_finish()遵守方案结束逻辑。

每频道7位记录只能在对应点确认NONE时置位。TRACKING频道不会因为一些阴性就变ABSENT。固定覆盖任务被定位打断后保持游标，重新规划只更新仍需检测的频道集合。

~~~python
def test_missing_channel_needs_every_cover_point(self):
    belief = BeliefTracker(Rules())
    pts = coverage_points()
    for j, point in enumerate(pts[:6]):
        belief.observe(Measurement(point, 20, "NONE", None, 5.0*(j+1)), j)
    self.assertEqual(belief.tracks[19].status, "UNKNOWN")
    belief.observe(Measurement(pts[6], 20, "NONE", None, 35.0), 6)
    self.assertEqual(belief.tracks[19].status, "ABSENT")
~~~

本测试只检验频道排除，不表示全局完成。其他测试包含：清除10个仍有UNKNOWN不得结束；16个不同频道清除可以结束；清除计数不重复；非覆盖点NONE不凭空增加七点记录；通信异常不记阴性。

覆盖证明写入模块说明，数值采样仅用于检查坐标生成和实现错误，不以有限点抽样代替证明。

**完成后得到：**“搜到几个”之外，还能判断“哪些频道已经排除”的系统。

## Step B5：公共执行器与固定策略完整闭环

**新增：**session.py、metrics.py、test_session.py、route_b/run.py。

先不写主动评分。run入口选择fixed策略：七点覆盖＋发现即定位。session.execute负责逐次扫描更新、记录NEAR优先清除、恢复剩余扫描、计时和停滞计数。计划被打断的动作保留未完成频道，不能将它们误记成已测。

控制器只看AgentSnapshot和BeliefTracker，不直接访问Scenario。正常完成、时间失败、几何矛盾、后端故障和开发步数截断使用不同结束原因。进入官方模式时由单调时钟管理实际预算；本地开发另设最大动作数防止无限循环。

~~~python
while not session.can_finish():
    action = fixed_selector.choose(session)
    result = session.execute(action)
    if result.failure_reason is not None:
        break
report = session.finish(
    "completed" if session.can_finish() else "incomplete"
)
~~~

上段展示调用结构；实际入口应保留具体failure_reason，不能全部压成incomplete而丢诊断。

- [ ] 测试一次SCAN多个频道的逐项时间与事件次数。
- [ ] 测试NEAR插入清除后扫描游标可恢复。
- [ ] 测试10与16目标、边缘目标、小半径及空频道排除。
- [ ] 首次生成单局JSON和轨迹，不优化平均时间。

**完成后得到：**可独立运行的路线B基础版，此阶段即可开始协议齐备后的官方演练对接。

## Step B6：有限候选动作与路线B人工评分

**新增：**candidates.py、route_b/policy.py、configs/route_b.json、test_candidates.py、test_route_b.py。

build_candidates(snapshot, tracker, rules)输出Candidate记录；estimate_time(action, robot, rules)计算完整宏动作时间。任何动作收益只计算它实际检测的频道；同频道同位置无新增信息的动作排除。

初始候选配额4个搜索、4个定位、3个清除、1个兜底，共12，与C后续公平对比一致。按稳定键排序，去掉相同动作；不足留空槽，B跳过无效候选，C使用掩码。频道选择使用轮转/未处理时间，避免只关注低编号频道。

policy.choose(candidates, weights)返回有效候选索引。首版评分按B方案归一化收益/成本公式，不做多层未来模拟。固定评分相同则优先预计耗时更小、再按action_id排序。

~~~python
def test_scan_cost_counts_every_channel(self):
    action = ActionSpec("scan-example", "SCAN", (0.0, 0.0), (1, 3, 5))
    robot = RobotState((0.0, 0.0), current_channel=1)
    self.assertAlmostEqual(estimate_time(action, robot, Rules()), 17.0)
~~~

RobotState定义在models.py，包含position和current_channel。该案例15秒检测＋2秒换频。另测当前频道5且扫描(5,1,3)仍17秒；扫描(1,3,5)则18秒。若控制器重新排序，测试应针对重排后的实际ActionSpec。

- [ ] 固定案例检查评分不读真值，候选点合法。
- [ ] 批量测量每步候选生成和几何计算耗时，记录P50/P95。
- [ ] 同seed比较fixed与active，保存每局配对差值。

**完成后得到：**优化方案中的主动路线B，而不是只会固定扫描的基线。

## Step B7：批量实验、调参与结果文件

**新增：**route_b/batch.py，扩充metrics.py。

固定种子清单分为调试、验证、最终留出。建议先100局诊断，再按计算预算扩大；目标分布与误差场整体划分，不让同一地图只换误差后进入另一集合。

每局CSV至少包含seed、profile、policy、config_hash、n_total、n_found、n_cleared、all_cleared、virtual_time_s、avg_clear_time_s、wall_time_s、move_distance_m、detect_count、switch_count、clear_attempts、fallback_steps、termination_reason。

all_cleared由结束后评估器核对真值；控制器的完成证据另记certified_finish，两者不一致必须报警。平均时间分母0记空值，汇总保留失败数与失败原因，不能只导出成功局。

建议输出：
~~~text
outputs/route_b/<run_id>/
  config.json
  seeds.json
  episodes.csv
  summary.json
  failures/
  trajectories/
~~~

未来命令（从B题问_代码目录执行）：
~~~powershell
python -m route_b.run --backend local --policy fixed --seed 42
python -m route_b.run --backend local --policy active --seed 42
python -m route_b.batch --policy active --seed-start 1000 --episodes 100
python -m unittest discover -s tests_q3 -v
~~~

命令与参数是本计划要求实现的CLI，不是目前已经可用的命令。配置权重只在验证集选取，留出集只用于最终评价。

## Step B8：官方客户端与正式运行准备

**新增：**official_client.py；run.py增加official后端。

先读取附件1/2并建立逐字段映射表，确认坐标如何提交、检测与清除响应、near编码、失败清除耗时、清除换频语义、虚拟时间、会话及剩余预算。没有协议时，本步骤依赖未满足，其余本地步骤照常推进。

使用与LocalSimulator相同detect_at/clear_at接口。官方返回时间与本地预计差值出现偏差时记录原始响应，定位原因，不能改造官方日志伪装一致。

客户端设置请求超时与实际截止预算；清除等可能产生副作用的请求超时，按协议查询会话状态或终止诊断，不自动盲重试。读操作与写操作重试分别管理。

- [ ] 在演练模式完成固定动作核账，再跑完整B。
- [ ] 检查客户端没有读取不可用目标真值。
- [ ] 将本地仿真结果与官方演练统计分别保存。
- [ ] 正式测试前冻结依赖、配置和版本；正式运行由后续明确操作启动。

## 3. 难度、验收门槛和实际下一步

最难是B3的保守几何与B4/B5的状态一致性；B6性能次之；B1计时和B8协议错误会让所有结果失真，因此不能跳过。不要一开始微调大量评分权重，也不要一开始实现完整贝叶斯后验。

下一轮只实施B1：创建四个基础模块，手工输入一个目标，得到26秒固定成功轨迹并通过边界测试。通过后再做B2随机场景和B3单目标闭环。路线B可用后，将公共核心交给路线C训练计划。

本轮仅生成计划，没有运行上述测试，也没有声称任何清除率或耗时改善。
