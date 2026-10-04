# 策略 3：单因子低估值选股（PE / PB）· backtrader 本地版

> 策略类型：单因子选股（基本面·估值因子） ｜ 难度：★★☆☆☆ ｜ 前置知识：策略 2（PanelStrategy/面板）、pandas
> **运行框架：backtrader（本地回测 + 免费数据）** ｜ 本策略的**聚宽云端版**见 [docs/joinquant/beginner/03_value_pe_pb.md](../../joinquant/beginner/03_value_pe_pb.md)

## 一、核心思路：价值投资与估值因子

如果说策略 1 看"趋势"、策略 2 看"过去涨跌"，策略 3 看的是**便宜与否**。价值投资的核心信念是：买入被低估的资产，长期能跑赢市场（"价值溢价"）。

衡量"便宜"最常用的两个估值指标：

$$PE = \frac{\text{股价}}{\text{每股收益}} \quad PB = \frac{\text{股价}}{\text{每股净资产}}$$

- **PE（市盈率）**：你为公司每 1 元盈利付出的价格。PE 越低，回本越快，通常越"便宜"；
- **PB（市净率）**：你为公司每 1 元净资产付出的价格。PB < 1 相当于"打折买账面资产"。

本策略固定用 **PB** 作为估值因子（`FACTOR = 'pb'`，可改 `'pe_ttm'`）：每个月按 PB **升序**取出最便宜的前 `topn` 只，等权持有。

> 给新手的直觉：买东西谁都想"物美价廉"。估值因子就是给所有股票标上"单价"，专挑单价最低的那批长期持有。当然，太便宜也可能有坑（公司快不行了），所以实操要配合质量因子——这就是后面策略 5 与进阶多因子的思路。

**重要提示（幸存者偏差 + 数据降级）**：股票池仍是 `load_index_members('000300')` 的**当前**成分股（幸存者偏差，收益偏高）。此外，本地免费估值源（东方财富）只有 **2018 年起**的日频数据，因此本策略回测起点被设为 `2018-01-01`，这是为贴合数据源能力做的**如实降级**，区间比聚宽版短。

## 二、算法结构（分步拆解）

```
加载数据（main）：
   候选池 = load_index_members('000300') 前 40 只
   逐只 load_universe(...) 取前复权日线（作为交易用的 OHLCV）
   data['__CAL__'] = 基准指数日线（时钟）
        │
LowValuation.__init__（一次）：
   预加载 panel = value_panel(codes, 'pb')   # 面板：index=日期, columns=股票代码
        │
每月调仓日 on_rebalance(cur)：
   ├─ 1. row = asof(panel, cur)   只取"不晚于 cur"的最近一行（防未来函数）
   ├─ 2. row = row[row > 0]       剔除负 PB（净资产为负的异常公司）
   ├─ 3. 样本不足 topn → 本月不调仓
   └─ 4. row.sort_values() 升序取前 topn → equal_weight_order(names, cur)
```

## 三、代码逐段详解 + backtrader 语法解析

### 3.1 引入面板工具

```python
from btlab.runner import (PanelStrategy, run_strategy, load_universe,
                          value_panel, asof)
```

- `value_panel(codes, field='pb')`：把几十只股票的某个估值字段拼成一张**面板** `DataFrame`，`index=日期`、`columns=股票代码`。`field` 可填 `'close'/'total_mv'/'circ_mv'/'pe_ttm'/'pe'/'pb'/'ps'`。底层来自 btlab 的 `load_stock_value`（东方财富）。
- `asof(panel, cur)`：取面板中**不晚于 `cur` 的最近一行**并 `dropna`，返回 `Series(index=代码)`。这是**防未来函数的核心习惯**——面板是按日期对齐的，调仓日只能用"已经公布"的数据，绝不能取 `cur` 之后的行。

### 3.2 `LowValuation(PanelStrategy)` 的 `__init__`

```python
def __init__(self):
    super().__init__()
    codes = [d._name for d in self.tradables]
    self.panel = value_panel(codes, FACTOR)
```

- `super().__init__()`：必须先调父类构造，它才会生成 `self.tradables`（可交易标的列表）和 `self.cal`（日历源）。**不调 `super()`，`self.tradables` 不存在。**
- `codes = [d._name for d in self.tradables]`：取所有可交易标的的名字（代码）作为面板列。
- 把估值面板**预加载一次**存在 `self.panel`，避免在 `next()` 里反复联网取数（面板是静态的，整个回测共用）。

### 3.3 `on_rebalance(cur)` —— 每月选股

```python
def on_rebalance(self, cur):
    row = asof(self.panel, cur)
    if row is None or len(row) < self.p.topn:
        return
    row = row[row > 0]
    if len(row) < self.p.topn:
        return
    names = [c for c in row.sort_values().index[:self.p.topn]
             if c in self.getdatanames()]
    self.equal_weight_order(names, cur)
```

逐行解读：

