# 策略 2：单因子动量选股（Momentum）· backtrader 本地版

> 策略类型：单因子选股（量价因子） ｜ 难度：★★☆☆☆ ｜ 前置知识：策略 1（指标/索引）、pandas 排序
> **运行框架：backtrader（本地回测 + 免费数据）** ｜ 本策略的**聚宽云端版**见 [docs/joinquant/beginner/02_momentum.md](../../joinquant/beginner/02_momentum.md)

## 一、核心思路：动量效应

**动量（Momentum）** 是学术界和实盘都反复验证过的异象：过去一段时间涨得好的股票，未来一段时间倾向于继续跑赢；跌得多的倾向于继续跌。背后的解释包括投资者反应不足、追涨的羊群效应、趋势惯性等。

本策略的做法非常朴素：

1. 在每个月（或每周/每天）的调仓日，计算股票池里每只股票**过去 N 个交易日（回看期）的收益率**；
2. 按收益率**降序**排序，选出最强的 `topn` 只；
3. **等权**买入并持有到下一个调仓日。

$$r_N = \frac{P_{t}}{P_{t-N}} - 1$$

其中 $P_t$ 是调仓日收盘价，$P_{t-N}$ 是 N 根 K 线前的收盘价。$r_N$ 越大，动量越强。

> 给新手的直觉：像赛车排名——你不需要预测谁会夺冠，只要"把过去一圈跑得最快的几辆车继续押注"，并定期换车。动量策略就是"赢家继续持有"的思路。

**重要提示（幸存者偏差）**：本策略的股票池用 `load_index_members('000300')` 取的是**当前**沪深300成分股。免费数据源拿不到"历史上某天"的成分股，而当前成分股都是活下来且规模够大的公司，**天然排除了早已退市或踢出指数的垃圾股**。因此回测收益会**偏高**，它只能用于教学演示"动量因子的写法与特性"，不代表真实可交易组合。聚宽云端版用 `get_index_stocks` 能拿到当时的历史成分，结论会更保守。

## 二、算法结构（分步拆解）

```
加载数据（main）：
   候选池 = load_index_members('000300') 取前 40 只
   逐只 load_universe(...) 取前复权日线，喂成多数据源
   额外喂一个 __CAL__ = 基准指数日线（每天都有行情，当"时钟"）
        │
每根日线 K 线触发 PanelStrategy.next()：
   │
   ├─ 1. 读 __CAL__ 的当前日期 cur，判断"本周期是否已调仓过"
   │      （monthly：年份+月份变了 → 触发；weekly/daily 同理）
   │
   └─ 2. 调仓日 → on_rebalance(cur)：
          ├─ 遍历 self.tradables，用 live(d, cur) 跳过停牌/未上市
          ├─ hist_close(d, lookback+1) 取近 N+1 根收盘价
          ├─ 算区间收益率 closes[-1]/closes[0]-1，存入 scores
          ├─ 样本不足 topn 则本月不调仓
          └─ 排序取前 topn → equal_weight_order(target, cur)
```

## 三、代码逐段详解 + backtrader 语法解析

### 3.1 引入多标的骨架

```python
from btlab.datasource import load_daily, load_index_members
from btlab.runner import PanelStrategy, run_strategy, load_universe
```

- `load_index_members('000300')`：取沪深300**当前**成分股代码列表（中证指数官网优先，新浪兜底）。返回的是股票代码，btlab 已按"股票"规则归一化（不会误判成指数）。
- `PanelStrategy`：btlab 给**多标的（选股类）策略**准备的骨架，封装了"交易日历、调仓频率调度、等权/市值调仓"三件琐事。下面逐条拆解它。

### 3.2 `class Momentum(PanelStrategy)` 与 `params`

```python
params = (
    ('lookback', LOOKBACK),   # 动量回看期（交易日）
    ('topn', TOPN),           # 持仓只数
    ('rebalance', REBALANCE), # 调仓频率：daily / weekly / monthly
)
```

