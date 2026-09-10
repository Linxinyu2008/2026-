# 2026 数学建模 B 题论文资料

本文件夹整理的是与“无线电干扰源的快速自动定位与清除”相关的公开论文。B 题的核心是二维测向交会、测向误差下的定位区域、第二检测点选址、未知数量多目标搜索，以及定向干扰源的可见性判断。因此，下面的论文主要从 bearing-only/AOA 定位、Fisher 信息矩阵、CRLB、主动搜索和机器人路径规划几个方向提供参考。

## 文件清单与用途

### 01_3D_Passive_Localization_in_the_Presence_of_Large_Bearing_Noise.pdf

这篇论文讨论大方位噪声下的被动 bearings-only 定位。虽然原问题是三维，但其中“目标位置由不同观测点发出的方位线交会得到”的基本几何关系可直接用于 B 题问题 1 的二维化建模。

建议重点看：方位线交会、测量误差对定位结果的影响、多个观测点联合定位。

对应 B 题：问题 1；也可作为 ±1°误差扇区模型的理论背景。

不能直接照搬：B 题给出的是确定性误差范围 [-1°,1°]，而论文主要讨论噪声模型，因此 B 题最好使用“误差扇区交集”作为主模型，再用随机误差模拟作为补充验证。

原始来源：<https://www.ee.bilkent.edu.tr/~signal/defevent/papers/cr1189.pdf>

### 02_Optimal_Sensor_Placement_for_Target_Localization_and_Tracking.pdf

Zhao、Chen 和 Lee 研究二维、三维目标定位中的最优传感器布置，涉及 bearing-only、距离和 RSS 传感器，并用 Fisher Information Matrix 以及 D-optimality 等指标评价观测几何。

建议重点看：二维 bearing-only 传感器的最优几何、FIM 行列式、传感器与目标之间的夹角、等权传感器的规则多边形布置。

对应 B 题：问题 2。可以把第一检测点得到的定位区域离散成候选目标点，对第二检测点逐点计算 FIM，选择定位不确定性最小且移动距离不过大的候选点。

论文中常见的“传感器围绕已知目标布置”假设在 B 题中并不完全成立，因为干扰源位置未知。因此需要将确定目标位置改成定位区域或目标位置先验分布。

开放版本：<https://arxiv.org/abs/1210.7397>

### 03_Sensor_Networks_for_Optimal_Target_Localization_with_Bearings-Only_Measurements.pdf

这篇 Sensors 论文系统分析了 bearings-only 定位中的传感器网络布置，并用 FIM、CRLB、A-optimality 和 D-optimality 评价定位精度。它对“为什么第二个点不能随便选”解释得比较清楚。

建议重点看：测向噪声、传感器距离、传感器与目标的相对几何、最小化 CRLB 迹的方法。

对应 B 题：问题 2；也可以作为问题 1 中定位精度评价指标的理论依据。

论文链接：<https://www.mdpi.com/1424-8220/13/8/10386>

### 04_Optimization_of_Observer_Trajectories_for_Bearings-Only_Target_Localization.pdf

Oshman 和 Davidson 讨论如何设计观测者运动轨迹，使 bearings-only 定位获得更高的可观测性和更小的不确定性。论文使用 Fisher 信息矩阵行列式来优化观测轨迹。

建议重点看：观测者运动如何改变目标—观测者几何、FIM 行列式最大化、观测路径与定位精度之间的关系。

对应 B 题：问题 2 和问题 3。问题 2 可借鉴“第二测点应主动制造更好的交会几何”；问题 3 可将下一检测点选择设计成“预计信息增益/移动时间”的最大化问题。

注意：论文主要研究连续轨迹和目标跟踪，B 题是静态干扰源、机器狗停下后才能检测，因此应保留 B 题的 5 秒检测时间和 5 m/s 移动速度约束。

论文链接：<https://oshman.net.technion.ac.il/files/2016/04/Oshman_Davidson_AES_V35_N3_Jul99.pdf>

### 05_Optimal_Geometries_for_AOA_Localization_in_the_Bayesian_Sense.pdf

