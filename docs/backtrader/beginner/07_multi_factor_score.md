# 策略 7：多因子打分模型（估值 + 质量 + 动量 + 规模）· backtrader 本地版

> **策略类型**：多因子选股（z-score 标准化） ｜ **难度**：★★★★☆ ｜ **前置知识**：知道"标准差""标准化"
> **运行**：`python strategies/backtrader/beginner/bt_s07_multi_factor_score.py` ｜ **聚宽版**：[07_multi_factor_score.md](../../joinquant/beginner/07_multi_factor_score.md)
> **语法底座**：[backtrader详解.md](../../learning/2.库详解/backtrader详解.md) 第 10 章

---

## 一、这一篇你将学到什么

策略 6 用"名次"把两个因子合起来。这一篇换成**z-score（标准化）**，并且一次用四个因子。

| 你会搞懂 | 一句话 |
|---|---|
| z-score 是什么 | "这个值比平均高/低多少个标准差" |
| 名次法 vs z-score | 前者抗极端值，后者保留距离信息 |
| 因子方向用**正负号**表达 | 好因子加号、坏因子减号 |
| 多因子对齐 | 四个因子都要取交集，缺一个就不能入选 |

**读完你应该能回答**：`score = z(roe) - z(pb) + z(mom) - z(mv)` 里，为什么 pb 和 mv 是减号？

---

## 二、心智模型：四个因子，一个分数

```
每月调仓（收盘后）
   │
   ├─ 取四个因子（全部用 asof 切到"今天已知"）：
   │     roe  净资产收益率   → 越高越好  （+）
   │     pb   市净率         → 越低越好  （−）
   │     mom  60 日动量      → 越高越好  （+）
   │     mv   总市值         → 越小越好  （−）
   │
   ├─ 每个因子做横截面 z-score：
   │     z = (值 − 本期所有股票的平均值) ÷ 标准差
   │     → 变成"比平均好/差多少个标准差"，无量纲
   │
   ├─ score = z(roe) − z(pb) + z(mom) − z(mv)
   │
   └─ 取 score 最大的 10 只 → 等权买入 → 次日开盘成交
```

**为什么要标准化？** 因为 ROE 的单位是"%"（常见 10~30），PB 是"倍"（常见 0.5~10），动量是小数（−0.3~0.5）。**直接相加，数值大的因子会独占话语权。** z-score 把四者都变成"标准差倍数"，才可加。

---

## 三、核心思路

**四因子 = 四类经典风格**，这是教科书级的组合：

| 因子 | 代表 | 方向 | 为什么有效（简化） |
|---|---|---|---|
| **质量**（ROE） | "好公司" | + | 赚钱效率高、有护城河 |
| **估值**（PB） | "便宜" | − | 价值溢价、均值回归 |
| **动量**（60 日涨幅） | "强势" | + | 趋势延续 |
| **规模**（总市值） | "小盘" | − | 小市值溢价 |

**z-score 公式**：

$$z_i = \frac{x_i - \bar{x}}{\sigma_x}$$

- $z_i = +2$ → 这个值比平均高 2 个标准差（很突出）
- $z_i = -1$ → 比平均低 1 个标准差

代码里的实现带了一个**除零保护**：

```python
def zscore(s):
    s = pd.Series(s, dtype=float)
    return (s - s.mean()) / (s.std() + 1e-12)     # +1e-12 防止标准差为 0
```

> **为什么要 `+1e-12`**：如果本期所有股票的某个因子值完全相同（标准差 = 0），除法会得到 inf 或 nan，把整个 score 污染。加一个极小的数就能避免——**这是量化代码里非常常见的一个小技巧**。

> **名次 vs z-score 的取舍**：
> - 名次法（策略 6）：把 1000 亿和 1200 亿看成"第 2 名和第 3 名"，差距被抹平 → 抗异常值；
> - z-score（本篇）：保留"差多少"，但对**极端值敏感**（一只股票的 PB 异常小，z 可能是 −8）。
> 实务里常先做**去极值（winsorize）**再标准化，本篇从简。

---

## 四、算法结构

```
main() → load_index_members → load_universe → __CAL__ → run_strategy
   │
   └─ MultiFactorScore.__init__()
         ├─ self.pb  = value_panel(codes, 'pb')
         ├─ self.mv  = value_panel(codes, 'total_mv')
         └─ self.roe = roe_panel(codes, lag_days=ROE_LAG)     ← 财报要滞后 45 天
   │
   └─ 每月 on_rebalance(cur)
         ├─ pb, mv, roe = asof(...)              ← 三张面板各自切到"已知"
         ├─ mom = {代码: 60 日涨幅}               ← 量价因子逐只算
         ├─ common = 四个集合的交集
         ├─ 过滤 pb > 0、mv > 0，再取一次交集
         ├─ score = z(roe) − z(pb) + z(mom) − z(mv)
         └─ 降序取前 10 → equal_weight_order()
```

---

## 五、代码逐段详解

### 5.1 三个面板 + 一个量价因子

```python
ROE_LAG = 45

class MultiFactorScore(PanelStrategy):
    params = (('topn', TOPN), ('lookback', LOOKBACK), ('rebalance', 'monthly'),)

    def __init__(self):
        super().__init__()
        codes = [d._name for d in self.tradables]
        self.pb  = value_panel(codes, 'pb')                  # 估值
        self.mv  = value_panel(codes, 'total_mv')            # 规模
        self.roe = roe_panel(codes, lag_days=ROE_LAG)        # 质量（滞后 45 天）
```

**三个面板 = 三种数据源**：估值/市值来自东财（2018+），财务来自新浪（季度）。它们的时间戳含义不同，所以**每个都要单独 `asof`**。

