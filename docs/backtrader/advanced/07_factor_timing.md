# 进阶策略 7：因子择时策略（Factor Timing）· backtrader 本地版

> 类型：因子进阶 / 动态多因子 ｜ 难度：★★★★★ ｜ 前置知识：backtrader 面板数据（asof/value_panel）、z-score、PanelStrategy
> **运行框架：backtrader（本地回测 + 免费数据）** ｜ 本策略的**聚宽云端版**见 [docs/joinquant/advanced/07_factor_timing.md](../../joinquant/advanced/07_factor_timing.md)

## 一、核心思路

前一篇（a07 之前的多因子）用「固定权重」把多个因子合成一个综合分：ROE、低估值、动量、小市值永远按同样比例加权。但因子也有周期——没有永远有效的因子，只有适应环境的因子组合。本策略让因子权重「随行就市」：

- 市场**贵**（估值分位高）→ 防守：超配 ROE / 低估值，砍掉动量；
- 市场**便宜**（估值分位低）→ 进攻：超配动量，降低质量/估值权重；
- 中间地带 → 均衡。

本地的 backtrader 版用「**沪深300 指数 PE 的历史分位**」当市场温度计（乐咕乐股，2005 年起免费）。分位高 = 市场贵 = 风险偏好低。用分位而非绝对值，是因为估值中枢会随时代漂移（比如全市场 ROE 长期下行会让 PE 中枢下移），分位更稳健。

给新手的直觉：估值分位就是「把今天的温度，放到过去十几年的温度计刻度里，看排在第几名」。排到 90% 就是「史上偏贵」，排到 10% 就是「史上偏便宜」。

```
分位 = (历史上 PE < 今日PE 的月份数) / 历史总月数
     pct = float((s < s.iloc[-1]).mean())     # s 为不晚于 cur 的全部 PE 序列
```

## 二、算法结构（分步拆解）

```
每月第 1 个交易日触发 on_rebalance(cur)
   │
   ├─ 1. asof() 取各因子面板「不晚于 cur」的最新一行（PB / 市值 / ROE）
   ├─ 2. 逐标的算动量 mom = closes[-1] / closes[0] - 1.0（回看 LOOKBACK 日）
   ├─ 3. _temperature(cur)：沪深300 PE 截至 cur 的历史分位
   │      └─ 分位 > 70% → 防守；< 30% → 进攻；否则 均衡
   ├─ 4. _weights(pct) 给四因子权重（roe/pb/mom/mv）
   ├─ 5. 截面 z-score 后加权合成 score
   │      score = w_roe·z(roe) - w_pb·z(pb) + w_mom·z(mom) - w_mv·z(mv)
   └─ 6. 取综合分最高的 TOPN 只 → equal_weight_order(names, cur)
```

## 三、代码逐段详解 + backtrader 语法解析

### 3.1 因子面板的预加载（__init__ 里算一次）

```python
def __init__(self):
    super().__init__()
    codes = [d._name for d in self.tradables]
    self.pb  = value_panel(codes, 'pb')          # DataFrame(index=日期, columns=代码)
    self.mv  = value_panel(codes, 'total_mv')
    self.roe = roe_panel(codes, lag_days=ROE_LAG)   # ROE，报告期后移 45 天模拟公告滞后
    self.pe  = load_index_pe('沪深300')             # Series(index=日期)，月度 PE
```

注意：`value_panel` / `roe_panel` / `load_index_pe` 返回的都是**普通 pandas 对象**，不是 backtrader 的 Line。它们在 `__init__` 里一次性加载，之后在 `on_rebalance` 里用 `asof()` 切片——因为财务数据是低频面板，没必要做成逐根递推的 Line（base doc 5.1：Line 用于行情/指标，面板数据用 pandas 更直接）。

`roe_panel` 把报告期后移 `lag_days=45` 天：季报在报告期结束后约 1~1.5 个月才公告，回测中只能用公告后的 ROE，否则是未来函数（base doc 17.2 已说明）。

### 3.2 `asof(panel, cur)` —— 防未来函数的面板切片（重点）

```python
def asof(panel, cur):
    if panel is None or len(panel) == 0:
        return None
    sub = panel.loc[:pd.Timestamp(cur)]     # 只取不晚于 cur 的行
    if len(sub) == 0:
        return None
    return sub.iloc[-1].dropna()            # 最近一行，去掉 NaN
```

`asof` 是本策略防止未来函数的核心：无论 `cur` 是哪天，它都只返回「≤ cur 的最近已公告数据」。若直接取 `panel.iloc[-1]`（整张表最后一行），就会用到回测「未来」的财务数据。`on_rebalance` 里这样用：

