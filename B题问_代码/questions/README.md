# 四问代码目录

代码按题目问题组织，第三问再按方法拆分：

```text
questions/
├─ q1/                 第一问：交会定位
├─ q2/                 第二问：第二检测点选择
├─ q3/
│  ├─ shared/          第三问共用规则、模型、仿真和接口
│  ├─ method_b/        第三问路线B：主动搜索
│  ├─ method_c/
│  │  ├─ runtime/      共用运行器、环境、控制器
│  │  ├─ hybrid/       Hybrid 对照方法
│  │  ├─ ppo/          PPO 训练入口
│  │  └─ framework_v2/ Framework V2
│  └─ tests/            第三问测试
└─ q4/                 第四问：定向源搜索与清除
```

第三问 Framework V2 平台控制器：

```powershell
conda run --no-capture-output -n data_env python -m questions.q3.method_c.runtime.official_controller --mode framework_v2 --robot-id "你的参赛队号"
```

第三问本地回测：

```powershell
conda run --no-capture-output -n data_env python -m questions.q3.method_c.runtime.backtest --framework-v2 --episodes 20
```

运行前请在项目根目录设置 `PYTHONPATH`，或者从 `B题问_代码` 目录直接执行上述命令。
