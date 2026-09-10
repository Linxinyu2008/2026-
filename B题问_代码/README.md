# B题代码工作区

这里统一存放 B 题前三个问题的代码，目录按题目小问和问题3路线划分。

```text
B题问_代码/
├─ q1_localization/       第一问：交会定位区域
├─ q2_second_detection/   第二问：第二检测点选择
├─ q3_common/             第三问公共层、路线B/C和测试
│  ├─ public/             公共规则、模拟器、状态和候选动作
│  ├─ route_b/            路线B策略
│  ├─ route_c/            路线C策略
│  └─ tests_q3/           第三问测试
├─ configs/               配置文件
└─ outputs/               本地实验输出
```

第一问和第二问是几何基础模块；第三问公共层和两条路线在此基础上继续扩展，不复制相同的定位算法。

## 运行入口

```powershell
python -m q1_localization.localization_region
python -m unittest q2_second_detection.test_second_detection_point -v
python -m unittest discover -s q3_common/tests_q3 -v
python -m q3_common.route_b.run --seed 42 --targets 10
```