`PanelStrategy` 自带一个 `rebalance` 参数（默认 `'monthly'`），子类可以追加自己的参数。这里三个参数都可在 `run_strategy(..., lookback=120)` 时覆盖。

### 3.3 `on_rebalance(cur)` —— 真正的调仓逻辑

```python
def on_rebalance(self, cur):
    scores = {}
    for d in self.tradables:
        if not self.live(d, cur):
            continue
        closes = self.hist_close(d, self.p.lookback + 1)
        if closes is None or closes[0] <= 0:
            continue
        scores[d._name] = closes[-1] / closes[0] - 1.0
    if len(scores) < self.p.topn:
        return
    target = sorted(scores, key=scores.get, reverse=True)[:self.p.topn]
    self.equal_weight_order(target, cur)
```

- `self.tradables`：由 `PanelStrategy.__init__` 自动生成，是**排除了 `__CAL__` 日历源之外的所有数据源**。每个元素 `d` 是一个 backtrader 数据源对象。
- `self.live(d, cur)`：判断这只票**今天有没有行情**。`return len(d) > 0 and d.datetime.date(0) == cur`——停牌或未上市时它的时间会停在旧日期，与 `cur` 不一致，据此跳过。这是多标的回测的必要防护。
- `self.hist_close(d, n)`：取标的最近 `n` 个收盘价（**含今日**），内部用 `d.close.get(size=n)`。注意 `get(size=n)` 返回普通 list，**最旧在前、最新在后**，所以 `closes[0]` 是 N 天前、`closes[-1]` 是今天。不足 n 个返回 `None`。这里取 `lookback+1` 根，用 `closes[-1]/closes[0]-1` 得到过去 `lookback` 个交易日的区间收益率。
- `sorted(..., reverse=True)[:topn]`：按动量降序取前 `topn` 只。
- `self.equal_weight_order(target, cur)`：等权调仓（见 3.5）。

### 3.4 `__CAL__` 日历机制（为什么需要它）

backtrader 以**主数据源**（第一个 `adddata` 的）的 K 线数为节拍推进 `next()`。如果某只股票今天停牌，它的 K 线数偏少，引擎推进就会错位——你没法可靠地知道"今天是几号"。`PanelStrategy` 的解法是：额外喂一根**基准指数日线**（每个交易日都有行情），命名为 `__CAL__`，专门当"时钟"。

```python
# PanelStrategy.__init__ 内部：
self.cal = self.getdatabyname('__CAL__')
self.tradables = [d for d in self.datas if d._name != '__CAL__']

# next() 内部：
cur = self.cal.datetime.date(0)        # 永远从"有行情的基准"读今天日期
mode = self.p.rebalance
key = (cur.year, cur.month) if mode=='monthly' else ...
if key == self._last_key:
    return                            # 本月已调仓，跳过
self._last_key = key
self.on_rebalance(cur)
```

这样无论个股怎么停牌，`cur` 永远是真实交易日，且 `monthly` 模式保证"每月只调一次仓"（不会因为某个月有多个交易日而每天重复下单）。`prenext` 被设为转调 `next()`，让策略从第一根 K 线起就能运行（内部已用 `live()` 和 `hist_close` 的长度判断挡住了数据不足）。

### 3.5 `equal_weight_order(names, cur, cap=0.98)` —— 等权调仓

`PanelStrategy` 提供的调仓工具，自动完成"卖旧的、买新的、对齐目标股数"：

1. 先遍历 `tradables`，把**不在目标名单里且仍有持仓**的标的 `self.close(d)` 清掉（腾出现金）；
2. 再对目标名单里的每只，按 `per = 账户总值 * 0.98 / len(名单)` 算每只应占金额，用当根收盘价 `d.close[0]` 估算目标股数，`round_lot` 取整手，与当前持仓比较得出 `delta`，`delta>0` 则 `self.buy(d, size=delta)`、`delta<0` 则 `self.sell(d, size=-delta)`。

