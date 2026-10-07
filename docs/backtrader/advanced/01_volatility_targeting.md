# 进阶策略 1：波动率目标策略（Volatility Targeting）· backtrader 本地版

> 类型：风险控制 / 仓位管理 ｜ 难度：★★★★☆
> 前置知识：backtrader 的 `__init__` / `next()` 生命周期、Line 索引方向、`order_target_percent`
> **运行框架：backtrader（本地回测 + 免费数据）** ｜ 本策略的**聚宽云端版**见 [docs/joinquant/advanced/01_volatility_targeting.md](../../joinquant/advanced/01_volatility_targeting.md)

## 一、核心思路

入门篇的 10 个策略都在回答「选什么股票」；本策略第一次把问题切换到「该买多少仓位」。

想象你开车：平坦的高速路上可以开快一点（仓位重一点），到了弯道多、路面湿滑的山路就要减速（减仓）。波动率目标策略就是给组合装一个「油门控制器」：

- **市场波动率低**（路况好）→ 加仓，多暴露风险去博收益；
- **市场波动率高**（路况差）→ 减仓，保住本金别翻车。

它的目标不是预测涨跌，而是把组合波动率**稳定在一个目标水平**（本例年化 15%）。这是「风险预算」思想——先决定「我愿意承担多少风险」，再反过来算「应该买多少仓位」。

数学表达：

```
目标仓位 w  = 目标波动率 σ_target / 已实现波动率 σ_realized
已实现波动率 σ_realized = std(日收益率) × √252
```

- 当前年化波动率 30%，目标 15% → 仓位 = 0.5（半仓）
- 当前年化波动率 10%，目标 15% → 仓位 = 1.0（满仓，被 `max_leverage` 封顶）

给新手的直觉：牛市初期往往波动率低（市场平静），此时仓位自动加重；大跌前波动率往往先放大，仓位自动减轻。这是一个**内置的风控开关**，不需要你判断牛熊。

本策略参数一览（文件顶部常量）：

| 参数 | 默认值 | 含义 |
|------|--------|------|
| `START` | `2013-01-01` | 回测起点（免费源长历史） |
| `END` | `None` | `None` = 取到今天 |
| `CASH` | `1_000_000` | 初始资金 100 万 |
| `SYMBOL` | `510300` | 沪深300ETF（含分红口径） |
| `LOOKBACK` | `20` | 波动率估计窗口（交易日） |
| `TARGET_VOL` | `0.15` | 目标年化波动率 15% |
| `MAX_LEVERAGE` | `1.0` | 仓位上限（1.0 = 不加杠杆） |

注意 `LOOKBACK=20` 与聚宽版 `g.lookback=60` 不同，是本地版为"更快反应波动"做的调整，两边结果**不可直接横向比较**。

## 二、算法结构（分步拆解）

```
每根日线 K 线触发 next()
   │
   ├─ 1. 取当前日期的 (ISO 年, ISO 周)；与上一根同周则直接 return（周度调仓）
   │
   ├─ 2. 取最近 lookback+1 根收盘价（含今日）→ list，最旧在前
   │      └─ 数量不足 lookback+1 根 → return（数据不足降级，防未来函数）
   │
   ├─ 3. 算日收益率序列 pct_change()，年化波动率 = std(收益率) × √252
   │      └─ 波动率 ≈ 0 → return
   │
   ├─ 4. 目标仓位 w = min(σ_target / σ, max_leverage)   （封顶，禁杠杆）
   │
   └─ 5. self.order_target_percent(target=w) 把总仓位调到 w
```

## 三、代码逐段详解 + backtrader 语法解析

### 3.0 整体运行骨架：`main()` 如何接上 Cerebro

初学者最该先看清"数据从哪来、引擎怎么跑"，否则会以为策略文件自己在算净值。本例的 `main()`：

```python
df = load_daily(SYMBOL, start=START, end=END)     # akshare 免费日线 → DataFrame
run_strategy(VolTarget, {SYMBOL: df}, cash=CASH, benchmark=BENCHMARK,
             title='进阶1 波动率目标策略（backtrader · 沪深300ETF）',
             plot_path=PLOT)
```

`run_strategy`（`btlab.runner`）内部做四件事：① `build_cerebro()` 建好带 **A 股费用/滑点** 的 `Cerebro`（`AStockCommission`：佣双边 0.03%、印花税仅卖出 0.05%、单笔最低 5 元，滑点 0.02%）；② `add_feeds` 把 DataFrame 包成 `PandasData` 喂进去；③ `cerebro.run()` 逐根推进；④ 取出 `NavRecorder` 净值序列算绩效、画图。撮合、持仓、账务**全部是 backtrader 引擎在做**，策略文件只写"何时买多少"。

