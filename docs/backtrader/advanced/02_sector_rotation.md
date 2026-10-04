# 进阶策略 2：行业轮动策略（Sector Rotation）· backtrader 本地版

> 类型：中观配置 / 行业轮动 ｜ 难度：★★★★☆
> 前置知识：多数据源喂入、`PanelStrategy` 骨架、`__CAL__` 日历时钟、`getdatabyname` / `live()`
> **运行框架：backtrader（本地回测 + 免费数据）** ｜ 本策略的**聚宽云端版**见 [docs/joinquant/advanced/02_sector_rotation.md](../../joinquant/advanced/02_sector_rotation.md)

## 一、核心思路

前一篇还在"个股 / 单标的"层面，本篇升到**中观（行业）**层面。思路是"自上而下"：先选行业，再在行业内选股。本例简化为"直接在行业层轮动"——买入动量最强的 K 个申万一级行业。

「行业动量」的直觉：过去一段涨得最好的行业，短期往往还有惯性（动量效应）。每月把仓位切到最强的几个行业，相当于"永远站在风口上"。

数学表达（行业动量）：

```
momentum_i = close_i(today) / close_i(t - lookback) - 1
```

选 `momentum` 最大的 `TOPN` 个行业，等权买入，月度再平衡。

给新手的直觉：行业有"景气度轮动"——白酒好的时候买白酒，新能源起来的时候切新能源。轮动策略赚的是"行业景气度切换"的钱，不用预测哪只个股最牛。

本策略参数一览（文件顶部常量）：

| 参数 | 默认值 | 含义 |
|------|--------|------|
| `START` | `2010-01-01` | 回测起点（申万指数 1999 年起，取长区间） |
| `END` | `None` | 取到今天 |
| `CASH` | `1_000_000` | 初始资金 100 万 |
| `TOPN` | `5` | 持有动量最强的行业数 |
| `LOOKBACK` | `60` | 行业动量回看期（交易日） |

聚宽版是"3 行业 × 10 个股"的二级结构，本地版简化为"直接轮动 5 个行业指数"，复杂度更低、更适合教学演示轮动逻辑本身。

## 二、算法结构（分步拆解）

```
main()：加载 31 个申万一级行业指数 + 沪深300(__CAL__ 日历)
   │
   └─ run_strategy() 启动回测，引擎逐根推进
         │
         └─ 每根 K 线 next()（PanelStrategy 调度）
               │
               ├─ 月份变化？（(年,月) != _last_key）→ 进入 on_rebalance(cur)
               │
               └─ on_rebalance(cur)：
                     ├─ 1. 遍历 self.tradables，只保留 live(d, cur) 的行业
                     ├─ 2. 每个行业算动量 = close[-1]/close[0] - 1
                     │      └─ hist_close(d, lookback+1) 取最近 N 根收盘（不足则跳过）
                     ├─ 3. 行业数 < TOPN → 跳过
                     ├─ 4. 按动量降序取前 TOPN 个
                     └─ 5. equal_weight_order(target, cur) 等权调仓
```

## 三、代码逐段详解 + backtrader 语法解析

### 3.0 数据源 API：`sw_industries` 与 `load_sw_index`

行业轮动依赖两个免费接口（`btlab.datasource`）：

| 函数 | 返回 | 说明 |
|------|------|------|
| `sw_industries()` | `DataFrame([code, name])` | 申万一级行业列表（共 31 个，日志确认全部可用） |
| `load_sw_index(code, start, end)` | `DataFrame[open,high,low,close,volume]` | 单个申万行业指数日线（1999 年起） |

`main()` 遍历 `sw_industries()` 逐行业 `load_sw_index`，只保留长度 ≥ `LOOKBACK+1` 的（剔除数据太短的行业），再把沪深300 作为 `__CAL__` 日历源一并加入。注意本例用**行业指数**轮动，31 个全部可用；若想复刻聚宽版"行业内选股"，需改用 `load_sw_members`，而它因上游限流只能覆盖约 16/31 个行业（见差异节）。

### 3.1 多数据源喂入与 `__CAL__` 日历源

`main()` 把 31 个行业指数和一个沪深300 指数一起喂给 `run_strategy`：

