# backtrader 版教材目录（本地回测）

本目录是 Quant_Lab 的**两套独立教材之一**：讲的是 `strategies/backtrader/` 里 20 个策略的**本地 backtrader 实现**，配套免费长周期数据，用 `python` 直接跑。

> 另一套是聚宽云端版 → [`docs/joinquant/`](../joinquant/README.md)
> 语法底座（必读）→ [`docs/learning/2.库详解/数据分析与量化研究相关库/backtrader详解.md`](../learning/2.库详解/数据分析与量化研究相关库/backtrader详解.md)

## 一、先读什么

```
0. 环境与数据     → ../本地回测使用指南.md
   └─ 装依赖、拉数据、跑第一个策略、常见报错
1. 语法底座       → ../learning/2.库详解/数据分析与量化研究相关库/backtrader详解.md
   └─ Cerebro / Strategy / 指标 / 分析器 / 费用滑点 / 聚宽对照表
2. 入门 10 篇     → beginner/01 … 10（建议按顺序）
3. 进阶 10 篇     → advanced/01 … 10
```

**如果你已经会聚宽**：先看 `backtrader详解.md` 的**第 0～3 章（心智模型与核心概念）**与**第 13 章（聚宽 ↔ backtrader 对照表）**，再直接进策略篇，差异一节会补齐细节。

## 二、入门篇（10 篇）

| # | 策略 | 类型 | 一句话 | 本篇重点讲透的 backtrader 语法 |
|---|------|------|--------|-------------------------------|
| 1 | [双均线趋势](beginner/01_ma_cross.md) | 技术择时 | MA5/MA20 金叉买入、死叉清仓 | `bt.Strategy` / `params` / `next` / `bt.ind.SMA` / `CrossOver` / `self.buy` / `self.close` / 索引方向 |
| 2 | [动量选股](beginner/02_momentum.md) | 单因子 | 按 60 日涨幅选前 10 名等权 | `PanelStrategy` / `__CAL__` 日历时钟 / `on_rebalance` / `equal_weight_order` |
| 3 | [低估值选股](beginner/03_value_pe_pb.md) | 单因子 | 按 PB 从低到高选股 | `value_panel` / `asof` 防未来函数 / 面板取数 |
| 4 | [小市值选股](beginner/04_size_cap.md) | 单因子 | 按总市值从小到大选股 | `total_mv` / `circ_mv` 口径 / 因子方向 |
| 5 | [质量选股](beginner/05_quality_roe.md) | 单因子 | 按 ROE 从高到低选股 | `roe_panel(lag_days=45)` 财报公告滞后 |
| 6 | [双因子组合](beginner/06_two_factor_rank.md) | 因子合成 | 动量 + 市值，排序打分 | `hist_close` 与序列语义 / 先卖后买 |
| 7 | [四因子打分](beginner/07_multi_factor_score.md) | 多因子 | 估值+质量+动量+规模 z-score | 因子标准化方向 / 面板对齐 |
| 8 | [因子中性化](beginner/08_factor_neutralize.md) | 多因子进阶 | 截面回归取残差去风格暴露 | `industry_map` / 虚拟变量 / OLS 残差 |
| 9 | [因子 IC 加权](beginner/09_factor_ic_weight.md) | 多因子进阶 | 用 IC/IR 动态调因子权重 | 滚动窗口 / 时序纪律 |
| 10 | [机器学习选股](beginner/10_ml_stock.md) | ML | 随机森林预测超额收益 | 滚动扩窗训练 / 标签滞后确认 `pending` |

## 三、进阶篇（10 篇）