Dogancay 研究带高斯先验的二维 AOA 定位，讨论 Bayesian FIM、D-optimality 和 A-optimality。它特别适合 B 题问题 2，因为第一条示向度和目标圆域可以形成一个粗略的先验区域。

建议重点看：先验协方差、误差椭圆、Bayesian FIM、D-optimality 与 A-optimality、传感器位置和先验误差椭圆之间的关系。

对应 B 题：问题 2。可以将第一条测向形成的扇区与目标圆域交集转化为概率网格，再用第二检测点使后验定位区域尽可能小。

开放获取论文页面：<https://pmc.ncbi.nlm.nih.gov/articles/PMC9785418/>

DOI：<https://doi.org/10.3390/s22249802>

### 06_Exploration-Based_Planning_for_Multiple-Target_Search.pdf

这篇论文研究未知数量、多位置目标的主动搜索，并考虑探测噪声、漏检和搜索路径。它不是无线电干扰源问题，但与 B 题问题 3 的“干扰源个数未知且必须尽可能全部清除”高度相关。

建议重点看：未知目标数量的表示方式、搜索概率更新、探索和利用的平衡、候选航点选择以及多目标路径规划。

对应 B 题：问题 3 和问题 4。可以把每个网格的“尚未发现干扰源概率”作为搜索状态，检测到信号后更新概率，并根据“发现概率、定位信息增益和移动时间”选择下一检测点。

不能直接照搬：论文面向无人机和一般目标检测，B 题还有频道切换、5 秒测向、3 秒光学精确定位和 2 秒清除等特殊时间成本。

论文页面：<https://pmc.ncbi.nlm.nih.gov/articles/PMC11086116/>

### 07_Sensor_Networks_Bearings-Only_Constrained_Scenarios.pdf

该文件是第 03 篇论文的同一开放 PDF 来源副本，内容重复保留，方便按“约束场景”关键词查找。正式写论文时只引用第 03 篇，不要把这两个文件重复列为两篇文献。

## 暂未下载但建议保留链接的论文

以下论文在检索时确认了题名和研究内容，但当前公开页面没有稳定可直接下载的 PDF 直链，或者需要通过出版社页面访问，因此没有伪造本地 PDF：

1. **Bearing-only target localization with uncertainties in observer position**：研究测向误差和观测点位置误差下的最大似然、最小二乘、总最小二乘及 CRLB。页面：<https://www.researchgate.net/publication/224205976_Bearing-only_target_localization_with_uncertainties_in_observer_position>
2. **Source searching in unknown obstructed environments through source estimation, target determination, and path planning**：研究源估计、目标选择和 A* 路径规划的闭环。页面：<https://www.sciencedirect.com/science/article/pii/S0360132322005017>
3. **Multi-Agent Active Multi-Target Search with Intermittent Measurements**：研究未知数量多目标的主动搜索和间歇性测量。页面：<https://www.sciencedirect.com/science/article/pii/S0967066124002533>
4. **Observer Path Planning for Maximum Information**：研究只使用 bearing angle 测量时，如何最大化观测路径的信息量。页面：<https://arxiv.org/abs/2103.02059>

## 阅读顺序建议

如果时间紧，建议依次阅读：02 → 03 → 05 → 04 → 06 → 01。前五篇可以搭出问题 1、问题 2 和问题 3 的主体框架，最后再用第 01 篇补充大测向误差下的稳健性分析。

## 与 B 题建模的对应关系

问题 1 适合采用“误差扇区求交 + 凸多边形直径 + 最小外接圆/覆盖判定”。问题 2 适合采用“候选网格 + 交会角/FIM/CRLB + 移动时间惩罚”。问题 3 适合采用“概率网格或粒子集合 + 覆盖搜索 + 发现后局部交会定位 + 清除顺序优化”。问题 4 需要额外维护“定向源方向候选集”，不能把一次无信号检测直接判定为该区域没有干扰源。

## 版权和使用说明

本文件夹中的论文来自作者主页、arXiv、开放获取期刊或公开论文镜像，仅用于学习和数学建模研究。引用时应以论文首页、DOI 或正式出版信息为准；GitHub 代码和论文中的具体许可证、引用要求仍需在原始页面确认。