### 5.2 取数与对齐

```python
def on_rebalance(self, cur):
    pb, mv, roe = asof(self.pb, cur), asof(self.mv, cur), asof(self.roe, cur)
    if pb is None or mv is None or roe is None:
        return

    mom = {}
    for d in self.tradables:
        if not self.live(d, cur):
            continue
        closes = self.hist_close(d, self.p.lookback + 1)
        if closes is None or closes[0] <= 0:
            continue
        mom[d._name] = closes[-1] / closes[0] - 1.0
    mom = pd.Series(mom, dtype=float)

    common = mom.index
    for s in (pb, mv, roe):
        common = common.intersection(s.index)          # 四个集合取交集
    if len(common) < self.p.topn:
        return
    mom, pb, mv, roe = mom[common], pb[common], mv[common], roe[common]

    pb = pb[pb > 0]                                    # 剔除负 PB
    mv = mv[mv > 0]
    common = pb.index.intersection(mv.index)           # 过滤后再对齐一次
    if len(common) < self.p.topn:
        return
    mom, pb, mv, roe = mom[common], pb[common], mv[common], roe[common]
```

**为什么对齐这么麻烦还要做？** 因为四个因子的"可用股票集合"天然不同：
- 某只票可能**刚上市** → 没有 60 日动量；
- 某只票可能**净资产为负** → PB 为负，被过滤；
- 某只票可能**没有财报数据** → ROE 缺失。

**取交集**保证"入选的每只票，四个因子都有值"——否则 score 里会出现 NaN，排序就乱了。

### 5.3 合成与排序

```python
score = (zscore(roe)              # 质量 +（越高越好）
         - zscore(pb)             # 估值 −（越低越好）
         + zscore(mom)            # 动量 +（越高越好）
         - zscore(mv))            # 规模 −（越小越好）
names = score.sort_values(ascending=False).index[:self.p.topn].tolist()
self.equal_weight_order(names, cur)
```

**逐项读一遍**：

| 项 | 含义 | 为什么是加号/减号 |
|---|---|---|
| `+zscore(roe)` | 质量高 → 加分 | ROE 越大越好 |
| `−zscore(pb)` | PB 低 → 加分 | PB 是"越小越好"，取负号后"越小→分越高" |
| `+zscore(mom)` | 涨得多 → 加分 | 动量越大越好 |
| `−zscore(mv)` | 市值小 → 加分 | 市值越小越好 |

因为 score 是"越大越好"，所以最后用 `ascending=False`（**与策略 6 的升序相反**——策略 6 用的是"名次相加、越小越好"）。

---

## 六、一次真实运行的轨迹

```
预加载因子面板（PB / 市值 / ROE）...
[2018-01-02] 开始月度调仓（无打印）
```

加一行诊断就能看见"这一期是谁靠什么入选的"：

```python
print(f'  [{cur}] Top3: {names[:3]}')
print(f'        z(roe)={zscore(roe)[names[0]]:.2f} z(pb)={zscore(pb)[names[0]]:.2f}')
```

---

## 七、与聚宽版的差异

| 维度 | 聚宽 | 本地版 |
|---|---|---|
| 因子来源 | `get_fundamentals`（估值/财务一起取） | 估值走东财、财务走新浪 |
| 财报时效 | 真实公告日 | 报告期 + 45 天近似 |
| 标准化 | `standardize()` 内置函数 | 自己写 `zscore()` |
| 下单 | `order_target_value` | `equal_weight_order` |

---

## 八、回测结果怎么读

| 指标 | 数值 | 怎么理解 |
|---|---|---|
| 累计收益率 | **+295.75%** | 优于单因子（除小市值） |
| 年化收益率 | **+17.74%** | —— |
| 最大回撤 | **−32.38%** | 比纯小市值（−29.58%）略大 |
| 夏普比率 | **0.82** | 优于多数单因子 |
| 成交笔数 | 1278 | 月频 |

**要点**：

1. **多因子的收益/风险比确实优于单因子**（夏普 0.82 vs 单因子 0.36~1.19 的中位）；
2. 但**它仍然没有跑赢纯小市值**（+295% vs +783%）——因为小市值是这段历史里最强的因子；
3. **注意"权重是拍脑袋定的"**：四个因子的系数都是 1，这只是起点。真正的研究要做**因子有效性检验（IC/IR）**——那正是策略 9 要做的事。

---

## 九、易混点与常见错误

| 症状 | 原因 | 正确做法 |
|---|---|---|
| score 里出现 nan | 某个因子有缺失 | 先取交集、再过滤 |
| 某因子完全不起作用 | 没标准化，被大数值因子压制 | 每个因子都 z-score |
| 排序方向反了 | 忘了 score 越大越好 | `ascending=False` |
| 报表数据"未卜先知" | ROE 没做 45 天滞后 | `roe_panel(..., lag_days=45)` |
| `pb` 是负数却入选 | 没过滤 | `pb[pb > 0]` |

---

## 十、自测题（不写代码也能做）

1. 为什么四个因子必须先 z-score 再加总？直接加会怎样？
2. 如果某期所有股票的 ROE 都一样，`zscore` 会返回什么？代码里怎么防的？
3. 为什么"多因子"不一定比"最强的单因子"收益高？那它的价值在哪里？

---

## 十一、改进方向（思考题）

1. **去极值**：先按 1%/99% 分位截断，再标准化，看看极端值的影响。
2. **权重不平均**：用策略 9 的 IC/IR 方法给因子动态赋权。
3. **因子中性化**：先剔除市值/行业暴露，再看"纯因子"的效果（策略 8）。
4. **加约束**：限制单一行业最多 30% 仓位，避免因子把仓位全压在一个行业。