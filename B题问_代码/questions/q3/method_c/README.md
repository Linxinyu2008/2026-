# 路线C

路线C暂不单独复制模拟器。它复用公共层，并提供特征编码、Gymnasium环境、动作掩码、训练和评估入口。

PPO只能选择公共候选动作，不能读取目标真值，也不负责替代几何清除保证。

统一实施计划：[路线C代码实施计划](../../../建模过程/问题3路线/路线C/B题问题3_路线C_代码实施计划.md)。数学方案和代码计划集中在该目录维护，此处仅保留入口。

实施顺序是：公共执行与证据核验 → 可行域和空间误差场 → 候选与757维观测 → 仿真回放和回测 → PPO训练 → 多种子验证及独立测试 → 冻结推理包。

当前已完成第一步的代码骨架：`core.py` 提供独立的 `RouteCEnv.reset/step/action_masks/report` 契约。它只调用 `questions/q3/public`，不调用 `questions/q3/route_b`；当前返回的是可检查的 Python 公开观察，后续 `features.py` 再将它编码为固定维度的数值向量。

`features.py` 已完成757维编码和schema校验，观测中的可行域中心、面积和半径来自公共几何层；它不会把检测点冒充目标中心。

`env.py` 已将核心环境接成 `GymRouteCEnv`：观察空间为 `Box(757,)`，动作空间为 `Discrete(12)`，动作掩码通过 `action_masks()` 提供。当前验收使用随机合法动作回放，还没有启动PPO训练。

`train.py` 提供 CPU 版 `MaskablePPO` 短训练入口。示例：

```powershell
python -m questions.q3.method_c.train --steps 10000 --seed 10001
```

训练输出包含 `model.zip`、`metadata.json` 和 TensorBoard 日志；训练完成不等于策略已经有效，必须经过独立回测。

## 多策略回测

在 PyCharm 项目目录中运行：

```powershell
conda run -n data_env python -m questions.q3.method_c.backtest --episodes 20 --targets 20
```

脚本会比较 `random`、`fixed_scan`、`active` 三种公开策略；指定 `--model model.zip` 后，会追加 PPO 回放。结果保存为 `episodes.csv` 和 `summary.json`，用于比较清除率、虚拟时间、决策步数和频道切换次数。

## 主控制器

实际运行优先使用混合训练 PPO，模型加载失败或 PPO 输出非法动作时自动回退到固定扫描：

```powershell
conda run -n data_env python -m questions.q3.method_c.controller --model outputs/route_c/20260911_031706/model.zip --seed 30001 --targets 16 --profile uniform
```

如需直接验证回退链路：

```powershell
conda run -n data_env python -m questions.q3.method_c.controller --mode fixed_scan --seed 30001 --targets 16 --profile uniform
```
