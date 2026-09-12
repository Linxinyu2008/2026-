# B题代码工作区

这里统一存放 B 题各小问的代码，目录按题目小问和问题3/问题4路线划分。

```text
B题问_代码/
├─ questions/q1/       第一问：交会定位区域
├─ questions/q2/   第二问：第二检测点选择
├─ questions/q3/             第三问公共层、路线B/C和测试
│  ├─ public/             公共规则、模拟器、状态和候选动作
│  ├─ route_b/            路线B策略
│  ├─ route_c/            路线C策略
│  └─ tests_q3/           第三问测试
├─ questions/q4/        第四问：定向源三角网格保证搜索
│  └─ tests/              第四问本地单元与端到端测试
├─ configs/               配置文件
└─ outputs/               本地实验输出
```

第一问和第二问是几何基础模块；第三问公共层和两条路线在此基础上继续扩展。第四问使用独立的定向源策略模块，同时复用已经验证的接口和基础数据结构，不复制第三问策略。

## 运行入口

```powershell
python -m questions.q1.localization_region
python -m unittest questions.q2.test_second_detection_point -v
python -m unittest discover -s questions/q3/tests -v
python -m questions.q3.method_b.run --seed 42 --targets 10
python -m unittest discover -s questions/q4/tests -v
python -m questions.q4.run --backend local --seed 0
```