| # | 策略 | 类型 | 一句话 | 本篇重点讲透的 backtrader 语法 |
|---|------|------|--------|-------------------------------|
| 1 | [波动率目标](advanced/01_volatility_targeting.md) | 风险控制 | 波动大就减仓，目标波动恒定 | `order_target_percent` vs `order_target_value` |
| 2 | [行业轮动](advanced/02_sector_rotation.md) | 中观配置 | 买最强行业，月度切换 | 多标的组织 / `live()` 停牌判断 |
| 3 | [多空对冲](advanced/03_long_short.md) | 绝对收益 | 多强空弱，剥离市场 Beta | **做空机制**：负 `size` / `position.size` 符号 / 风险熔断 |
| 4 | [事件驱动](advanced/04_event_driven.md) | 另类策略 | 业绩超预期后买入并持有窗口 | `event_calendar` 结构与窗口判断 |
| 5 | [低价可转债轮动](advanced/05_convertible_bond.md) | 跨品种 | 低价格（真双低需历史溢价率，免费源不可得） | `listed_bonds` / `load_bond_daily` / 覆盖率门槛 |
| 6 | [ETF 轮动](advanced/06_etf_rotation.md) | 资产配置 | 动量轮动 + 国债防御切换 | `value_weight_order` / 权重归一化 |
| 7 | [因子择时](advanced/07_factor_timing.md) | 因子进阶 | 按指数 PE 分位切换因子权重 | 分位数计算 / regime 切换 |
| 8 | [ML 因子合成](advanced/08_ml_factor.md) | ML 进阶 | 梯度提升合成 6 个因子 | `GradientBoostingRegressor` / 滚动训练 |
| 9 | [均值回归](advanced/09_intraday_meanrev.md) | 日内/反转 | **已降级**为日线 5 日超跌反转 | 降级实现的取舍（**无免费分钟数据**） |
| 10 | [量价情绪](advanced/10_sentiment.md) | 另类数据 | **用代理因子**替代新闻情绪 | 代理因子构造（**无免费新闻文本**） |

> 第 9、10 篇是**因免费数据受限而降级/替代**的实现，文档开头有显著声明，请先读声明再读正文。
> 第 5 篇回测区间为 2019-01 ~ 2025-06（可转债数据可得性所限），**不要与其他策略横向比收益**。

## 四、每篇的结构

每一篇都是**教程**（不是 API 手册），统一 11 节，**不敲代码也能读懂**：

```
# 策略 N：名称 · backtrader 本地版
├─ 一、这一篇你将学到什么   学习目标（策略层 + 工程层）+ 读完应能回答的问题
├─ 二、心智模型             先不看代码：这个策略在时间轴上长什么样（配具体数字走一遍）
├─ 三、核心思路             金融逻辑、公式、给新手的直觉类比 + 常见误解
├─ 四、算法结构             树状 ASCII 流程图：数据 → 判断 → 下单 → 成交
├─ 五、代码逐段详解         逐段讲透，每段都答"这段在整条链路里的位置 / 不这样写会怎样"
├─ 六、一次真实运行的轨迹   运行日志片段 + 关键变量的真实数值
├─ 七、与聚宽版的差异       触发方式、下单口径、数据来源、费用写法逐条对照
├─ 八、回测结果怎么读       真实实测数字 + 每个字段怎么理解 + 该警惕什么
├─ 九、易混点与常见错误     症状 / 原因 / 正确做法 对照表
├─ 十、自测题               不写代码也能做的检验题
└─ 十一、改进方向           针对真实短板的思考题
```

## 五、重要前提（读任何一篇前都该知道）

| 事项 | 说明 |
|------|------|
| 成交时点 | 默认**当根收盘出信号 → 次日开盘成交**，天然免疫未来函数（未开 Cheat-On-Close） |
| 索引方向 | `[0]`=当根、`[-1]`=昨天；**`[1]`=明天（禁止使用）**；首根的 `[-1]` 会静默绕到数据集末行 |
| 取数类型 | `close[0]` 是数字；**`close.get(size=n)` 返回 `array.array`（不是 list）**，但索引语义同 list：`[0]` 最旧、`[-1]` 最新；`get(ago=1)` 是**未来**，取昨天要用 `get(ago=-1)` |
| A 股成本 | 佣金双边 0.03%、印花税卖出 0.05%、单笔最低 5 元、滑点 0.02%；股数按 100 股整手 |
| 数据来源 | akshare 免费源（新浪 / 东财 / 申万 / 乐咕乐股），无需聚宽账号；ETF 为不复权价 + 分红加回修正 |
| 幸存者偏差 | 免费源只提供**当前**指数成分股，非历史成分 → 选股类策略收益偏乐观，已逐篇标注 |
| 回测区间 | 各策略不同（股票 2012+ / 指数 2005+ / ETF 2013+ / 申万 1999+ / 可转债 2019+），每篇会写明 |

运行方式：在项目根目录执行 `python strategies/backtrader/beginner/bt_s01_ma_cross.py`，或一次跑完全部 20 个：

```bash
python tools/run_all_backtrader.py            # 全部
python tools/run_all_backtrader.py s01 a05    # 只跑名字含 s01 / a05 的
```