```python
data[row['name']] = load_sw_index(row['code'], start=START, end=END)
...
data['__CAL__'] = load_daily(BENCHMARK, start=START, end=END)
```

- backtrader 以**主数据源**（第一个 `adddata` 的）K 线数为节拍。行业指数各自停牌/上市时间不同，若以某行业当节拍会错位。
- 解法是额外喂一个"**每个交易日都有行情**"的沪深300，命名为 `__CAL__`，专门当**时钟**。引擎的 `next()` 按 `__CAL__` 的日期推进，再判断"今天该调仓吗"。

### 3.2 `PanelStrategy` —— 多标的调仓骨架

本策略继承 `btlab.runner.PanelStrategy`，它已替你写好三件琐事：

```python
class PanelStrategy(bt.Strategy):
    params = (('rebalance', 'monthly'),)     # 'daily' | 'weekly' | 'monthly'

    def __init__(self):
        self.cal = self.getdatabyname('__CAL__')          # 日历源
        self.tradables = [d for d in self.datas
                          if d._name != '__CAL__']          # 真正的交易标的

    def next(self):
        cur = self.cal.datetime.date(0)                    # 以日历源日期为准
        key = (cur.year, cur.month)                        # monthly 模式
        if key == self._last_key:
            return
        self._last_key = key
        self.on_rebalance(cur)                             # 子类只需实现这个
```

子类只需实现 `on_rebalance(cur)`。调度逻辑（周/月/日切换）由骨架统一处理，你不必在每个策略里重写一遍 `isocalendar`。

### 3.3 `self.getdatabyname` 与 `self.tradables`

```python
self.names = {d._name: d._name for d in self.tradables}
```

- `self.datas`：全部数据源列表（含 `__CAL__`）。
- `self.tradables`：`PanelStrategy` 已排除 `__CAL__` 后的可交易标的。
- `self.getdatabyname('510300')`：按 `adddata(name=...)` 时给的名字取回数据源对象。多标的遍历、按名取数都靠它。

### 3.4 `live(d, cur)` —— 停牌 / 未上市判断

```python
def live(self, d, cur):
    return len(d) > 0 and d.datetime.date(0) == cur
```

这是本仓库判断"这只票今天有没有行情"的标准写法。某行业指数若今天停牌或未上市，它的 `datetime` 会停在旧日期，`d.datetime.date(0) != cur` → 返回 `False`，跳过不参与。这是多标的回测防"对齐错位"的核心。

### 3.5 `hist_close` 与 Line 索引方向

```python
closes = self.hist_close(d, self.p.lookback + 1)
if closes is None or closes[0] <= 0:
    continue
scores[d._name] = closes[-1] / closes[0] - 1.0
```

- `hist_close(d, n)` 内部是 `d.close.get(size=n)`，返回 **list（最旧在前、最新在后）**。
- `closes[-1]` 是 list 的**最后一个 = 最新一根收盘价**；`closes[0]` 是最旧一根。这是 **list 语义**，与 Line 的 `[-1]=昨天` 完全不同，务必分清。
- 动量 = 最新/最旧 - 1，只用历史窗口，无未来数据。
- `closes is None` 表示该行业数据不足 N 根（手动挡未来函数）。

### 3.6 `equal_weight_order` 等权调仓

```python
self.equal_weight_order(target, cur)     # target 是代码列表
```

骨架按 `总资产 × 0.98 / len(target)` 算出每只目标金额，先 `close` 不在名单的，再 `buy/sell` 差额对齐到目标股数。逻辑全在 `PanelStrategy` 里，子类一行调用即可。

### 3.7 防未来函数小结

只用 `close.get(size=n)`（历史窗口）+ 以 `__CAL__` 当日日期判断调仓 + `live()` 过滤停牌。没有任何 `[1]` 正索引、没有任何"看后面"。

### 3.8 一个动量计算的数值例子

假设某行业指数最近 61 根收盘价为 `closes`（list，最旧在前），其中：

```
closes[0]  = 1000   （60 个交易日前）
closes[-1] = 1150   （今天）
```

