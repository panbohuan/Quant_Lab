# 策略 6：双因子组合（动量 + 市值，排序打分法）· backtrader 本地版

> **策略类型**：双因子选股（量价 + 规模） ｜ **难度**：★★★☆☆ ｜ **前置知识**：理解"排名"
> **运行**：`python strategies/backtrader/beginner/bt_s06_two_factor_rank.py` ｜ **聚宽版**：[06_two_factor_rank.md](../../joinquant/beginner/06_two_factor_rank.md)
> **语法底座**：[backtrader详解.md](../../learning/2.库详解/数据分析与量化研究相关库/backtrader详解.md) 第 10 章

---

## 一、这一篇你将学到什么

前五篇都是**单因子**：只看一个指标排序。这一篇第一次把**两个因子合成一个分数**。

| 你会搞懂 | 一句话 |
|---|---|
| 为什么需要多因子 | 单因子暴露太集中，容易被单一风格打爆 |
| **排序打分法（rank）** | 把不同量纲的因子都换成"名次"，再相加 |
| 方向怎么处理 | 动量要"越大越好"，市值要"越小越好"——用符号解决 |
| 交集对齐 | 两个因子的股票集合要先取交集 |

**读完你应该能回答**：`score = (-mom).rank() + mv.rank()` 里那个负号是干什么的？

---

## 二、心智模型：这个策略在时间轴上长什么样

```
每月调仓（收盘后）
   │
   ├─ 因子 A（动量）：取每只票过去 60 日涨幅 → 排名
   │     涨幅越大 → 名次越小（第 1 名是最好的）
   │
   ├─ 因子 B（市值）：取每只票最近一期总市值 → 排名
   │     市值越小 → 名次越小（第 1 名是最好的）
   │
   ├─ 合成：score = 动量名次 + 市值名次
   │     两者都好的股票，score 最小
   │
   └─ 取 score 最小的 10 只 → 等权买入 → 次日开盘成交
```

**为什么"名次相加"能工作？** 因为名次是**无量纲**的：动量的单位是"百分比"，市值的单位是"亿元"，直接相加没有意义；换成"第几名"以后，两者就都变成 1,2,3,… 可以相加了。

---

## 三、核心思路

**多因子的动机**：任何单因子都有"失灵期"。

| 只买 | 什么时候会很难受 |
|---|---|
| 动量 | 风格反转时（前期涨最多的跌最狠） |
| 小市值 | 大盘蓝筹行情时（2017、2020） |
| 低估值 | 成长股泡沫时 |

**两个因子一起用**，只要它们**不同时失灵**，组合的波动就会下降。

**本策略选的两个因子**：

- **动量（60 日涨幅）**：趋势延续性 → 越大越好
- **市值（总市值）**：小市值溢价 → 越小越好

**打分方法：排序打分（rank）**

$$score = rank(-\text{动量}) + rank(\text{市值})$$

- `(-mom).rank()`：动量越大 → 取负后越小 → 名次越靠前（第 1 名 = 动量最强）
- `mv.rank()`：市值越小 → 名次越靠前（第 1 名 = 市值最小）
- `score` 越小越好 → 取 `sort_values()` 升序的前 10

> **和下一篇的区别**：本篇用**名次**（相对排序），策略 7 用 **z-score**（标准化数值）。名次法更"抗极端值"（一个异常大的值也只占第 1 名），z-score 保留了距离信息。两种都常用。

---

## 四、算法结构

```
main() → load_index_members → load_universe → __CAL__ → run_strategy
   │
   └─ TwoFactorRank.__init__()
         └─ self.mv = value_panel(codes, 'total_mv')      ← 只需要市值面板
   │
   └─ 每月 on_rebalance(cur)
         ├─ mv = asof(self.mv, cur)                        ← 取已公布市值
         ├─ mom = {代码: 60 日涨幅}（用 hist_close 逐只算）
         ├─ common = 动量集合 ∩ 市值>0 的集合                ← 对齐
         ├─ 样本 < 10 → 不调仓
         ├─ score = (-mom).rank() + mv.rank()
         └─ 升序取前 10 → equal_weight_order()
```

---

## 五、代码逐段详解

### 5.1 参数与面板

```python
UNIVERSE_SIZE = 40
TOPN = 10
LOOKBACK = 60               # 动量回看期

class TwoFactorRank(PanelStrategy):
    params = (('topn', TOPN), ('lookback', LOOKBACK), ('rebalance', 'monthly'),)

    def __init__(self):
        super().__init__()
        codes = [d._name for d in self.tradables]
        self.mv = value_panel(codes, 'total_mv')       # 只需要一张面板
```

### 5.2 `on_rebalance`：取数 → 对齐 → 打分

```python
def on_rebalance(self, cur):
    mv = asof(self.mv, cur)                       # ① 市值（防未来）
    if mv is None:
        return

    mom = {}                                      # ② 动量（逐只算）
    for d in self.tradables:
        if not self.live(d, cur):
            continue
        closes = self.hist_close(d, self.p.lookback + 1)
        if closes is None or closes[0] <= 0:
            continue
        mom[d._name] = closes[-1] / closes[0] - 1.0
    mom = pd.Series(mom, dtype=float)

    common = mom.index.intersection(mv[mv > 0].index)   # ③ 取交集
    if len(common) < self.p.topn:
        return
    mom, mv = mom[common], mv[common]

    score = (-mom).rank() + mv.rank()             # ④ 排序打分
    names = score.sort_values().index[:self.p.topn].tolist()
    self.equal_weight_order(names, cur)
```

