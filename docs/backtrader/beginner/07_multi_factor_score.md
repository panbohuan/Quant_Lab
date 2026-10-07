# 策略 7：多因子打分模型（Multi-Factor Score）· backtrader 本地版

> 策略类型：多因子选股（z-score 标准化 + 线性加权） ｜ 难度：★★★★☆ ｜ 前置知识：策略 6 的排名法、z-score、pandas 对齐
> **运行框架：backtrader（本地回测 + 免费数据）** ｜ 本策略的**聚宽云端版**见 [docs/joinquant/beginner/s07_multi_factor_score.md](../../joinquant/beginner/07_multi_factor_score.md)

## 一、核心思路

把经典因子归纳为四大类（Barra 等模型的底层逻辑），各取一个代表合成综合分，选"又好又便宜、趋势向上且盘子不大"的股票：

| 大类 | 代表因子 | 方向 | 含义 |
|------|----------|------|------|
| 质量 Quality | ROE | 越高越好 | 赚钱能力强 |
| 估值 Value | PB | 越低越好 | 便宜 |
| 动量 Momentum | 60 日涨幅 | 越高越好 | 趋势强 |
| 规模 Size | 总市值 | 越小越好 | 小盘溢价 |

**为什么从策略 6 的"排名法"升级到"打分法"**：排名法只保留"先后"信息，丢掉"领先多少"。z-score 标准化把每个因子变成"均值 0、标准差 1"的标准分布，既统一量纲、又保留幅度：

$$z = \frac{x - \mu}{\sigma}$$

转换后 `z = 1.5` 表示"比平均高 1.5 个标准差"，因子间可直接相加。

综合分按方向加权：

$$score = z(ROE) - z(PB) + z(动量) - z(市值)$$

负号即"越小越好"。选 `score` 最高的 TOPN 只等权持有。

> 给新手的直觉：四个裁判给每个选手打分（都按"标准差"换算成统一尺度），质量裁判的加分、估值裁判的减分……最后总分最高的人入选。z-score 让"ROE 15%"和"市值 200 亿"这种风马牛不相及的数字能放在同一个算式里。

## 二、算法结构（分步拆解）

```
每月首个交易日触发 on_rebalance(cur)
   │
   ├─ 1. 取三个基本面面板快照（严格 ≤ cur）
   │      ├─ asof(self.pb, cur)   → PB（市净率）
   │      ├─ asof(self.mv, cur)   → 总市值
   │      └─ asof(self.roe, cur)  → ROE（lag_days=45 模拟公告滞后）
   │
   ├─ 2. 算动量因子（量价类，来自行情）
   │      └─ self.hist_close(d, lookback+1) → closes[-1]/closes[0]-1
   │
   ├─ 3. 四因子对齐到共同股票集合（多次 intersection + 剔除 PB/市值≤0）
   │
   ├─ 4. z-score 标准化 + 按方向加权合成 score
   │
   └─ 5. equal_weight_order(score 最高的前 TOPN 只, cur)
```

## 三、代码逐段详解 + backtrader 语法解析

### 3.1 预加载三张面板

```python
class MultiFactorScore(PanelStrategy):
    params = (('topn', TOPN), ('lookback', LOOKBACK), ('rebalance', 'monthly'),)

    def __init__(self):
        super().__init__()
        codes = [d._name for d in self.tradables]
        self.pb = value_panel(codes, 'pb')
        self.mv = value_panel(codes, 'total_mv')
        self.roe = roe_panel(codes, lag_days=ROE_LAG)
```

四个因子来自两套数据源：

- **行情类（动量）**：每根 K 线实时算，来自 backtrader 数据源 `self.hist_close`。
- **基本面类（PB / 市值 / ROE）**：用 `value_panel` / `roe_panel` 在 `__init__` 一次性预拼成面板，调仓时切片。

关键差异在于 **`roe_panel(codes, lag_days=45)`**：季报在报告期结束后约 1~1.5 个月才公告，本地免费源只有"报告期"没有"公告日"。`roe_panel`（§14.2）把 ROE 序列的索引整体后移 45 天（`s.index = s.index + pd.Timedelta(days=lag_days)`），模拟"公告之后才能用"的约束——**这是本地版防未来函数的关键一步**，否则会提前用上还没发布的财报。

### 3.2 z-score 工具函数

```python
def zscore(s):
    s = pd.Series(s, dtype=float)
    return (s - s.mean()) / (s.std() + 1e-12)
```

分母 `+ 1e-12` 防止某因子所有值相等、标准差为 0 时除零报错（浮点保护，详见 `backtrader详解` §15 思路）。

### 3.3 `on_rebalance`：四因子合成

**(1) 面板快照——`asof` 逐张切片**

```python
pb, mv, roe = asof(self.pb, cur), asof(self.mv, cur), asof(self.roe, cur)
if pb is None or mv is None or roe is None:
    return
```

三张面板各自 `asof(cur)`，确保都不晚于当天。注意 `asof` 内部 `iloc[-1]` 取的是**面板行**（按日期排序的 DataFrame 行），这是 pandas 行索引语义，与 Line 的 `[0]/[-1]` 无关，不要混淆。

**(2) 动量因子**

```python
mom = {}
for d in self.tradables:
    if not self.live(d, cur):
        continue
    closes = self.hist_close(d, self.p.lookback + 1)   # list，含今日
    if closes is None or closes[0] <= 0:
        continue
    mom[d._name] = closes[-1] / closes[0] - 1.0         # list[-1]=最新
mom = pd.Series(mom, dtype=float)
```

`closes` 是 `array.array`（不是 Python list），`closes[-1]` 是**最新收盘**（今天）、`closes[0]` 是最旧（60 天前）。这里绝不能用 Line 的 `close[1]`（那是明天）。`hist_close` 已用 `len(d) < n` 守卫，只返回已走完的 K 线。

