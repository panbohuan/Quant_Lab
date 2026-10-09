# 策略 3：单因子低估值选股（PB）· backtrader 本地版

> **策略类型**：单因子选股（基本面·估值） ｜ **难度**：★★☆☆☆ ｜ **前置知识**：知道"净资产""市值"
> **运行**：`python strategies/backtrader/beginner/bt_s03_value_pe_pb.py` ｜ **聚宽版**：[03_value_pe_pb.md](../../joinquant/beginner/03_value_pe_pb.md)
> **语法底座**：[backtrader详解.md](../../learning/2.库详解/数据分析与量化研究相关库/backtrader详解.md) 第 10 章、第 14 章（btlab 工具层）

---

## 一、这一篇你将学到什么

前两篇用的都是**量价数据**（价格、均线）。这一篇第一次用**基本面数据**，于是多了一个全新的问题：**基本面数据什么时候才算"能用"？**

| 你会搞懂 | 一句话 |
|---|---|
| **面板数据（panel）** | 把多只股票的因子值排成"日期 × 代码"的表格 |
| `value_panel(codes, 'pb')` | btlab 帮你把估值字段拼成面板 |
| `asof(panel, cur)` | **只取不晚于 cur 的最近一期** —— 本篇的核心防未来函数机制 |
| 因子方向 | PB 越低越好，所以排序用**升序** |
| 为什么要剔除负 PB | 净资产为负的公司，"便宜"是假象 |

**读完你应该能回答**：为什么不能直接拿"今天的 PB"给 2019 年的每一天排序？

---

## 二、心智模型：这个策略在时间轴上长什么样

```
每月第一个交易日（收盘后）
   │
   ├─ 1. 取出"截至今天已经公布"的最新一期 PB
   │        （asof：panel.loc[:cur] → 最后一行 → 逐列前向填充）
   │
   ├─ 2. 剔除 PB ≤ 0 的股票（净资产为负，估值指标失去意义）
   │
   ├─ 3. 按 PB 从小到大排序，取最便宜的 10 只
   │
   └─ 4. 等权买入（每只 ≈ 总资产 × 0.98 ÷ 10），次日开盘成交
```

**面板长这样**（`index` 是日期，`columns` 是股票代码）：

| 日期 | 600000 | 600519 | 000002 | … |
|---|---|---|---|---|
| 2020-06-30 | 0.62 | 12.10 | NaN | … |
| 2020-07-01 | 0.63 | 12.35 | 1.05 | … |
| 2020-07-02 | NaN | 12.40 | 1.04 | … |

**注意 2020-07-02 那行的 600000 是 NaN**——这正说明为什么 `asof` 必须做**逐列前向填充**：如果只取"最后一行"，就会把 600000 整只丢掉。

---

## 三、核心思路

**价值溢价（Value Premium）**：长期看，**估值便宜的股票平均收益高于贵的股票**。

**PB（市净率）= 市值 ÷ 净资产**：

$$PB = \frac{\text{总市值}}{\text{净资产}}$$

- PB = 1 → 你花 1 块钱买到了 1 块钱的净资产；
- PB = 0.5 → 打五折买净资产（但市场可能认为这些资产会贬值）；
- PB = 10 → 你花 10 块钱买 1 块钱净资产（通常是高 ROE 的好公司）。

**为什么低 PB 可能跑赢？**

1. **均值回归**：极度悲观的价格终会修复；
2. **安全边际**：净资产提供一定的下行保护；
3. **风格轮动**：价值风格与成长风格交替占优。

**为什么必须剔除负 PB？** 净资产为负意味着**资不抵债**，此时 PB 是负数，"越小越好"会把最危险的公司排到最前面。这是本策略里一个非常典型的**因子清洗**动作。

> **常见误解**：低估 ≠ 一定涨。低 PB 也可能是**价值陷阱**——比如一个夕阳行业的公司，净资产一直在贬值（"便宜"是因为市场预期它会继续变差）。这就是为什么后面的策略 7 会做多因子（加上质量和动量）。

---

## 四、算法结构

