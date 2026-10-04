# 策略 1：双均线趋势跟踪（MA Cross）· backtrader 本地版

> 策略类型：技术指标择时（单标的） ｜ 难度：★☆☆☆☆ ｜ 前置知识：Python 基础、K线/均线概念
> **运行框架：backtrader（本地回测 + 免费数据）** ｜ 本策略的**聚宽云端版**见 [docs/joinquant/beginner/01_ma_cross.md](../../joinquant/beginner/01_ma_cross.md)

## 一、核心思路

**均线（MA，Moving Average）** 是过去 N 个交易日收盘价的算术平均值，用来平滑价格波动、看清趋势方向：

$$MA_N = \frac{\text{最近 } N \text{ 天的收盘价之和}}{N}$$

例如 5 日均线，就是把最近 5 天的收盘价加起来除以 5。每天收盘后算出一个新的 5 日均线值，连起来就是一条"跟随价格、但更平滑"的曲线。

**为什么需要短期和长期两条均线？**

- **短期均线**（如 5 日）只用了很少几天数据，对价格变化反应**快**，紧跟价格；
- **长期均线**（如 20 日）平均了更多天数据，更**平滑**，代表中期趋势方向。

两条均线的**相对位置**和**交叉**构成买卖信号：

- **金叉（买入信号）**：短期均线从下向上穿过长期均线，意味着短期价格开始强于长期趋势，可能是一轮上涨的启动；
- **死叉（卖出信号）**：短期均线从上向下穿过长期均线，意味着短期走弱，可能转跌。

这就是**趋势跟踪（Trend Following）**的雏形：**不预测涨跌，只跟随趋势**。涨了就跟进去吃利润（让利润奔跑），跌了就离场截断亏损。

> 给新手的直觉：想象你在观察一列火车（价格）。均线就是"火车头的平均位置"。当快的车头（短期均线）超过了慢的车厢（长期均线），说明车在加速前进，你上车；反过来车头落后了，说明在减速，你下车。

## 二、算法结构（分步拆解）

```
每根日线 K 线触发 next()（数据不足时走 prenext，默认跳过 —— 由 SMA(slow) 的 minperiod 自动挡住）
   │
   ├─ 1. 指标已在 __init__ 声明：ma_fast / ma_slow / cross
   │      cross = CrossOver(ma_fast, ma_slow)，引擎逐根自动递推
   │
   ├─ 2. 当前状态 self.position 是否为空仓？
   │      ├─ 空仓 且 cross[0] > 0（本根发生金叉）→ 计算整手股数并买入
   │      └─ 持仓 且 cross[0] < 0（本根发生死叉）→ 清仓
   │
   └─ 3. self.buy(size=...) / self.close()
          ↓ 默认：下一根 K 线开盘价成交（天然防未来函数）
```

关键点：本例**不手动比较"今天"和"昨天"的均线**，而是把这件事交给 `bt.ind.CrossOver`。它在每一根 K 线上自动判断"当根短均线是否上穿/下穿长均线"，返回 `+1`（上穿）、`-1`（下穿）、`0`（未交叉）。引擎的 `minperiod` 机制保证在均线数据未凑够之前不会执行 `next()`，因此不存在"偷偷看未来"的问题。

## 三、代码逐段详解 + backtrader 语法解析

### 3.1 顶部导入与路径处理

```python
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import backtrader as bt
from btlab.datasource import load_daily
from btlab.runner import run_strategy, round_lot
```

- `import backtrader as bt`：引入回测引擎本体。本仓库**所有**撮合、账户、指标、绩效都由它负责，btlab 只是样板封装。
- `load_daily`：btlab 的数据入口，自动识别股票/ETF/指数，从新浪/东财等免费源取日线，并缓存到 `data_cache/`。
- `run_strategy`：btlab 的"一键回测"，内部建好带 A 股费用/滑点的 `Cerebro`、喂数据、跑、出报告、画净值图。
- `round_lot`：把任意股数向下取整到 100 的整数倍（A 股 1 手 = 100 股/份）。**backtrader 本身不懂整手**，传 137 股它就真买 137 股，必须自己截。