则动量 = `closes[-1] / closes[0] - 1 = 1150/1000 - 1 = 15%`。所有行业都算出这个值后，取最大的 `TOPN=5` 个进入 `equal_weight_order`。注意 `closes[-1]` 是 **list 最后一个 = 今天**，`closes[0]` 是 **list 最旧 = 60 天前**——这是 list 语义，和 Line 的 `[-1]=昨天` 恰好相反，是本仓库反复强调的易错点。

### 3.9 为什么本例"31 个行业全部可用"但仍有局限

日志打印"可用行业指数 31 个"，因为申万行业**指数**（`load_sw_index`）覆盖全部 31 个一级行业，免费源完整。但这意味着回测买的是"行业指数"本身——它在 backtrader 里能成交，实盘却不可直接交易（要换行业 ETF）。更深的局限在**数据口径**：本例是"行业层轮动"，并不等同于聚宽版"行业内选股"。若想复刻聚宽版，需要 `load_sw_members` 取行业内个股，而该接口因上游限流只能覆盖约 16/31 个申万一级行业（`industry_map` 会跳过异常行业），届时行业覆盖会有明显缺口。教学时务必分清"指数轮动"与"个股轮动"两件事。

## 四、与聚宽版的差异

| 维度 | 聚宽云端版 | backtrader 本地版 |
|------|-----------|-------------------|
| 选股层级 | 先选 TOPN 行业，再在**行业内选股**（`get_industry_stocks` + 个股动量，3 行业 × 10 股） | 直接拿**申万一级行业指数**做轮动标的，无行业内二次选股（简化版） |
| 触发方式 | `run_monthly(rebalance, 1, time='09:30')` | `PanelStrategy` 的 `(年,月)` 变化检测 |
| 行业数据 | `get_industries('sw_l1')` + 行业指数 `.SI` 行情 | `sw_industries()` + `load_sw_index(code)`（1999 年起免费） |
| 可交易性 | 选出的个股可直接交易 | 行业指数本身不可直接交易，实盘应换对应行业 ETF（教学演示用） |
| 下单口径 | `order_target_value(security, 市值)` | `equal_weight_order`（目标股数，已 `round_lot` 整手） |
| 数据来源 | 聚宽平台 | akshare 免费源 |

**重要诚实提示**：本例用行业**指数**轮动，31 个行业全部可用（日志确认 31 个）。但若想复刻聚宽版"行业内选股"，则要用 `load_sw_members`，而该接口因上游限流**只能覆盖约 16/31 个申万一级行业**（`industry_map` 会跳过异常行业），届时行业覆盖会有缺口。另外本例股票池用"当前"成分，存在幸存者偏差。

## 五、回测结果（真实数据）

区间 2010-01-04 ~ 2026-09-30（4067 个交易日），初始资金 100 万元，基准沪深300。数据来自 `results/logs/bt_a02_sector_rotation.log`。

| 指标 | 数值 |
|------|------|
| 累计收益率 | 79.72% |
| 年化收益率 | 3.70% |
| 基准累计收益率 | 23.26% |
| 超额收益 | 56.45% |
| 最大回撤 | -26.23% |
| 夏普比率 | 0.44 |
| 年化波动率 | 9.19% |
| 日胜率 | 53.10% |
| 总成交笔数 | 408 笔 |
| 累计换手率 | 9702.92% |

解读：行业轮动大幅跑赢沪深300（超额 +56.45%），年化波动仅 9.19%（比 a01 的 14.32% 低），说明"分散到多个行业"确实平滑了波动。但年化收益仅 3.70% 偏低——因为本例是**行业指数轮动**而非个股轮动，赚的是行业间相对强弱（β 层面），且换手率高达 9702% 意味着摩擦成本吃掉不少收益。回撤 -26.23% 优于沪深300 同等暴露。

## 六、改进方向（思考题）

1. **换可交易标的**：把行业指数换成对应的行业 ETF（如 512660 军工、515030 新能源等），让回测真正可落地，消除"指数不可交易"的 gap。
2. **引入估值温度计**：在动量之外叠加行业 PE 分位（`load_index_pe` 或 `value_panel`），"低估 + 高动量"才买入，避免在过热行业接盘。
3. **降低换手**：把月度换成双月调仓，或对调仓名单做"重叠保留"，减少无谓卖出再买入，直接改善高换手吞噬的收益。