```
main()
 ├─ load_index_members('000300')[:40]       取股票池（⚠️ 当前成分股）
 ├─ load_universe(...)                      批量取日线，剔除上市过晚的
 ├─ data['__CAL__'] = 沪深300               日历源
 └─ run_strategy(LowValuation, data, ...)
       │
       └─ LowValuation.__init__()
             └─ self.panel = value_panel(codes, 'pb')     ← 一次预加载整张面板
       │
       └─ 每月 on_rebalance(cur)
             ├─ row = asof(self.panel, cur)               ← 只取 ≤ cur 的最近一期
             ├─ row = row[row > 0]                        ← 剔除负 PB
             ├─ 样本 < 10 只 → 不调仓
             ├─ 升序取前 10（PB 最小 = 最便宜）
             └─ equal_weight_order() → 次日开盘成交
```

---

## 五、代码逐段详解

### 5.1 参数区

```python
START = '2018-01-01'        # 估值数据（东财）约 2018 年起
END = None
CASH = 1_000_000
BENCHMARK = '000300'
UNIVERSE_SIZE = 40
TOPN = 10
FACTOR = 'pb'               # 估值因子列名：'pb'（市净率）或 'pe_ttm'（滚动市盈率）
```

| 参数 | 说明 |
|---|---|
| `START='2018-01-01'` | ⚠️ **不是随便定的**：免费估值数据（东财）大约从 2018 年才有，早于此没有数据 |
| `FACTOR` | 改成 `'pe_ttm'` 就变成"低市盈率策略"——**一行切换一个因子**，这是面板设计的价值 |

### 5.2 `__init__`：一次性预加载面板

```python
class LowValuation(PanelStrategy):
    params = (('topn', TOPN), ('rebalance', 'monthly'),)

    def __init__(self):
        super().__init__()
        codes = [d._name for d in self.tradables]
        print(f'  预加载 {len(codes)} 只股票的 {FACTOR} 面板 ...')
        self.panel = value_panel(codes, FACTOR)
```

| 这一行 | 在做什么 |
|---|---|
| `super().__init__()` | 让 `PanelStrategy` 先把 `self.cal`、`self.tradables` 建好 |
| `codes = [d._name for d in self.tradables]` | 从数据源拿标的代码 |
| `self.panel = value_panel(codes, 'pb')` | 把 38 只股票的 PB 拼成一张"日期 × 代码"的大表 |

> **为什么可以在这里一次性加载整段历史？** 因为 `value_panel` 返回的是普通 pandas 对象，不是 backtrader 的 Line。**关键在于：之后用它时必须用 `asof` 切片，绝不能直接用最后一行。**（如果用最后一行，那就是用"今天的数据"给历史排序——典型未来函数。）

### 5.3 `on_rebalance`：三步选股

```python
def on_rebalance(self, cur):
    row = asof(self.panel, cur)           # ① 只取 <= cur 的最近一期
    if row is None or len(row) < self.p.topn:
        return
    row = row[row > 0]                    # ② 剔除负 PB
    if len(row) < self.p.topn:
        return
    names = [c for c in row.sort_values().index[:self.p.topn]   # ③ 升序 = 最便宜
             if c in self.getdatanames()]
    self.equal_weight_order(names, cur)
```

**① `asof(self.panel, cur)` 到底做了什么？** （本仓库最关键的防未来函数工具）

```python
sub = panel.loc[:pd.Timestamp(cur)]     # 只保留"日期 ≤ 今天"的行
row = sub.ffill().iloc[-1]              # 逐列向前填充 → 取最后一行
return row.dropna()                     # 没数据的新股会被丢掉
```

两层保护：

| 保护 | 作用 |
|---|---|
| `panel.loc[:cur]` | **切掉未来**：cur 之后的估值数据一律看不到 |
| `.ffill()`（逐列前向填充） | **不丢股票**：某只票当天没数据时，用它上一期的值；而不是整只丢掉 |

**② `row[row > 0]`**：剔除 PB ≤ 0。这一步看起来简单，但少了它策略就会去买资不抵债的公司。

**③ `row.sort_values()`**：默认**升序**。PB 越小越靠前 —— 这就是"低估值"。这里 `names` 还做了一个过滤 `if c in self.getdatanames()`，防止面板里出现数据源里没有的股票。

### 5.4 主函数

```python
def main():
    codes = load_index_members('000300')[:UNIVERSE_SIZE]
    data = load_universe(codes, start=START, end=END, adjust='qfq', label='股票池')
    data['__CAL__'] = load_daily(BENCHMARK, start=START, end=END)
    run_strategy(LowValuation, data, cash=CASH, benchmark=BENCHMARK,
                 title=f'策略3 单因子低估值选股（backtrader · 因子={FACTOR}）',
                 plot_path=PLOT)
```