`cap=0.98` 即预留 2% 现金缓冲，避免取整与滑点导致现金不足被拒（`order.Margin`）。

### 3.6 `main()` —— 组装数据

```python
codes = load_index_members('000300')[:UNIVERSE_SIZE]      # 前 40 只
data = load_universe(codes, start=START, end=END, adjust='qfq', label='股票池')
data['__CAL__'] = load_daily(BENCHMARK, start=START, end=END)
run_strategy(Momentum, data, cash=CASH, benchmark=BENCHMARK, ...)
```

- `load_universe`：批量取候选池日线，并**剔除"上市太晚、覆盖不了回测区间"的标的**（上市晚于起点 + 90 天宽限的会被丢弃）。日志里"候选 40 只 → 数据可用 35 只"就是这一步的结果。
- `data` 是一个 `{代码: DataFrame}` 字典，喂给 `run_strategy` 时内部逐个 `adddata`；最后把 `__CAL__` 也加进去当时钟。

### 3.7 数据源命名与查找（多标的必备语法）

`run_strategy` 内部把 `data` 字典逐个 `adddata`，用代码作 `name`。于是策略里可以用以下方式定位数据源：

- `self.getdatanames()`：返回所有数据源名字列表，例如 `['600000', '600036', ..., '__CAL__']`。
- `self.getdatabyname('600000')`：按名字取回该数据源对象 `d`。
- `d._name`：数据源的名字（代码字符串）。`PanelStrategy` 用它区分"真正的交易标的"和"日历源 `__CAL__`"——凡是 `_name == '__CAL__'` 的都排除在 `self.tradables` 之外。

> 多标的里**绝对不要**用 `self.data`（它永远指向第一个 `adddata` 的源）去代表"当前股票"。必须遍历 `self.tradables` 或 `getdatabyname(name)`。这是新手在多标的策略里最常见的混淆：写了 `self.data.close` 结果所有排序都用的是第一只股票的收盘价。

### 3.8 常见写错与陷阱（对照表）

| 写法 | 后果 | 正确做法 |
|------|------|----------|
| 子类不写 `super().__init__()` | `self.tradables` / `self.cal` 不存在，`next` 直接报错 | 子类 `__init__` 第一行必调 `super().__init__()` |
| 用 `self.data` 当"当前股票" | 永远只取到第一只，选股全错 | 遍历 `self.tradables` 或 `getdatabyname` |
| 调仓前不判断 `live(d, cur)` | 停牌/未上市票被买入，成交失败或取到旧价 | 调仓前用 `self.live()` 过滤 |
| `hist_close(d, n)` 取 n 根却用 `closes[-1]/closes[-2]` | 算错区间（应为 `closes[-1]/closes[0]-1`） | 牢记 `get(size=n)`：最旧在前、最新在后 |
| 调仓逻辑每天重复触发 | 每个交易日都重复下单、摩擦成本爆炸 | 用 `PanelStrategy` 内置的 `_last_key` 按月/周去重（已内置） |
| 用 `order_target_value` 思路写 | backtrader 无此便捷函数（需自己换算股数） | 用 `equal_weight_order` 或手算 `round_lot` |

> 关于 `load_universe` 的"宽限"：它剔除"上市晚于回测起点 + 90 天"的标的（日志里"候选 40 只 → 数据可用 35 只"就是这步的结果）。这保证多标的策略的 `next()` 从区间开头就能正常触发，不会因为某只股票上市太晚、数据不足而错位。

### 3.9 想看成交明细？加 notify_order

本策略没重写任何 `notify_order` / `notify_trade`，但回测照常出"总成交笔数"。原因是：订单状态由 backtrader 引擎自动管理，`PanelStrategy.equal_weight_order` 只是提交买卖单；绩效统计交给 `run_strategy` 里的 `Transactions` 分析器，不依赖你在策略里打印。若想知道"某笔单哪天以什么价成交"，在子类里加：

