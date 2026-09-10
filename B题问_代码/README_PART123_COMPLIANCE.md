# Part 1/2/3 代码实现与合规说明

本目录现在包含第一问、第二问和第三问的可复现代码、测试与本地回测入口。本文档按照附件1《模拟器使用说明》和附件2《模拟器通信接口说明及编程指南》整理，区分“已经在本地代码中实现”和“必须连接真实模拟器才能验收”的内容。

## 一、目录结构

```text
B题问_代码/
├── q1_localization/              第一问：有界示向误差交会定位
│   ├── localization_region.py
│   └── backtest.py
├── q2_second_detection/          第二问：第二检测点选择
│   ├── second_detection_point.py
│   └── backtest.py
├── q3_common/
│   ├── public/                   三部分共用的坐标、误差、计时、置信区域和官方客户端
│   ├── route_b/                  路线B独立策略
│   ├── route_c/                  混合场景训练 PPO、回测和主控制器
│   └── tests_q3/                 公共层、路线B、路线C测试
└── part123_backtest.py           三部分统一本地回测入口
```

路线 C 不导入 `route_b`；路线 B 和路线 C 只通过 `public` 共用数据结构、候选动作和本地执行规则。

## 二、已经实现的内容

### 第一问

- 将示向度误差区间转换为半平面约束；
- 求交会定位区域的有限顶点、凸包和面积；
- 区分空集、退化区域、无界区域和正常有界区域；
- 计算定位区域直径、直径圆、最小覆盖圆和覆盖比指标；
- `backtest.py` 使用多组随机目标和 ±1°误差检查求解状态与几何量是否有限。

### 第二问

- 在第一次示向结果的角域和目标圆域内生成可行粒子；
- 按面积均匀的径向变量采样，避免简单均匀半径造成偏差；
- 用接收半径下界计算鲁棒接收覆盖率；
- 用 FIM 几何损失进行候选点初筛；
- 用最坏定位区域直径进行候选点精修；
- `backtest.py` 检查接收覆盖率和最坏直径的稳定性。

### 第三问

- 公共仿真器实现圆形目标区域、移动耗时、检测耗时、频道切换和地点相关、时间固定的测向误差；
- 修正 `/clear` 语义：清除频道不改变测向机当前频道；成功清除耗时 5 秒，未发现目标耗时 3 秒；
- 新增 `public/geometry.py`，根据多次 BEARING 观测的 ±1° 半平面约束计算频道级空间置信区域中心、面积、半径和状态；
- 757 维特征现在读取置信区域中心和面积，不再把最后检测点直接当作目标中心；
- 新增 `public/official_client.py`，按附件协议封装 `/enter`、`/measure`、`/clear`、`/exit`、串行请求、`accepted` 校验、同一 `request_id` 重试和现实时间预算；
- 新增 `route_c/official_controller.py`，把公开状态、候选动作、PPO/固定扫描回退和真实 HTTP 动作串联起来；
- 路线 B 提供固定扫描和公开候选动作主动评分；
- 路线 C 提供 757 维观测、12 个候选动作、动作掩码和 Gymnasium 环境；
- 使用混合场景训练 PPO，使 `uniform`、`edge`、`clustered`、`min_radius` 和 `max_error` 都参与训练；
- 提供随机、固定扫描、主动评分和 PPO 的统一回测；
- 主控制器优先加载混合训练 PPO，模型加载失败、动作掩码异常或 PPO 输出非法动作时自动回退固定扫描；
- 所有已有测试在 `data_env` 中通过。

## 三、统一本地回测

在 PyCharm 项目目录中运行：

```powershell
conda run -n data_env python part123_backtest.py --episodes 10 --targets 16 --profile mixed
```

如果要把混合训练 PPO 也加入第三部分统一本地回测：

```powershell
conda run --no-capture-output -n data_env python part123_backtest.py --episodes 10 --targets 16 --profile mixed --model outputs/route_c/20260911_043624/model.zip
```

结果保存到：

```text
outputs/part123/part123_backtest.json
```

分别运行第一问和第二问：

```powershell
conda run -n data_env python -m q1_localization.backtest --episodes 50
conda run -n data_env python -m q2_second_detection.backtest --episodes 20
```

第三问主控制器：

```powershell
conda run -n data_env python -m q3_common.route_c.controller --model outputs/route_c/20260911_043624/model.zip --seed 30001 --targets 16 --profile mixed
```

## 四、当前本地回测结果解释

2026-09-11 修复后重新训练的PPO模型位于 `outputs/route_c/20260911_043624/model.zip`。在20个独立混合场景、每例16个全向源的本地回测中，PPO全部清除，平均定位清除时间为496.809秒；固定扫描为628.352秒。该结果只说明当前本地规则仿真中的相对表现。

回测结果只证明当前本地规则仿真中的相对表现，不等价于真实模拟器正式测试成绩。

## 五、仍需真实模拟器演练确认的内容

以下内容不能只靠本地仿真声称已经完成：

- 在已登录并启动官方模拟器的前提下，真实 `POST /enter`、`/measure`、`/clear`、`/exit` HTTP 演练；客户端代码已经准备，但本轮没有伪造服务器响应；
- `arena_id`、参赛队号 `robot_id` 和每步唯一 `request_id`；
- 网络中断时复用原请求内容和原 `request_id` 的幂等重试；
- `/enter` 返回的现实剩余时间和 1200 秒现实运行时限；
- 真实模拟器中的定向干扰源覆盖角度；
- 正式测试日志、加密日志上传和三次正式测试行为。

空间置信区域复用了第一问的完整半平面求解器，能够区分空集、退化集和无界集。第四问代码不纳入本目录；第四问题目与建模文字材料保留在上层目录中。

因此，当前代码可以用于算法实验、演练准备和本地回测，但在完成真实接口适配与至少一次演练测试前，不应宣称已经完全满足正式测试要求。

## 六、完整验证命令

```powershell
conda run -n data_env python -m unittest discover -s q3_common/tests_q3 -v
conda run -n data_env python part123_backtest.py --episodes 10 --targets 16 --profile mixed
```

官方模拟器已启动并登录后，才运行真实控制器：

```powershell
conda run --no-capture-output -n data_env python -m q3_common.route_c.official_controller --robot-id "你的参赛队号" --model outputs/route_c/<新模型目录>/model.zip
```

本命令会实际调用官方接口；未启动模拟器时不要运行，运行报告会保存到 `outputs/route_c/official/`。