和策略 2 的结构完全一样（取池 → 取日线 → 加日历 → 跑）。**这说明 `PanelStrategy` 已经把"选股类策略的骨架"抽象好了**：换因子策略，只需要换 `on_rebalance` 里那几行。

---

## 六、一次真实运行的轨迹

```
[btlab] 股票池：候选 40 只 → 数据可用 38 只
  预加载 38 只股票的 pb 面板 ...
[3/3] 开始 backtrader 回测 ...
（每月调仓，无打印；净值图存到 results/bt_s03_result.png）
```

如果你想"看见"它在做什么，把 `on_rebalance` 里的 `names` 打印出来：

```python
print(f'  [{cur}] 本期最便宜的 {len(names)} 只：{names[:5]} ...')
# 输出示例： [2020-07-01] 本期最便宜的 10 只：['sh601988', 'sh601288', 'sh600016', ...] ...
```

---

## 七、与聚宽版的差异

| 维度 | 聚宽 | backtrader 本地版 |
|---|---|---|
| 取估值 | `get_fundamentals(query(valuation.pb).filter(...))` | `value_panel(codes, 'pb')`（东财，2018 起） |
| 财报时效 | 平台按公告日返回 | 自己用 `asof(cur)` 切片 |
| 股票池 | 历史成分股 | 当前成分股（幸存者偏差） |
| 调仓 | `run_monthly` + `order_target_value` | `PanelStrategy` + `equal_weight_order` |

---

## 八、回测结果怎么读

区间 2018-01 ~ 2026-09，初始 100 万，基准沪深300：

| 指标 | 数值 | 怎么理解 |
|---|---|---|
| 累计收益率 | **+136.91%** | 明显跑赢基准（+6.61%） |
| 年化收益率 | **+10.78%** | 不错的水平 |
| 最大回撤 | **−33.72%** | 2018 熊市 + 2021 后价值股回调 |
| 夏普比率 | 0.58 | 风险收益比尚可 |
| 成交笔数 | 1067 | 月频调仓，约 8 年 100 次换仓 |

**要点：**

1. **超额收益显著**：+136.91% vs 基准 +6.61%，是"低估值因子在 A 股有效"的一个例证；
2. **但区间特殊**：2018-2026 正好覆盖了 A 股"核心资产 → 价值回归"的风格切换，**换成其他区间结论可能反转**；
3. **样本只有 38 只**（沪深300 前 40 只，剔除 2 只数据不足），且是**当前成分股**——幸存者偏差同样存在，只是比小市值策略弱一些（大盘股退市概率低）。

---

## 九、易混点与常见错误

| 症状 | 原因 | 正确做法 |
|---|---|---|
| 收益高得离谱 | 直接用了面板最后一行（用今天的数据排历史） | **必须** `asof(panel, cur)` 切片 |
| 明明有 40 只，入选的却很少 | `asof` 没做前向填充，某天只有少量股票有值 | btlab 的 `asof` 已用 `.ffill()` 处理 |
| 买到了资不抵债的公司 | 没剔除负 PB | `row = row[row > 0]` |
| 因子方向反了 | 用了 `ascending=False` | 低 PB 好 → **升序** |
| 2017 年跑不出结果 | 估值数据 2018 才有 | `START` 不要早于 2018 |
| 以为 `self.panel` 是 Line | 它是 pandas DataFrame | 用 `asof` 取值，不能 `panel[0]` |

---

## 十、自测题（不写代码也能做）

1. `asof(panel, cur)` 里"两刀"分别切掉了什么？如果只做第一刀会怎样？
2. 为什么要剔除负 PB？如果某公司 PB = −3，它在"升序排序"里会排第几？
3. `value_panel` 和 `roe_panel` 返回的是 Line 还是 pandas 对象？这对写法有什么影响？
4. 为什么本策略的 `START` 定在 2018 年，而不是像策略 1 那样定在 2013 年？

---

## 十一、改进方向（思考题）

1. **换成 PE**：把 `FACTOR` 改成 `'pe_ttm'` 再跑一次，对比两个估值因子的表现差异（PE 对亏损公司不适用，注意过滤）。
2. **估值 + 质量双因子**：低 PB 容易踩"价值陷阱"，加上 ROE 过滤（见策略 7 的多因子打分）。
3. **行业中性化**：银行股天然 PB 低，会占满名单。用行业回归剔除行业影响（见策略 8）。
4. **加安全边际缓冲**：不要"排名一变就调仓"，设置"只有跌出前 15 名才卖"，降低换手。