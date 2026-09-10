# Part 1/2/3 Compliance and Backtest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (recommended) or superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐第一、第二、第三部分中可以由本地代码验证的题目规则，修正公共仿真器的 `/clear` 计时与频道语义，加入统一回测与实现说明，并明确真实模拟器接口仍需单独演练。

**Architecture:** 第一问和第二问继续保持独立数学模块；第三问继续由 `public` 公共仿真规则、`route_b`、`route_c` 和统一测试组成。新增的合规检查和回测只读取公开接口，不让路线 C 调用路线 B 内部实现。

**Tech Stack:** Python 3.13、标准库、NumPy、Gymnasium、Stable-Baselines3、sb3-contrib、unittest、Conda `data_env`。

**Spec:** `E:/xwechat_files/wxid_7fku0nd1iore22_5534/msg/file/2026-09/附件1.docx` and `E:/xwechat_files/wxid_7fku0nd1iore22_5534/msg/file/2026-09/附件2.docx`.

## Global Constraints

- 目标数量必须位于 10–16。
- 目标区域半径为 1800 米，机器狗速度为 5 米/秒。
- `/measure` 检测耗时为 5 秒，频道切换耗时为 1 秒。
- `/clear` 不改变测向机频道；成功耗时 5 秒，未发现目标耗时 3 秒。
- 真实接口要求 `/enter`、`/measure`、`/clear`、`/exit` 串行调用，并使用唯一 `request_id`。
- 本地回测不能替代真实模拟器演练，README 必须明确这一点。

### Task 1: 修正公共模拟器规则

**Files:**
- Modify: `B题问_代码/q3_common/public/simulator.py`
- Test: `B题问_代码/q3_common/tests_q3/test_simulator.py`

**Interfaces:** `LocalSimulator.clear_at(point, channel)` 保持签名不变，改为不切换频道并按成功与失败使用不同耗时。

- [ ] 添加清除失败耗时和频道保持的回归测试。
- [ ] 修改 `clear_at`，成功增加 5 秒，失败增加 3 秒，不调用频道切换。
- [ ] 在 `data_env` 中运行公共模拟器测试。

### Task 2: 增加第一、第二部分可复现回测入口

**Files:**
- Create: `B题问_代码/q1_localization/backtest.py`
- Create: `B题问_代码/q2_second_detection/backtest.py`
- Modify: `B题问_代码/q1_localization/README.md`
- Modify: `B题问_代码/q2_second_detection/README.md`

**Interfaces:** 两个入口都输出 JSON 统计和可复现的随机种子结果，不改变原有求解函数签名。

- [ ] 第一问回测生成多组可行角域，检查区域状态、凸性和最小覆盖圆覆盖性。
- [ ] 第二问回测生成第一次观测粒子和候选网格，检查接收覆盖约束和最坏直径有限性。
- [ ] 为两个入口补充运行说明。

### Task 3: 增加三部分统一回测和合规说明

**Files:**
- Create: `B题问_代码/part123_backtest.py`
- Create: `B题问_代码/README_PART123_COMPLIANCE.md`

**Interfaces:** 统一入口运行第一问、第二问、第三问本地回测，输出 JSON/CSV；README 标明已实现、部分实现和必须真实演练的要求。

- [ ] 串联三个模块的本地回测指标。
- [ ] 记录第三问 PPO、固定扫描和回退结果。
- [ ] 运行全部 unittest 与统一回测。

### Task 4: 同步到 PyCharm 项目

**Files:**
- Sync changed files to `E:/PythonProject1/B题问_代码`.

- [ ] 使用 `data_env` 运行测试和回测。
- [ ] 检查输出文件和 README 路径。