### 3.2 回测参数

```python
START = '2013-01-01'     # 数据起点（沪深300ETF 2012-05 上市）
END = None               # None = 到今天
CASH = 1_000_000         # 初始资金
BENCHMARK = '000300'     # 基准：沪深300指数
SYMBOL = '510300'        # 交易标的：沪深300ETF
```

这些都是普通变量，直接改即可调参。ETF 用 `510300`（沪深300ETF）；基准用 `000300`（指数代码，btlab 能自动区分股票与指数）。

### 3.3 `class MaCross(bt.Strategy)` —— 策略基类

所有 backtrader 策略都继承 `bt.Strategy`。引擎在回测中按固定顺序回调你的方法：`__init__`（一次）→ `prenext/nextstart/next`（逐根）→ `notify_order`（订单状态）→ `stop`（收尾）。

### 3.4 `params` —— 策略参数

```python
params = (
    ('fast', 5),      # 短期均线周期
    ('slow', 20),     # 长期均线周期
    ('stake', 0.95),  # 买入资金比例（留 5% 缓冲，避免滑点/费用导致下单失败）
)
```

- `params` 是**元组套元组** `(('名字', 默认值), ...)`。在 `addstrategy(MaCross, fast=10)` 时可运行时覆盖。
- 在策略内部用 `self.p.fast`、`self.p.slow`、`self.p.stake` 读取。
- 注意 `SMA` 的**默认值其实是 30**（不是 20），所以这里**显式写 `period=`** 是必须的。

### 3.5 `__init__` —— 声明指标（只跑一次）

```python
def __init__(self):
    self.ma_fast = bt.ind.SMA(self.data.close, period=self.p.fast)
    self.ma_slow = bt.ind.SMA(self.data.close, period=self.p.slow)
    self.cross = bt.ind.CrossOver(self.ma_fast, self.ma_slow)
```

- **声明与执行分离**：指标在 `__init__` 里只"描述怎么算"，引擎在每根 K 线自动递推。这里**不能**写 `self.data.close[0]` 之类的"当前值"——此时还没有当前 K 线。
- `bt.ind.SMA(line, period=N)`：简单移动平均，返回一条 Line。默认对 `self.data` 生效，这里显式传 `self.data.close`。
- `bt.ind.CrossOver(a, b)`：交叉指标。当 `a` 从下方上穿 `b` 输出 `+1`，下穿输出 `-1`，其余 `0`。它内部自动对比 `a[0] vs b[0]` 与 `a[-1] vs b[-1]`，即"当根是否反超了上一根"。

### 3.6 `next()` —— 每根 K 线（交易日）执行一次

```python
def next(self):
    if not self.position:
        if self.cross[0] > 0:
            size = round_lot(self.broker.getcash() * self.p.stake / self.data.close[0])
            if size > 0:
                self.buy(size=size)
    elif self.cross[0] < 0:
        self.close()
```

**索引方向（最重要的一条，务必记牢）：**

| 写法 | 含义 | 能否在回测用 |
|------|------|--------------|
| `self.data.close[0]` | **当根**收盘价 | 可以 |
| `self.data.close[-1]` | **上一根**（昨天） | 可以 |
| `self.data.close[-2]` | 上上根（前天） | 可以 |
| `self.data.close[1]` | **下一根（明天）** | **禁止**（未来数据） |

> 隐蔽坑：在第一根 K 线上写 `close[-1]` **不会报错**，而是静默绕到数据集最后一行（等于偷看未来）。本策略靠 `SMA(slow=20)` 的 `minperiod` 自动挡住——前 19 根引擎调 `prenext` 而非 `next`，到数据足够时才首次进 `next`，此时 `[-1]` 一定是真实历史。**绝对不要**用正索引 `[1]` 看后面。

**逐行解读：**