- `asof(self.panel, cur)`：拿到调仓日及之前最近一行的 PB 估值（每列一只股票）。面板为空或 `cur` 早于所有数据则 `None`。
- `len(row) < topn`：如果当天有估值的股票太少（样本不足），本月不调仓，避免选不出 `topn` 只。
- `row = row[row > 0]`：**剔除负 PB**。PB 为负意味着净资产为负（资不抵债），没有"便宜"的估值意义，必须过滤。
- `row.sort_values()`：pandas 默认**升序**（小→大）。PB 越小越靠前，所以升序取 `[:topn]` 就是"最便宜的 topn 只"。这与策略 2 动量（降序 `reverse=True`）的方向恰好相反——**因子方向是选股策略最容易写反的地方**。
- `if c in self.getdatanames()`：再过滤一遍，确保这只代码确实加载了行情（面板列可能包含没加载日线的票），否则 `equal_weight_order` 里 `getdatabyname` 会找不到。
- `equal_weight_order(names, cur)`：等权调仓（机制见策略 2 的 3.5 节）。

### 3.4 成交时点与索引口径（再强调）

- 本策略仍是"当根收盘后（`next()` 里）判断 → 次日开盘成交"的默认口径，`asof` 把估值数据也严格卡在 `cur` 及以前，所以**因子数据没有未来泄漏**。
- 面板是日频、阶梯式变化（估值每天更新一条），与复权价通过日期索引自然对齐，不需要手算窗口。

### 3.5 面板长什么样（一眼看懂 value_panel 产出）

`value_panel(codes, 'pb')` 返回一张 `DataFrame`，`index=日期`、`columns=股票代码`，值就是该日该股的 PB。示意（已 `dropna` 后的一行）：

```
           600000  600036  600276  ...
2018-01-02   1.02    1.55    8.30  ...
2018-01-03   1.01    1.54    8.41  ...
2018-01-04   1.03    1.56    8.55  ...
...          ...     ...     ...
2026-09-30   0.88    1.42    7.90  ...
```

`asof(panel, cur)` 在这一张表里"横向切一刀"：取 `cur` 及之前**最近一行**，得到 `Series(index=代码, values=PB)`。这行就是当月选股的依据。

### 3.6 asof 的实现细节（为什么它防未来函数）

```python
def asof(panel, cur):
    sub = panel.loc[:pd.Timestamp(cur)]   # 只保留日期 <= cur 的部分
    if len(sub) == 0:
        return None
    return sub.iloc[-1].dropna()          # 取最近一行并剔除缺失
```

- `panel.loc[:Timestamp(cur)]` 是 pandas 的**左闭切片**：索引里所有晚于 `cur` 的行都被切掉，物理上不可能取到未来数据。
- `iloc[-1]` 取剩余部分的最后一行，即"不晚于调仓日的最近估值"。
- `dropna()` 去掉这一行里缺失（NaN）的股票，避免无效代码进入排序。

对比聚宽：`get_fundamentals(q, date=context.current_dt.date())` 由平台保证"只给已披露数据"。两者思路一致——**因子数据绝不能用调仓日之后才公布的值**。

### 3.7 因子方向：升序还是降序（最容易写反）

本策略要"买便宜的"，所以 PB **越小越好**，必须用**升序** `row.sort_values()`（pandas 默认升序）。如果用成降序，就会买入 PB 最高的"贵价股"，逻辑全反：

```python
# 正确：升序，取最便宜的前 topn
names = row.sort_values().index[:topn]
# 错误：descending=True 会选 PB 最高的票，与策略思想相反
names = row.sort_values(ascending=False).index[:topn]
```

估值类因子（PE/PB）都是升序；与之相对，动量（策略 2）、质量 ROE（策略 5）是降序。写选股策略时，**先想清楚因子经济含义，再决定方向**，这是最容易翻车的地方。

### 3.8 常见写错与陷阱

| 写法 | 后果 | 正确做法 |
|------|------|----------|
| 排序方向写反（误用降序） | 买入最贵的票，逻辑相反 | 估值/市值升序、动量/质量降序 |
| 不剔 `row[row>0]` | 负 PB（资不抵债）的票入选 | 先 `row = row[row > 0]` |
| 不用 `asof` 直接取 `panel.loc[cur]` | 可能取到 `cur` 之后才公布的估值（未来函数） | 永远 `asof(panel, cur)` |
| 选股前不校验 `c in self.getdatanames()` | 面板里有但没加载行情 → `getdatabyname` 报错 | 用 `if c in self.getdatanames()` 过滤 |
| 子类漏 `super().__init__()` | `self.tradables` 不存在 | 第一行调 `super().__init__()` |

### 3.9 面板为空 / 数据缺失会怎样

`value_panel` 对某只股票取不到估值时（如东财未收录、上市太晚），会在日志打印 `[跳过] 代码 估值pb: ...`，并把该列整体丢弃。因此面板 `columns` 可能少于候选数，这是正常的——`asof` 取行时只对存在的列排序。若整张面板为空（如把 `FACTOR` 写成了不存在的字段名），`asof` 返回 `None`，`on_rebalance` 直接 `return` 本月不调仓，不会崩溃。这层"软失败"正是面板因子写法稳健的原因：单只票的数据问题不会拖垮整个回测。

