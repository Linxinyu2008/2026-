# 2026 数学建模：B题

本仓库保存 2026 年高教社杯数学建模竞赛 B 题的题目材料、建模过程、前三问代码和本地实验结果。

## 目录

- `题目/`：官方题目 PDF 与附件原文件。
- `B题_论文资料/`：论文写作与参考资料。
- `建模过程/`：各小问的建模推导、路线讨论和代码审查记录。
- `B题问_代码/`：前三问可运行代码、测试、本地模拟器、PPO模型和回测结果。
- `docs/`：开发过程中的计划文档。

第四问代码不在本仓库中；题目原文仍包含完整四问要求。

## 本地验证

在 `B题问_代码` 目录、`data_env` 环境中运行：

```powershell
python -m unittest q1_localization.test_localization_region q2_second_detection.test_second_detection_point -v
python -m unittest discover -s q3_common/tests_q3 -v
python part123_backtest.py --episodes 10 --targets 16 --profile mixed
```

当前代码只实现本地算法和本地规则模拟。官方模拟器演练、正式测试和日志导出需要另行进行。