- `not self.position`：`self.position` 是当前标的的持仓对象，空仓时 `size==0`，`if not self.position` 即"当前空仓"。
- `self.cross[0] > 0`：本根发生了金叉。
- `self.broker.getcash()`：账户当前可用现金（元）。`* self.p.stake` 即只用 95% 留缓冲。
- `/ self.data.close[0]`：用当根收盘价估算能买多少股。
- `round_lot(...)`：取整到 100 的整数倍。`if size > 0` 防止取整后变 0。
- `self.buy(size=size)`：下买单。**默认成交在下一根开盘价**——这是 backtrader 的天然防未来函数机制，也是本仓库 20 个策略统一的"隔夜决策"口径。
- `self.close()`：平掉当前标的全部持仓，最省心的离场方式，自动算方向与数量。

### 3.7 `main()` 与 `run_strategy`

```python
df = load_daily(SYMBOL, start=START, end=END)
run_strategy(MaCross, {SYMBOL: df}, cash=CASH, benchmark=BENCHMARK,
             title='策略1 双均线趋势跟踪（backtrader · 沪深300ETF）',
             plot_path=PLOT)
```

- `load_daily` 返回 `DataFrame`（含 `open/high/low/close/volume` 列与 `DatetimeIndex`），`run_strategy` 内部用 `bt.feeds.PandasData` 喂给引擎。
- `benchmark='000300'`：`run_strategy` 内部会再加载基准指数，计算"基准累计收益率"和"超额收益"并画对比曲线。
- 运行：`python strategies/backtrader/beginner/bt_s01_ma_cross.py`，首次联网拉数据并缓存，之后秒开；净值图存到 `results/bt_s01_result.png`。

### 3.8 `run_strategy` 内部：分析器与绩效指标（回测是怎么算出来的）

`run_strategy` 在背后做了几件 backtrader 标准动作，了解它们有助于你读懂日志里的每一项指标：

- `NavRecorder`（btlab 自定义的 `bt.Analyzer`）：在每根 K 线的回调里记录 `self.broker.getvalue()`（账户总资产），得到一条逐日净值序列。它同时实现了 `prenext / nextstart / next` 三种回调，覆盖"数据不足期"和"正常期"，保证净值曲线从第一天起就有值。
- `bt.analyzers.Transactions`：逐笔记录成交明细。`run_strategy` 用它汇总"总成交笔数"和"累计成交额"，后者除以初始资金得到日志里的"累计换手率"。
- `perf_from_nav(nav)`：基于上面那条净值序列，算累计/年化收益、最大回撤（`nav / nav.cummax() - 1` 的最小值）、夏普（`日均收益均值 / 标准差 × √252`）、年化波动率、日胜率。公式都是标准的，你改不了口径，但要明白它们是"账户总资产"视角（已含现金与持仓市值），不是单纯净值。

所以你代码里**不需要**自己写绩效计算——`run_strategy` 一站式搞定。这也是 btlab"样板封装"的意义：20 个策略共用同一套费用、滑点、绩效口径，结果才互相可比。

### 3.9 常见写错与陷阱（对照表）

| 写法 | 后果 | 正确做法 |
|------|------|----------|
| `self.data.close[1]` | 取"明天"，未来函数；末根还会 `IndexError` | 只用 `[0]` 与负索引 |
| 第一根 K 线写 `close[-1]` | 静默绕到数据集末行（偷看未来） | 靠 `SMA(slow)` 的 `minperiod` 自动挡；或 `len(self) >= N` |
| `bt.ind.SMA(period=20)` 不写参数 | 实际得到 **30** 日均线 | 永远显式写 `period=` |
| 买入 `size=137` | backtrader 真买 137 股（非整手） | `round_lot(size)` 取整手 |
| 满仓 `size = cash / price` 不留缓冲 | 滑点/费用导致现金不足，`order.Margin` 拒单 | 用 `self.p.stake=0.95` 留 5% |
| 在 `__init__` 里读 `close[0]` | 此时还没有当前 K 线，直接报错 | 数值操作全放 `next()` |