### 3.1 参数与 `next()` 里的周度检测

源码在 `next()` 开头这样控制调仓频率：

```python
def next(self):
    cur = self.data.datetime.date(0)          # 当根 K 线的日期（datetime.date）
    week = cur.isocalendar()[:2]              # (ISO 年, ISO 周) 元组
    if week == self._last_week:
        return                                # 同一周只调一次
    self._last_week = week
```

聚宽的 `run_weekly` 在本地没有对应物，这里用 **ISO 周年+周数** 做"换周检测"：只要相邻两根 K 线的 `(年, 周)` 相同就跳过，相当于"每周第一次出现新周号时调仓"。`self.data.datetime.date(0)` 取的是**当根**日期（`[0]` = 当根，见第 5 节索引规则）。

### 3.2 `self.data.close.get(size=N)` —— 取最近 N 根收盘价

```python
closes = self.data.close.get(size=self.p.lookback + 1)
if len(closes) < self.p.lookback + 1:
    return
```

- `get(size=N)` 返回 **`array.array`**（**不是 Python list**），元素按时间**最旧在前、最新在后**排列。
- 这里取 `lookback + 1` 根，是为了能算出 `lookback` 个收益率（相邻两根相除需要多一根）。
- **关键陷阱**：`get()` 返回的是 list，不是 Line。list 的 `[-1]` 是"最后一个 = 最新一根"，和 Line 的 `[-1]`（= 上一根/昨天）语义**完全不同**。本例全程用 pandas 处理 list，没有触碰 Line 负索引，所以不存在绕圈风险。
- `len(closes) < lookback + 1` 是**手动挡未来函数**：数据不够 N 根就算不出波动率，直接 return。等价于指标 `minperiod` 的防护作用。

### 3.3 年化波动率的计算

```python
rets = pd.Series(closes, dtype=float).pct_change().dropna()
vol = float(rets.std() * (252 ** 0.5))    # 年化波动率
```

`pct_change()` 把收盘价序列变成日收益率；`std()` 是收益率标准差；乘 `√252` 把日波动年化（A 股一年约 252 个交易日）。全程只用"过去 N 根"的历史窗口，没有任何未来数据。

### 3.4 `order_target_percent` —— 本篇重点

```python
w = min(self.p.target_vol / vol, self.p.max_leverage)
self.order_target_percent(target=w)       # w 是占总资产的比例，0.5 = 半仓
```

这是 backtrader 官方的"目标仓位比例"下单函数。它与聚宽同名同义，但**和 `order_target_value` 容易混淆**，必须厘清：

| 函数 | 入参含义 | 引擎算什么 | 适用场景 |
|------|----------|------------|----------|
| `order_target_value(target=500000)` | 目标市值（元） | 买/卖到"持仓市值 = 50 万" | 单一标的目标金额固定 |
| `order_target_percent(target=0.5)` | 目标仓位比例 | 买/卖到"持仓市值 = 总资产 × 0.5" | 全账户按比例调配，本例最合适 |
| `order_target_size(target=100)` | 目标股数 | 买/卖到"持仓 = 100 股" | 精确股数控制 |

波动率目标策略用 `order_target_percent` 最契合：它要的是"组合整体暴露 0.5 倍风险"，而 `target` 直接是占总资产比例，引擎自己按当前市值换算股数，天然适配"仓位随净值波动"的需要。

> 注意 A 股整手约束：`order_target_percent` 内部换算出的股数会带零头，但本例标的只有一只 ETF，且引擎默认 `set_checksubmit(True)` 会校验现金，零头不影响成交。若想严格整手，应像 a02~a05 那样先 `round_lot` 再 `buy/sell`。

### 3.5 索引方向自检（全仓库铁律）

本策略只用到 `close.get(size=N)`（序列语义）和 `datetime.date(0)`（当根）。重申：Line 索引 **`[0]`=当根、`[-1]`=昨天、`[-2]`=前天、`[1]`=明天（未来，禁用）**。首根 K 线上 `[-1]` 会静默绕到数据集末行（无声未来函数），本例靠"数据不足就 return"挡住。

### 3.6 `stop()` 收尾打印

```python
def stop(self):
    print(f'仓位区间 {min(self.weights)*100:.1f}% ~ {max(self.weights)*100:.1f}%')
```

回测结束自动调用一次，打印真实调仓出的仓位区间（日志显示 17.3%~100.0%，平均 84.8%），用于验证"低波动加仓、高波动减仓"是否真的生效。

### 3.7 为什么"默认次日开盘成交"本身就是防未来函数