```python
def notify_order(self, order):
    if order.status == order.Completed:
        print(self.datetime.date(0), '成交', order.executed.size,
              f'价={order.executed.price:.3f}', f'费={order.executed.comm:.2f}')
```

注意 `notify_order` 在每根 K 线都可能被调用（处理上一根提交的订单），里面的逻辑不要假设"今天一定有新信号"。另外订单被拒时状态是 `order.Margin`（现金不足）或 `order.Rejected`，可借此排查"为什么该买的没买上"——多数情况是 `equal_weight_order` 的 `round_lot` 后股数为 0，或单笔低于最低佣金阈值导致整笔被拒。

## 四、与聚宽版的差异

| 维度 | 聚宽版（云端） | backtrader 本地版 |
|------|----------------|-------------------|
| 股票池 | `get_index_stocks('000300.XSHG')` 取**历史当时**成分股 | `load_index_members('000300')` 取**当前**成分股（幸存者偏差） |
| 停牌处理 | `current_data[s].paused` 等实时状态过滤 | `PanelStrategy.live(d, cur)` 用"行情日期==cur"判断 |
| 取历史行情 | `attribute_history(s, N, '1d', 'close')` | `d.close.get(size=N)` / `self.hist_close(d, N)` |
| 定时调仓 | `run_monthly(rebalance, 1)` | `PanelStrategy` 的 `next()` 内按"年月变化"自调度 |
| 下单口径 | `order_target_value` 按市值 | `equal_weight_order` 按整手股数换算 |
| 过滤 ST/涨跌停 | `filter_stocks` 六道过滤 | 本地免费源无实时 ST/涨跌停字段，仅用 `live()` 跳过停牌 |

核心思想（动量排序、等权持有）不变；触发与下单口径必须重写。本地版因免费源限制，**少了 ST/退市/涨跌停的精细过滤**，且股票池有幸存者偏差——这是数据源能力差异带来的真实降级，已在 3.1 与源码头注释如实标注。

## 五、回测结果（真实数据）

回测区间 **2015-01-05 ~ 2026-09-30**（2855 个交易日），初始资金 100 万元，股票池取沪深300成分股前 40 只、月频调仓、持仓 10 只，基准沪深300指数：

| 指标 | 数值 |
|------|------|
| 累计收益率 | 165.02% |
| 年化收益率 | 8.98% |
| 最大回撤 | -49.75% |
| 夏普比率 | 0.45 |
| 基准累计收益率 | 19.66% |
| 超额收益 | 145.35% |
| 总成交笔数 | 1723 |
| 累计换手率 | 16828.36% |

**解读（仅基于上表真实数字）：** 动量因子在 2015~2026 这段区间显著跑赢沪深300（超额 +145.35%），体现了"追涨强者"的阶段性有效性。但代价是**高波动与深回撤**：年化波动率 27.02%、最大回撤 -49.75%，远高于宽基本身——动量在 2015 股灾、2018 熊市、2021~2022 的风格反转期都会剧烈回撤，因为它持有的是前期最热的票，一旦反转跌得最狠。1723 笔成交、1.68 万 %的累计换手率说明月频换仓的摩擦成本很高，这个超额里有一部分是靠高周转换来的。**再次提醒**：这里的股票池是"当前成分股"，剔除了一路退市的公司，真实收益会被高估。

## 六、改进方向（思考题）

1. **缓解幸存者偏差**：若想更接近真实，可接入"历史成分股快照"数据源；教学上至少要清楚认知该偏差的方向（偏高）。
2. **动量 + 反转复合**：单纯追涨在熊市反转期最痛，可加入"过去 1 个月反转、过去 12 个月动量"的经典 12-1 月策略写法，平滑回撤。
3. **加波动过滤或止损**：用 `bt.ind.ATR` 剔除高波动标的，或下 `buy_bracket` 止损单，把 -49.75% 这种极端回撤压下来；也可尝试把 `rebalance` 调成 `'weekly'` 观察换手与回撤的权衡。