### 3.10 换因子只改一行

想把估值因子从 PB 切到 PE，只需把文件顶部的 `FACTOR = 'pb'` 改成 `FACTOR = 'pe_ttm'`（滚动市盈率），其余代码一行不动。`value_panel` 会自动去取对应字段，`on_rebalance` 仍按"升序取最便宜的前 topn"工作。注意不同估值字段都可能出现负值（亏损股 PE 为负、资不抵债 PB 为负），统一靠 `row[row > 0]` 过滤，无需为每种因子单独写判断——这也是把"因子名"参数化带来的好处。

### 3.11 估值因子在牛熊中的表现差异（读结果时要知道）

低估值（价值）因子的有效性是**周期性**的，不是每年都赢：在价值风格占优的年份（如 2014、2019 初、2022~2023）它显著跑赢；在"核心资产/成长股抱团"的年份（2020~2021）它反而跑输高估值成长。本策略回测区间恰好处在价值因子相对有效的后半段，所以累计 136.91% 看着漂亮——但若把起点拉到 2019 年，结论会打折。理解这点能避免你把"某段区间的好结果"外推成"永远有效"，这也是基本面量化最容易被忽视的陷阱。

### 3.12 本策略绩效从哪来（与策略 1 同源）

本策略不自己算绩效——`run_strategy` 用 `NavRecorder`（逐日账户总值）得到净值序列，再用 `bt.analyzers.Transactions` 汇总成交笔数与累计成交额。日志里的"累计换手率 3239.15%" =（所有成交金额之和）/ 初始资金 100 万。月频换 10 只、每只平均持有约 1 个月，这个换手率在选股策略里属于中等，比动量（16828%）低得多，因为估值因子换手天然比动量慢——估值变化是日频但信号稳定，不需要频繁调仓。

## 四、与聚宽版的差异

| 维度 | 聚宽版（云端） | backtrader 本地版 |
|------|----------------|-------------------|
| 取估值 | `query(valuation.pb_ratio).filter(...).order_by(pe_ratio.asc())` + `get_fundamentals` | `value_panel(codes,'pb')` 拼面板 + `asof` 取行 |
| 股票池 | `get_all_securities(['stock'])` 全市场 | `load_index_members('000300')` 当前成分（幸存者偏差） |
| 数据时点 | 任意历史时点都有估值 | 仅 2018 年起，区间被缩短（降级） |
| 索引设置 | `df.set_index('code')` 让索引变代码 | 面板 `columns` 本就是代码，无需此步 |
| 过滤 | `df[df[factor]>0]` 剔除负估值 | `row[row > 0]` 同样剔除负 PB |
| 下单 | `order_target_value` 等权 | `equal_weight_order` 按整手股数 |
| 负向过滤 | `filter_stocks` 六道过滤（ST/停牌等） | 仅 `live()` 跳过停牌 |

思路（低估值升序选股）完全一致。差异集中在：① 估值数据源从"平台实时库"换成"本地免费面板 + asof 防未来函数"；② 股票池与数据区间因免费源受限而降级。这些都不改变因子本身的逻辑。

## 五、回测结果（真实数据）

回测区间 **2018-01-02 ~ 2026-09-30**（2123 个交易日），初始资金 100 万元，沪深300成分股前 40 只、月频调仓、PB 升序选前 10 只，基准沪深300指数：

| 指标 | 数值 |
|------|------|
| 累计收益率 | 136.91% |
| 年化收益率 | 10.78% |
| 最大回撤 | -33.72% |
| 夏普比率 | 0.58 |
| 基准累计收益率 | 6.61% |
| 超额收益 | 130.30% |
| 总成交笔数 | 1067 |
| 累计换手率 | 3239.15% |

**解读（仅基于上表真实数字）：** 低估值（PB）因子在这段区间表现出很强的"价值溢价"——累计 136.91%、年化 10.78%，大幅跑赢同期几乎躺平的沪深300（基准仅 +6.61%，超额 +130.30%）。同时它的回撤（-33.72%）比策略 2 动量（-49.75%）更克制，夏普 0.58 也更稳健，说明"买便宜"在 A 股宽基成分股里是相对有效的防御性因子。仍要记住两点：① 股票池是**当前**沪深300成分（幸存者偏差，偏高）；② 估值因子在 2020~2021 的"核心资产抱团"行情里一度跑输高估值成长股，价值因子的有效性是**周期性**的，不是每年都赢。

## 六、改进方向（思考题）

1. **因子组合**：把 PE 与 PB 合成综合估值分（如等权 z-score），或叠加 ROE 做"便宜的好公司"（见策略 5 与进阶多因子），规避单纯低 PB 里"便宜是因为快退市"的陷阱。
2. **行业中性化**：不同行业 PB 天然不可比（银行 PB 永远低），可用 btlab 的 `industry_map` 在行业内做相对排序，消除行业偏差。
3. **加估值极端值过滤与止损**：剔除 PB 异常低（如资不抵债边缘）的票，配合 `buy_bracket` 止损，进一步压低回撤；也可对比 `'pe_ttm'` 因子看哪个估值口径更优。