backtrader 的成交时点是本仓库所有策略成立的基石。`next()` 在第 t 根 K 线**收完之后**才被调用——此时你看到的是第 t 根的收盘价，但现实里收盘后你来不及按收盘价成交。引擎因此默认把订单推迟到**第 t+1 根开盘价**成交：

```
第 t 根：next() 看到收盘 → 提交 buy/sell
        ↓ 订单不在这根成交
第 t+1 根：开盘价成交
```

这天然免疫"用当根收盘价下单、当根收盘价成交"的未来函数。本策略 `order_target_percent` 因此永远按"今天收盘算出的仓位 → 明天开盘调到位"，与聚宽 `run_weekly(time='09:30')` 的次日开盘语义一致。仓库**一律不开** `set_coc(True)`（当根收盘成交），因为它会削弱这层保护。

### 3.8 `__init__` 里为什么只存状态、不声明指标

本策略的 `__init__` 只有两行：

```python
self._last_week = None
self.weights = []
```

没有 `bt.ind.SMA` 之类的指标声明——因为波动率每调仓一次都用 `get(size=N)` 现算，是**无状态**的，不存在"指标需要 minperiod"的问题。这也意味着引擎不会自动挡未来函数（没有 minperiod），所以"数据不足就 return"这行手动判断**必须保留**，它是本策略唯一的未来函数防线。对比有指标的策略（如带 `SMA(60)`），本例是把防护责任完全交给了程序员。

## 四、与聚宽版的差异

| 维度 | 聚宽云端版 | backtrader 本地版 |
|------|-----------|-------------------|
| 触发方式 | `run_weekly(rebalance, 1, time='09:30')`（每周一） | `next()` 内 `isocalendar()[:2]` 换周检测，等效于每周首根 |
| 下单口径 | `order_target_value(security, 目标市值)` | `order_target_percent(target=仓位比例)`，语义更直接 |
| 回看窗口 | `g.lookback = 60` | `LOOKBACK = 20`（参数不同，结果不可直接比） |
| 仓位下限 | `min_weight = 0.0`（可空仓） | 仅封顶 `max_leverage`，无下限（波动率极低时自动满仓） |
| 标的代码 | `000300.XSHG` 指数 | `510300` ETF（含分红口径，更贴近实盘） |
| 数据来源 | 聚宽平台行情 | `btlab.datasource.load_daily`（akshare 免费源） |
| 手续费/滑点 | `set_order_cost` + `set_slippage(FixedSlippage(0.02))` | `AStockCommission`（佣双边 0.03%、印花卖 0.05%、最低 5 元）+ 滑点 0.02% |
| 成交时点 | 平台约定次日 | 默认"当根收盘出信号 → 次日开盘成交"（天然防未来函数） |

思路完全一致，差异全在"触发方式"和"下单口径"两处——印证了对照表那句"思路能平移，写法必须重写"。

## 五、回测结果（真实数据）

区间 2013-01-04 ~ 2026-09-30（3338 个交易日），初始资金 100 万元，基准沪深300。数据来自 `results/logs/bt_a01_volatility_targeting.log`。

| 指标 | 数值 |
|------|------|
| 累计收益率 | 103.76% |
| 年化收益率 | 5.52% |
| 基准累计收益率 | 72.62% |
| 超额收益 | 31.14% |
| 最大回撤 | -35.39% |
| 夏普比率 | 0.45 |
| 年化波动率 | 14.32% |
| 日胜率 | 50.50% |
| 总成交笔数 | 344 笔 |
| 累计换手率 | 4088.80% |

解读：波动率目标策略跑赢了满仓持有沪深300（超额 +31.14%），且仓位区间 17.3%~100%、平均 84.8%，确实在波动高时降仓。但它**没有显著降低回撤**（最大回撤 -35.39%，与沪深300 自身回撤量级接近），夏普 0.45 只算中庸——说明"单标的波动率目标"主要贡献了"平滑仓位"而非"降低尾部风险"。年化波动 14.32% 与目标 15% 接近，风控开关工作正常。

## 六、改进方向（思考题）

1. **放开或抬升 `max_leverage`**：当前封顶 1.0 禁止杠杆；若允许 1.2~1.5 倍，低波动期收益弹性更大，但需评估 A 股 ETF 无法真正加杠杆的实盘约束。
2. **用 EWMA 波动率替代简单 std**：`rets.ewm(span=lookback).std()` 对近期波动更敏感，大跌前能更快减仓，回撤可能更小。
3. **下行波动率 / 波动率上限 + 止损**：只算"下跌日"波动，或叠加 `buy_bracket` 止损腿（见 backtrader 详解 7.4 节），在暴跌中主动断臂。