| 步骤 | 为什么这么做 |
|---|---|
| ① `asof` | 市值是基本面数据，必须"只取已公布的最近一期" |
| ② `hist_close(d, lookback+1)` | 动量是量价数据，逐只用 Line 取（**返回 array，`[-1]` 是最新**） |
| ③ `intersection` | 必须对齐：某只票有动量但没市值（或者停牌）就不能参与打分 |
| ④ `(-mom).rank() + mv.rank()` | 见下 |

**④ 那个负号到底在干什么？** 用一张表说清（假设只有 4 只票）：

| 股票 | 60 日涨幅 | `(-mom).rank()` | 总市值 | `mv.rank()` | score |
|---|---|---|---|---|---|
| A | +30% | **1**（动量最强） | 800 亿 | 3 | 4 |
| B | +5% | 3 | 200 亿 | **1**（市值最小） | 4 |
| C | −10% | 4 | 120 亿 | **1**（并列最小） | 5 |
| D | +18% | **2** | 1500 亿 | 4 | 6 |

- `(-mom).rank()`：先取负再排名 → **涨幅越大，名次数字越小**
- `mv.rank()`：默认升序 → **市值越小，名次数字越小**
- 两者相加 → **score 越小 = 两个因子都越靠前**

最终 A、B 并列 4 分，会被优先选中。

> **为什么不用 `mom.rank(ascending=False)`？** 效果一样，但 `(-mom).rank()` 更直观地表达了"我要把方向翻转过来"。两种写法都可以，选一种并在注释里写清楚。

---

## 六、一次真实运行的轨迹

```
[btlab] 股票池：候选 40 只 → 数据可用 38 只
（每月调仓，无打印）
```

想看清它在选什么，加一行：

```python
print(f'  [{cur}] 入选：'
      f'{[f"{c}(动量{mom[c]:+.1%},市值{mv[c]/1e8:.0f}亿)" for c in names[:3]]} ...')
# → [2020-07-01] 入选：['sz300124(动量+42.1%,市值620亿)', ...] ...
```

---

## 七、与聚宽版的差异

| 维度 | 聚宽 | 本地版 |
|---|---|---|
| 动量 | `attribute_history(sec, 61, '1d', 'close')` 自己算 | `hist_close(d, 61)`（内部 `close.get(size=61)`） |
| 市值 | `get_fundamentals(query(valuation.market_cap))` | `value_panel(codes,'total_mv')` |
| 打分 | pandas `rank()` | 同样是 pandas `rank()` |
| 股票池 | 历史成分股 | 当前成分股（幸存者偏差） |

**注意**：聚宽版用 `get_fundamentals` 能拿到**历史时点**的市值；本地免费源只有"某日估值表"，所以必须靠 `asof` 切片。

---

## 八、回测结果怎么读

| 指标 | 数值 | 怎么理解 |
|---|---|---|
| 累计收益率 | **+783.63%** | 全场最高 |
| 年化收益率 | **+29.52%** | —— |
| 最大回撤 | **−26.40%** | 比纯小市值（−29.58%）**还小** |
| 夏普比率 | **1.17** | 与纯小市值接近 |
| 成交笔数 | 1210 | 月频 |

**为什么"动量 + 小市值"能同时提高收益、降低回撤？**

1. **小市值贡献收益**（本仓库里小市值是最强的单因子）；
2. **动量做了"择时"**：在小市值股票里，只买**最近还在涨**的那些，避开了正在下跌的小盘股；
3. 两个因子的相关性不高，**组合的波动被摊薄**。

> **但要冷静**：收益 +783% 里，**大部分仍然来自"小市值"这个已被证明最不可信的因子**（见策略 4）。这一篇真正的知识点是**"多因子怎么合成"**，不是这串数字。

---

## 九、易混点与常见错误

| 症状 | 原因 | 正确做法 |
|---|---|---|
| 选了动量最差的股票 | 忘了取负 | `(-mom).rank()` 或 `mom.rank(ascending=False)` |
| 报错 `KeyError` / 索引对不齐 | 两个因子的股票集合不同 | 先 `index.intersection()` 取交集 |
| `score` 里有 NaN | 某个因子缺值 | 先过滤（`mv[mv>0]`）再取交集 |
| 以为 rank 后数字越大越好 | 名次越小越靠前 | 取 `sort_values()` **升序**的前 N |
| 忘了 `asof` | 用了未来市值 | 基本面数据一律先 `asof` |

---

## 十、自测题（不写代码也能做）

1. 为什么要把两个因子换成"名次"再相加，而不是直接相加？
2. 如果两个因子高度相关（比如"市值"和"流通市值"），多因子组合还有意义吗？
3. `(-mom).rank() + mv.rank()` 与 `mv.rank() - mom.rank()` 等价吗？为什么？

---

## 十一、改进方向（思考题）

1. **换因子**：把市值换成 PB（`value_panel(codes,'pb')`），做"动量 + 低估值"。
2. **加权**：`score = 1.5*(-mom).rank() + mv.rank()`，让动量占更大权重，观察结果变化。
3. **加第三个因子**：再叠加 ROE（见策略 7），但要注意因子越多、越容易过拟合。
4. **去极值**：先用分位数截断（winsorize）再排名，看看对极端值是否更稳健。