**(3) 四因子对齐**

```python
common = mom.index
for s in (pb, mv, roe):
    common = common.intersection(s.index)
if len(common) < self.p.topn:
    return
mom, pb, mv, roe = mom[common], pb[common], mv[common], roe[common]
pb = pb[pb > 0]
mv = mv[mv > 0]
common = pb.index.intersection(mv.index)
if len(common) < self.p.topn:
    return
mom, pb, mv, roe = mom[common], pb[common], mv[common], roe[common]
```

先求四者的并集交集，再分别剔除 PB≤0、市值≤0 的脏数据，二次交集。**对齐必须用 `index.intersection`**，因为动量来自行情（含今日）、基本面来自面板（公告滞后），股票集合天然不完全一致。

**(4) 标准化 + 方向加权**

```python
score = (zscore(roe)             # 质量 +
         - zscore(pb)            # 估值 -
         + zscore(mom)           # 动量 +
         - zscore(mv))           # 规模 -
names = score.sort_values(ascending=False).index[:self.p.topn].tolist()
self.equal_weight_order(names, cur)
```

四个 z-score 按方向带正负号相加，降序取前 TOPN。`equal_weight_order` 的先卖后买、整手取整、`cap=0.98` 缓冲逻辑与策略 6 完全一致（§三 / `backtrader详解` §9.1、§9.4）。

### 3.4 防未来函数的三道闸门

1. **`asof(panel, cur)`**：三张基本面面板只取 `≤ cur` 的行，且 `roe_panel` 已后移 45 天；
2. **`hist_close` 的长度守卫**：动量只用已收盘的 K 线；
3. **backtrader 默认成交时点**（§9.1）：`on_rebalance` 在当根收盘后触发，订单**次日开盘**成交，信号不回踩未来。

### 3.5 `PanelStrategy` 的月份调度与 `__CAL__` 时钟

"每月触发一次"由骨架完成，原理与策略 6 一致（`runner.py`）：

```python
def next(self):
    cur = self.cal.datetime.date(0)
    key = (cur.year, cur.month) if self.p.rebalance == 'monthly' else cur
    if key == self._last_key:
        return
    self._last_key = key
    self.on_rebalance(cur)
```

`self.cal` 来自喂入的 `__CAL__` 基准指数（每个交易日有行情），当"日历时钟"避免停牌股导致日期错乱。`rebalance='monthly'` 时 key 取 `(年, 月)`，跨月才触发一次 `on_rebalance`。本策略因四个因子都要 `asof(cur)` 切片，对"cur 是哪一天"的依赖比单因子更强——时钟的准确直接决定 `asof` 切得对不对，进而决定有没有未来函数。同样，`next()` 收盘后调用、订单次日开盘成交，自动免疫未来数据。

## 四、与聚宽版的差异

| 维度 | 聚宽云端版（s07） | backtrader 本地版（bt_s07） |
|------|-------------------|------------------------------|
| 触发方式 | `run_monthly(rebalance, 1, time='09:30')` | `PanelStrategy` 月份变化 → `on_rebalance(cur)` |
| 基本面来源 | `get_fundamentals(query(valuation.pb_ratio, market_cap, indicator.roe))`，一次性 join 两张表 | `value_panel('pb'/'total_mv')` + `roe_panel(lag_days=45)` 三张独立面板，各自 `asof` 切片 |
| 股票池 | `get_all_securities` 全市场 + 过滤 | `load_index_members('000300')[:40]` 当前前 40 只 |
| ROE 时效 | 云端实时财报 | `lag_days=45` 模拟公告滞后（本地必要） |
| 下单口径 | `order_target_value` 按金额 | `equal_weight_order` 整手股数再平衡 |
| 数据局限 | 无 | 免费估值源约 2018 年起；当前成分股 → 幸存者偏差 |

**与策略 6 的进步**：聚宽版直接用 `get_fundamentals` 一次查回 PB/市值/ROE，本地版因数据分散在三张面板、且 ROE 要模拟公告滞后，必须分三次 `asof` 再交集——这正是"免费源换云端源"要额外付出的工程成本。

## 五、回测结果（真实数据）

数据来源：`results/logs/bt_s07_multi_factor_score.log`（本地实跑，未编造）。

| 指标 | 数值 |
|------|------|
| 回测区间 | 2018-01-02 ~ 2026-09-30（2123 个交易日） |
| 初始 / 期末资金 | 100 万 → 3,957,500 元 |
| 累计收益率 | +295.75% |
| 年化收益率 | 17.74% |
| 基准（沪深300）累计 | +6.61% |
| 超额收益 | +289.14% |
| 最大回撤 | -32.38% |
| 夏普比率 | 0.82 |
| 年化波动率 | 23.32% |
| 日胜率 | 52.08% |
| 总成交笔数 | 1278 |
| 累计换手率 | 14809.62% |

**解读**：四因子 z-score 打分年化 17.7%，跑赢基准但明显低于策略 6 的双因子排名法（年化 29.5%）。原因有二：一是引入了 ROE/估值这类"质量+价值"因子拉低了整体波动与弹性；二是等权合成隐含"四因子同等重要"，而实际各因子有效性差异巨大（见策略 9）。最大回撤 -32% 比策略 6 略深，说明多因子并未显著降低尾部风险。

## 六、改进方向（思考题）

1. **因子加权**：等权合成不合理，改用历史 IC/IR 动态赋权（见策略 9）。
2. **去极值**：z-score 对极端值敏感，一个超大离群值会拉偏均值/标准差，应做 `Winsorize` 分位截尾。
3. **因子中性化**：PB 与市值高度相关，简单相加会重复计权，可参考策略 8 做行业/市值中性化提纯。
