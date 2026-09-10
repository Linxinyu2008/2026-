# 路线B

路线B是问题3的第一条可运行实现，先完成确定性正确性，再加入主动评分。

推荐文件顺序：`models.py` → `config.py` → `scenario.py` → `simulator.py` → `geometry.py` → `belief.py` → `coverage.py` → `session.py` → `policy.py` → `run.py`。

所有物理规则、观测处理、时间账本和完成判断放在 `q3_common`；这里仅放路线B的策略选择和命令入口。

当前本地入口：

```powershell
python -m q3_common.route_b.run --seed 42 --targets 10
python -m unittest discover -s q3_common/tests_q3 -v
python -m q3_common.route_b.experiment --episodes 30 --seed-start 0
```

当前版本已经包含：七点覆盖、20频道状态、地点固定误差、本地虚拟计时、发现后半距离局部收缩、固定候选槽位、搜索/定位/清除评分和成功清除记录。
