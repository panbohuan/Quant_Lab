# 聚宽版教材目录（云端回测）

本目录是 Quant_Lab 的**两套独立教材之一**：讲的是 `strategies/joinquant/` 里 20 个策略的**聚宽原生实现**。这些文件是**纯云端代码**——只用聚宽内置 API，整份复制粘贴到聚宽「策略研究」里就能直接回测，没有任何本地依赖。

> 另一套是 backtrader 本地版 → [`docs/backtrader/`](../backtrader/README.md)
> 聚宽函数全集 → [`docs/learning/3.聚宽函数详解/get_functions.md`](../learning/3.聚宽函数详解/get_functions.md)

## 一、先读什么

```
0. 聚宽平台概念    → 账号 / 回测界面 / 编译运行 / 回测参数（区间、资金、频率、基准）
1. 函数底座        → ../learning/3.聚宽函数详解/get_functions.md
   └─ initialize / run_daily / attribute_history / get_fundamentals / order_* 等全解
2. 入门 10 篇      → beginner/01 … 10（建议按顺序）
3. 进阶 10 篇      → advanced/01 … 10
```

**跑起来只需要三步**：登录聚宽 → 新建策略 → 把某个 `.py` 的内容**整份**粘贴进去，设好回测区间与初始资金，点"编译运行"。

## 二、入门篇（10 篇）

| # | 策略 | 类型 | 一句话 | 本篇重点讲的聚宽 API |
|---|------|------|--------|----------------------|
| 1 | [双均线趋势](beginner/01_ma_cross.md) | 技术择时 | MA5/MA20 金叉买入、死叉清仓 | `initialize` / `set_benchmark` / `set_option` / `set_order_cost` / `set_slippage` / `run_daily` / `attribute_history` / `order_target_value` / `context.portfolio` |
| 2 | [动量选股](beginner/02_momentum.md) | 单因子 | 按 60 日涨幅选前 10 名等权 | `run_monthly` / `get_index_stocks` / `get_price` / `order_target_percent` |
| 3 | [低估值选股](beginner/03_value_pe_pb.md) | 单因子 | 按 PB 从低到高选股 | `get_fundamentals` / `query` / `valuation` 表 |
| 4 | [小市值选股](beginner/04_size_cap.md) | 单因子 | 按总市值从小到大选股 | `get_fundamentals` 的 `market_cap` / 全市场过滤 |
| 5 | [质量选股](beginner/05_quality_roe.md) | 单因子 | 按 ROE 从高到低选股 | `get_fundamentals` 的 `indicator` 表 / 财报期处理 |
| 6 | [双因子组合](beginner/06_two_factor_rank.md) | 因子合成 | 动量 + 市值，排序打分 | 多因子取数 + `rank` 合成 |
| 7 | [四因子打分](beginner/07_multi_factor_score.md) | 多因子 | 估值+质量+动量+规模 z-score | 因子标准化方向 / 多表联合查询 |
| 8 | [因子中性化](beginner/08_factor_neutralize.md) | 多因子进阶 | 回归取残差去市值/行业暴露 | 行业分类 `get_industry` / `statsmodels` |
| 9 | [因子 IC 加权](beginner/09_factor_ic_weight.md) | 多因子进阶 | 用 IC/IR 动态调因子权重 | `g` 保存历史快照 / 滚动窗口 |
| 10 | [机器学习选股](beginner/10_ml_stock.md) | ML | 随机森林预测超额收益 | 特征构造 / 防未来函数 / `run_daily` 调仓 |

## 三、进阶篇（10 篇）

| # | 策略 | 类型 | 一句话 | 本篇重点讲的聚宽 API |
|---|------|------|--------|----------------------|
| 1 | [波动率目标](advanced/01_volatility_targeting.md) | 风险控制 | 波动大就减仓，目标波动恒定 | `run_weekly` / `order_target_percent` / 波动率估计 |
| 2 | [行业轮动](advanced/02_sector_rotation.md) | 中观配置 | 买最强行业，月度切换 | 行业指数 `get_price` / 行业成分 |
| 3 | [多空对冲](advanced/03_long_short.md) | 绝对收益 | 多强空弱，剥离市场 Beta | 融券做空（`order` 负数）/ 保证金 |
| 4 | [事件驱动](advanced/04_event_driven.md) | 另类策略 | 业绩超预期后买入并持有窗口 | 财报公告日 / 事件窗口管理 |
| 5 | [可转债双低](advanced/05_convertible_bond.md) | 跨品种 | 低价格 + 低溢价率 | 可转债数据 / `bond` 相关接口 |
| 6 | [ETF 轮动](advanced/06_etf_rotation.md) | 资产配置 | 动量轮动 + 国债防御切换 | ETF 列表与行情 |
| 7 | [因子择时](advanced/07_factor_timing.md) | 因子进阶 | 按指数 PE 分位切换因子权重 | 指数估值数据 / regime 判断 |
| 8 | [ML 因子合成](advanced/08_ml_factor.md) | ML 进阶 | 梯度提升合成多个因子 | 特征工程 / 模型滚动训练 |
| 9 | [高频均值回归](advanced/09_intraday_meanrev.md) | 日内 | 开盘暴跌后博日内反弹 | **分钟级** `get_price(unit='1m')` / 日内择时 |
| 10 | [舆情情绪](advanced/10_sentiment.md) | 另类数据 | 用新闻/股吧情绪打分选股 | 舆情文本数据接口 |

> 第 9、10 篇在聚宽上**能拿到分钟数据与舆情数据**，因此这两篇是"完整版思路"；它们在 `docs/backtrader/` 的对应篇目因免费数据受限做了降级/替代，两篇对照着读最能体会"数据可得性如何决定策略形态"。

## 四、每篇的结构

```
# 策略 N：名称
├─ 一、核心思路          金融逻辑、公式、给新手的直觉（含"给新手的直觉"类比）
├─ 二、算法结构          树状 ASCII 流程图（定时器触发 → 取数 → 下单）
├─ 三、代码逐段详解      逐个讲透用到的聚宽函数（参数表、其他用法、为什么这么写）
├─ 四、回测说明          建议区间/资金/频率/基准、该看哪些指标、如实的风险提示
└─ 五、改进方向（思考题）
```

> 聚宽教材**不预置回测数字**：聚宽回测结果依赖你设置的区间与资金，本仓库不给固定数字以免误导。想看**真实实测数字**，请到 backtrader 版对应篇目（本地可复现）。

## 五、重要前提

| 事项 | 说明 |
|------|------|
| 运行环境 | 聚宽官网「策略研究」在线编辑器，**无需本地 Python 环境** |
| 依赖 | 零依赖。只用聚宽内置全局函数，不需要 `pip install` 任何东西 |
| 成交默认 | 聚宽下单默认在**下一个 bar 以开盘价**撮合，与 backtrader 默认行为一致 |
| 复权 | 用 `set_option('use_real_price', True)` 开动态复权 |
| 成本 | 用 `set_order_cost(OrderCost(...), type='stock')` + `set_slippage(...)`，别省 |
| 可移植性 | 每个文件都是**自包含**的，整份复制即可运行，不要只复制其中一段 |

> 与本地版的关键区别（详见每篇的"与 backtrader 版差异"对照）：聚宽把引擎和撮合放在云端，`initialize` / `run_daily` 驱动策略；backtrader 把引擎放在本机，用 `Cerebro` + `next()` 驱动。**策略思想完全相通，载体不同。**
