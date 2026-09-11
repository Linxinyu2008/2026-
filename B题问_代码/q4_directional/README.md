# 问题4：定向源三角网格保证搜索

本目录是第四问的独立实现，采用“全局三角网格保证发现—保守位置域—有限局部回退—光学覆盖清除”路线。它复用 `q3_common.public` 中的协议数据结构思想，但不直接复制第三问策略。

当前已实现并在本地测试的基础组件：

- `simulator.py`：定向/全向源观测、NEAR、清除和虚拟计时；
- `geometry.py`：圆约束外包多边形、示向扇区裁剪和保守可行域；
- `triangular_grid.py`：相交三角单元、全部顶点保留和光学覆盖点；
- 全局扫描默认使用从 `(0,0)` 出发的最近邻加有限 2-opt 访问顺序。它只重排同一组三角网格点，不减少覆盖点，因此保持覆盖保证，同时减少机器狗的全局移动距离；需要对照最近邻或旧蛇形路线时可使用 `--global-route nearest` 或 `--global-route snake`。
- `local_policy.py`：局部测量预算、无进展计数和固定光学清除队列。
- `controller.py`：全局网格扫描、频道证据、局部任务调度和停止条件；
- `adapters.py`：本地模拟器与官方协议的统一后端；
- 官方演练输出同时生成完整 `*.commands.jsonl` 行为日志，记录每个请求的路径、唯一 `request_id`、参数、响应和重试信息，满足附件2的自记录要求；
- `run.py`：本地运行入口，默认不连接平台；
- `backtest.py`：本地种子批量回放和 CSV 输出。

尚未接入正式平台。后续实现顺序见仓库外的实施计划：
`docs/superpowers/plans/2026-09-11-q4-triangular-search.md`。

在 `B题问_代码` 目录下运行本地组件测试：

```powershell
python -m unittest discover -s q4_directional/tests -v
```

仿真器中的源位置、朝向和误差只属于测试真值，策略模块不读取它们。

本地运行示例：

```powershell
python -m q4_directional.run --backend local --seed 0 --output outputs/q4_directional/demo.json
python -m q4_directional.backtest --seeds 0:4 --output outputs/q4_directional/baseline.csv
python -m q4_directional.backtest --seeds 0:19 --global-route nearest --output outputs/q4_directional/nearest_after_opt.csv
```

官方后端已完成字段适配，但只有显式指定 `--backend official --robot-id ...` 才会调用 `/enter`；在平台测试前不应使用该参数。
