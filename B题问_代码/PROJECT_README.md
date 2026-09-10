# B题代码工作区

这里统一存放 B 题各小问代码。目录按题目小问和问题3路线划分，公共代码只保留一份。

## 目录约定

```text
B题问_代码/
├─ q1_localization/       第一问：交会定位区域
├─ q2_second_detection/   第二问：第二检测点选择
├─ q3_common/             第三问公共层、路线B/C和测试
│  ├─ public/             公共规则、模拟器、状态和候选动作
│  ├─ route_b/            路线B策略
│  ├─ route_c/            路线C策略
│  └─ tests_q3/           第三问测试
├─ configs/     路线B/C配置
└─ outputs/     本地实验输出；不把结果混入源码
```

第一、二问分别放在 `q1_localization` 和 `q2_second_detection`。第三问公共层和两条路线在此基础上复用几何算法，不复制同一份实现。

## 实施顺序

1. 先在 `q3_common/public` 完成规则、固定误差场、虚拟计时和连续局部收缩定位。
2. 再在 `q3_common/route_b` 完成七点覆盖、候选生成和路线B入口。
3. 路线B稳定后，才在 `q3_common/route_c` 增加 Gymnasium 环境、动作掩码和 MaskablePPO。

路线B不依赖 PyTorch。路线C训练前必须先通过路线B的公共环境测试。