```python
pb, mv, roe = asof(self.pb, cur), asof(self.mv, cur), asof(self.roe, cur)
if pb is None or mv is None or roe is None:
    return
```

`asof` 返回的是 `Series(index=代码)`，再用 `pb[pb > 0]` 过滤非法值，最后 `mom.index.intersection(pb.index)...` 取四个因子都有效的代码交集——截面必须「同口径对齐」才能合成分数。

### 3.3 估值分位的计算（不得用未来数据）

```python
def _temperature(self, cur):
    s = self.pe.loc[:pd.Timestamp(cur)].dropna()   # 截至 cur 的全部 PE
    if len(s) < 36:
        return None                                 # 历史不足 3 年不判断
    return float((s < s.iloc[-1]).mean())           # 历史分位
```

这里 `s.iloc[-1]` 是序列最后一行 = **当前最新 PE**（因为已用 `.loc[:cur]` 截断，不含未来）。`(s < s.iloc[-1]).mean()` 即「历史中有多少比例的月份比今天便宜」，得到 0~1 的分位。历史不足 36 个月（乐咕乐股 2005 年起，但某指数可能晚）则返回 `None`，策略退化为均衡权重。

### 3.4 权重 regime 切换

```python
def _weights(self, pct):
    if pct is None:                          return {...1.0...}, '均衡(历史不足)'
    if pct > HIGH_PCT:   return {'roe':1.5,'pb':1.5,'mom':0.3,'mv':0.5}, '高估→防守'
    if pct < LOW_PCT:    return {'roe':0.7,'pb':0.7,'mom':2.0,'mv':1.0}, '低估→进攻'
    return {...1.0...}, '均衡'
```

注意：权重是**相对比例**，不是绝对仓位。动量在进攻时翻倍（2.0）、防守时砍到 0.3；ROE/低估值相反。因子择时的风险就在「判断错」会两边挨打，所以权重变化不宜极端（本策略最大 2.0 倍，没有全砍到 0）。

### 3.5 截面 z-score 合成

```python
score = (w['roe'] * zscore(roe) - w['pb'] * zscore(pb)
         + w['mom'] * zscore(mom) - w['mv'] * zscore(mv))
names = score.sort_values(ascending=False).index[:self.p.topn].tolist()
self.equal_weight_order(names, cur)
```

`zscore` 把每个因子在「当期截面」上标准化（减均值除标准差），消除量纲，再加权求和。低估值（pb）和市值（mv）取负号——pb 越低越好、市值越小越好（小盘溢价）。最后取综合分最高的 TOPN 只等权买入。

### 3.6 关键参数表

| 参数 | 默认 | 含义 |
|------|------|------|
| `UNIVERSE_SIZE` | 40 | 取沪深300前 40 只成分股（注意幸存者偏差） |
| `TOPN` | 10 | 持有股票数 |
| `LOOKBACK` | 60 | 动量回看期 |
| `ROE_LAG` | 45 | ROE 公告滞后天数（防未来） |
| `HIGH_PCT` / `LOW_PCT` | 0.70 / 0.30 | 估值分位阈值 |

### 3.7 backtrader 索引方向速查（防未来函数，必记）

| 写法 | 含义 | 能否在回测中用 |
|------|------|----------------|
| `d.close[0]` | 当根收盘价（Line 索引） | ✅ |
| `d.close[-1]` | 上一根（昨天） | ✅ |
| `d.close[-2]` | 上上根（前天） | ✅ |
| `d.close[1]` | 下一根（明天） | ❌ 未来数据，禁用 |
| `d.close.get(size=n)` 返回的 list | `list[0]`=最旧、`list[-1]`=最新 | ✅（list 语义，与 Line 相反） |

本策略动量用 `closes[-1]/closes[0]-1`（`closes` 是 `hist_close` 返回的 list，`[-1]`=最新）；财务面板用 `asof` 截断。两个易错点：**(1)** `line[1]` 是未来，禁用；**(2)** 首根 K 线 `[-1]` 会绕到数据集末尾（base doc 5.1 危险信号 1），本策略靠 `hist_close` 的 `len(d)<n` 判空挡住。

### 3.8 `asof` 为什么不能换成 `panel.iloc[-1]`

`value_panel` 返回的 DataFrame 是按日期排好的。若直接写 `self.pb.iloc[-1]`，取的是**整张表最后一行** = 回测「最未来」那天的估值——静默用未来数据！`asof(panel, cur)` 先 `panel.loc[:pd.Timestamp(cur)]` 截断到 `cur` 及之前，再取 `.iloc[-1]`，保证只用「已公告」的数据。这是本地回测相对聚宽 `get_fundamentals(date=...)` 最易踩的坑：聚宽按传入日期取快照，本地必须自己截断。