> 上面最后一条尤其隐蔽：有人图省事把"读数值 + 下单"塞进 `__init__`，结果回测立刻报错——因为指标的"当前值"只有在 `next()` 被调用、某根具体 K 线存在之后才存在。`__init__` 只负责"声明线"，`next()` 才负责"读线上的值"。

## 四、与聚宽版的差异

| 维度 | 聚宽版（云端） | backtrader 本地版 |
|------|----------------|-------------------|
| 触发方式 | `run_daily(trade, time='14:50')` 每天盘中触发 | `next()` 每根日线自动触发（收盘出信号） |
| 信号计算 | 用 `attribute_history` 取 21 根，自己算"今天/昨天"均线判断交叉 | 用 `bt.ind.CrossOver` 引擎自动递推交叉，无需手算窗口 |
| 下单口径 | `order_target_value(security, value)` 按目标市值 | `self.buy(size=整手股数)` 按股数，需 `round_lot` 取整 |
| 数据来源 | 聚宽内置行情（需账号） | btlab + akshare 免费源（新浪），ETF 用"加回分红"的含分红口径修正 |
| 手续费/滑点 | `set_order_cost` + `set_slippage` | `build_cerebro` 内置 `AStockCommission`（佣金双边 0.03%、印花税仅卖出 0.05%、单笔最低 5 元、滑点 0.02%） |
| 基准对比 | `set_benchmark('000300.XSHG')` | `run_strategy(benchmark='000300')` 内部加载对比 |
| 成交时点 | 默认次日开盘（云端） | 默认次日开盘（backtrader 默认） |

思路完全一致（金叉满仓、死叉清仓），只是"谁提供引擎"和"怎么下单"不同。聚宽的 `order_target_value` 自带再平衡（自动算股数），backtrader 则需要自己算整手股数——这是 A 股整手约束带来的必然差异，不是策略变化。

## 五、回测结果（真实数据）

回测区间 **2013-01-04 ~ 2026-09-30**（3338 个交易日），初始资金 100 万元，标的沪深300ETF，基准沪深300指数：

| 指标 | 数值 |
|------|------|
| 累计收益率 | 5.31% |
| 年化收益率 | 0.39% |
| 最大回撤 | -39.24% |
| 夏普比率 | 0.10 |
| 基准累计收益率 | 72.62% |
| 超额收益 | -67.31% |
| 总成交笔数 | 224 |
| 累计换手率 | 23703.32% |

**解读（仅基于上表真实数字）：** 这张成绩单清楚地体现了趋势跟踪策略在"慢牛+长震荡"市场的特征——它大幅跑输买入持有沪深300（超额 -67.31%）。原因有二：一是均线策略在 2013~2014 与 2019~2021 的震荡期反复出现假金叉/假死叉，频繁进出（累计换手率高、224 笔成交但年化仅 0.39%）；二是趋势策略天然"慢半拍"，在 2015 股灾式的急跌里来不及离场，造成 -39.24% 的最大回撤。双均线本身没有错，它只是**不适合长期慢涨、短期剧烈的 A 股宽基单边市**；它的价值在于帮你建立"指标 + 索引 + 成交时点"的 backtrader 肌肉记忆。

## 六、改进方向（思考题）

1. **加趋势过滤**：只有在长期均线向上（即 `ma_slow[0] > ma_slow[-1]`）时才允许做多，从根上规避熊市里的反复假信号。
2. **换 EMA 或加长均线**：把 `fast/slow` 调成 `10/60`，或用 `bt.ind.EMA` 给近期更高权重，观察滞后与回撤的变化（可用 `cerebro.optstrategy` 做参数优化，但警惕过拟合）。
3. **加止损/止盈**：用 `self.buy_bracket(...)` 一次下"主单 + 止损单 + 止盈单"三腿，让单笔亏损有上限，而不是被动等死叉。