### 3.9 分位数 vs 绝对值：为什么用分位

估值「绝对值」会随时代漂移——比如全市场 ROE 长期下行，PE 中枢也会下移，今天 13 倍可能历史上算贵、二十年前算便宜。`(s < s.iloc[-1]).mean()` 把「今日 PE」放到自身历史里排位，得到 0~1 分位，自动适应中枢漂移。代价是：历史不足 36 个月（乐咕乐股 2005 年起，但某指数可能晚）时分位不可靠，本策略返回 `None` 退化为均衡权重（见 3.3）。

### 3.10 回测时序与因子择时的常见坑

`on_rebalance(cur)` 在当根收盘后被调用，`self.buy/sell` 默认**下一根开盘**成交（base doc 5.6），天然防未来。因子择时的坑：(1) **判断错两边挨打**——误判高估会错过上涨、误判低估会踩跌，所以权重变化不宜极端（本策略最大 2.0 倍）；(2) **ROE 公告滞后**——必须用 `roe_panel(lag_days=45)` 后移，否则用到未公告的财报；(3) **幸存者偏差**——`load_index_members` 返回当前成分，回测用了历史并不存在的龙头（见第四节）。

## 四、与聚宽版的差异

| 维度 | 聚宽版 a07 | backtrader 本地版 |
|------|-----------|-------------------|
| 市场温度计 | **沪深300 年化波动率**（高波动→risk-on） | **沪深300 PE 历史分位**（高分位→防守） |
| 因子源 | `get_fundamentals` 取当期 PE/ROE（当前快照） | `value_panel`/`roe_panel` 面板 + `asof` 截断 + ROE 滞后 45 天 |
| 因子数量 | 3 个（动量/价值/质量） | 4 个（动量/价值/质量/市值） |
| 触发方式 | `run_monthly(rebalance, 1)` | `PanelStrategy` 月度 `on_rebalance` |
| 下单口径 | `order_target_value` | `equal_weight_order` → `round_lot` 整手 |
| 费用/滑点 | `set_order_cost(type='stock')` + `FixedSlippage(0.02)` | `AStockCommission` + `set_slippage_perc(0.0002)` |
| 股票池 | 全量沪深300成分（实时） | 前 40 只（免费源只给当前成分，有幸存者偏差） |

**数据可得性差异（本例特有）**：聚宽用 `get_fundamentals` 直接拿「回测当日」的财务快照，天然带时间点；本地免费源只有「当前」估值/ROE 序列，必须用 `asof` 截断到 `cur` 并给 ROE 加公告滞后，否则会静默用未来财务数据。这是本地回测最易踩的未来函数坑。

> 幸存者偏差提示：`load_index_members('000300')` 返回的是**当前**成分股，不是 2018 年的成分股。回测把「现在的龙头」放进历史，会高估收益（已退市的劣质股被自动剔除）。教学可接受，实盘应取历史成分。

## 五、回测结果（真实数据）

来源：`results/logs/bt_a07_factor_timing.log`（区间 2018-01-02 ~ 2026-09-30，2123 个交易日，初始资金 100 万）。

| 指标 | 数值 |
|------|------|
| 累计收益率 | 208.81% |
| 年化收益率 | 14.32% |
| 最大回撤 | -32.64% |
| 夏普比率 | 0.69 |
| 年化波动率 | 23.36% |
| 基准（沪深300）累计收益 | 6.61% |
| 超额收益 | 202.20% |
| 总成交笔数 | 1318 |
| 累计换手率 | 13576.88% |

解读：因子择时显著跑赢基准（超额 202%），最大回撤 -32.64%、夏普 0.69 均优于纯轮动（a06 夏普仅 0.46）。日志显示 2021 年初、2024-2025 年多次进入「高估→防守」状态，2022-2024 年长期处于「低估→进攻」——说明估值分位确实在切换权重 regime。换手率 13576% 偏高（月频 + 40 只大池），是收益的主要成本。

## 六、改进方向（思考题）

1. **多温度计合成**：把 PE 分位与波动率、股债性价比（ERP）结合，避免单一指标误判。
2. **因子权重平滑**：相邻月份权重突变会放大换手，可对 `w` 做移动平均或加「调仓缓冲」。
3. **缓解幸存者偏差**：若拿到历史成分股列表，应回测「当时」的成分而非当前成分，收益会更接近实盘；也可加止损约束压低 -32% 回撤。
