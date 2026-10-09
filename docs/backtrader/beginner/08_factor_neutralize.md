# 策略 8：因子中性化（市值 + 行业中性）· backtrader 本地版

> **策略类型**：多因子进阶（因子提纯） ｜ **难度**：★★★★☆ ｜ **前置知识**：知道"回归""残差"（不熟也能读：本篇会把直觉讲清楚）
> **运行**：`python strategies/backtrader/beginner/bt_s08_factor_neutralize.py` ｜ **聚宽版**：[08_factor_neutralize.md](../../joinquant/beginner/08_factor_neutralize.md)
> **语法底座**：[backtrader详解.md](../../learning/2.库详解/数据分析与量化研究相关库/backtrader详解.md) 第 10 章、第 14 章

---

## 一、这一篇你将学到什么

策略 7 的"动量因子"里，其实**混着市值和行业的影响**。这一篇要把它们**剥离出去**，得到"纯动量"。

| 你会搞懂 | 一句话 |
|---|---|
| 什么是**因子暴露** | 你的因子分数里，掺了多少"别的东西" |
| **截面回归取残差** | 用回归把"能解释的部分"扣掉，剩下的就是"纯因子" |
| 行业**虚拟变量**（dummy） | 把"行业"这种文字分类变成 0/1 数值 |
| `industry_map()` | btlab 提供的"股票 → 申万一级行业"映射 |

**读完你应该能回答**：为什么"动量最强的股票"里往往有一堆小盘股？这算不算动量因子本身厉害？

---

## 二、心智模型：把"混进来的东西"减掉

假设你想研究"动量到底有没有用"，于是按 60 日涨幅排序买了前 10 名。结果发现：

```
入选的 10 只里，有 8 只是小盘股、5 只是同一个行业（比如半导体）
        │
        ├─ 你赚的钱，可能来自"小市值溢价"，而不是"动量"
        └─ 也可能来自"行业 beta"（半导体集体上涨），而不是"选股"
```

**中性化就是**：先用回归算出"如果只看市值和行业，这只股票的动量应该是多少"，再拿**真实动量减去这个预测值**：

```
残差 = 真实动量 − 用(市值, 行业)能解释的动量
     = 剔除市值/行业影响之后的"纯动量"
```

```
每月调仓（收盘后）
   │
   ├─ 1. 算每只票的 60 日动量
   ├─ 2. 准备两个"解释变量"：log(总市值)、申万一级行业
   ├─ 3. 做一次截面回归：动量 ~ logmv + 行业哑变量
   ├─ 4. 取回归残差 = 纯动量
   └─ 5. 按纯动量降序取前 10 → 等权买入 → 次日开盘成交
```

---

## 三、核心思路

**为什么要中性化？** 因为因子之间天然相关：

| 现象 | 混进来的东西 |
|---|---|
| 动量强的股票常常是小盘股 | **市值暴露** |
| 某个行业整体上涨时，行业内所有股票动量都高 | **行业暴露** |

如果不剥离，你**无法判断到底是谁在起作用**——更危险的是，你可能以为找到了"alpha"，其实只是承担了已知的 beta。

**用回归的语言说**：

$$momentum_i = \alpha + \beta \cdot \log(mv_i) + \sum_k \gamma_k \cdot industry_{k,i} + \varepsilon_i$$

其中 $\varepsilon_i$（残差）就是"市值和行业解释不了的那部分动量"。**我们买残差最大的股票**。

> **直觉类比**：班里两个学生都考了 90 分。A 上了补习班、家里有家教；B 全靠自己。你更欣赏谁？**中性化就是"把补习班的加成扣掉"再看谁更厉害。**

---

## 四、算法结构

```
main() → load_index_members → load_universe → __CAL__ → run_strategy
   │
   └─ FactorNeutralize.__init__()
         ├─ self.mv = value_panel(codes, 'total_mv')      ← 市值面板
         └─ self.ind_map = industry_map(codes)            ← 股票→行业
   │
   └─ 每月 on_rebalance(cur)
         ├─ mv = asof(self.mv, cur)，取 log
         ├─ mom = {代码: 60 日涨幅}
         ├─ common = 动量 ∩ 市值 的股票
         ├─ ind = {代码: 行业名}（缺失归入"未知"）
         ├─ pure = neutralize(mom, logmv=log(mv), industry=ind)   ← OLS 残差
         └─ 纯动量降序取前 10 → equal_weight_order()
```

---

## 五、代码逐段详解

### 5.1 中性化函数 `neutralize`（本篇核心）

```python
import statsmodels.api as sm

def neutralize(factor, logmv=None, industry=None):
    """对 factor 做截面回归取残差。logmv / industry 为 None 表示不中性化该维度。"""
    y = pd.Series(factor, dtype=float)              # 被解释变量：动量
    X = pd.DataFrame(index=y.index)                 # 解释变量矩阵

    if logmv is not None:
        X['logmv'] = pd.Series(logmv, dtype=float).reindex(y.index)
    if industry is not None:
        ind = pd.Series(industry).reindex(y.index).fillna('未知')
        dummies = pd.get_dummies(ind, prefix='ind', drop_first=True)   # 行业→0/1
        X = pd.concat([X, dummies.astype(float)], axis=1)

    if X.shape[1] == 0:
        return y - y.mean()                         # 没有解释变量 → 只去均值

    X = sm.add_constant(X, has_constant='add')      # 加截距项
    mask = y.notna() & X.notna().all(axis=1)        # 只保留数据完整的股票
    if mask.sum() < X.shape[1] + 5:                 # 样本太少 → 退化为去均值
        return y - y.mean()

    model = sm.OLS(y[mask], X[mask]).fit()
    resid = pd.Series(np.nan, index=y.index)
    resid[mask] = model.resid                       # ← 残差 = 纯因子
    return resid
```

**逐块解释：**

| 代码块 | 作用 | 不写会怎样 |
|---|---|---|
| `X['logmv']` | 控市值。用 **log** 是因为市值分布极度右偏（几十亿到几万亿） | 直接用原始市值，回归会被几个巨头主导 |
| `pd.get_dummies(..., drop_first=True)` | 把"银行/医药/…"变成 0/1 列。**`drop_first` 是为了避免完全共线** | 会引入"虚拟变量陷阱"，矩阵不可逆 |
| `fillna('未知')` | 行业缺失归入"未知"类 | 否则那只票会被整只丢掉 |
| `sm.add_constant` | 加截距项 | 回归会强制过原点，残差有偏 |
| `mask.sum() < X.shape[1] + 5` | 样本数必须显著多于变量数 | 变量比样本还多时回归毫无意义（过拟合） |
| `model.resid` | 残差 = 真实值 − 拟合值 | —— |

> **数据限制（务必知道）**：申万行业接口对部分行业会返回异常结构，`industry_map` 实际**只能覆盖约一半的申万一级行业**（回测日志显示 16/31 个行业可用）。未映射到的股票被归入"未知"类——这削弱了行业中性化的效果，是免费数据源的已知局限。

### 5.2 策略部分

```python
NEUTRALIZE_BY = ('logmv', 'industry')

class FactorNeutralize(PanelStrategy):
    params = (('topn', TOPN), ('lookback', LOOKBACK), ('rebalance', 'monthly'),)

    def __init__(self):
        super().__init__()
        codes = [d._name for d in self.tradables]
        self.mv = value_panel(codes, 'total_mv')
        self.ind_map = industry_map(codes)          # {代码: 申万一级行业名}

    def on_rebalance(self, cur):
        mv = asof(self.mv, cur)
        if mv is None:
            return
        mom = {}                                     # 与前面几篇一致：逐只算动量
        for d in self.tradables:
            if not self.live(d, cur):
                continue
            closes = self.hist_close(d, self.p.lookback + 1)
            if closes is None or closes[0] <= 0:
                continue
            mom[d._name] = closes[-1] / closes[0] - 1.0
        mom = pd.Series(mom, dtype=float)
        if len(mom) < self.p.topn + 5:
            return

        mv = mv[mv > 0]
        common = mom.index.intersection(mv.index)
        mom, mv = mom[common], mv[common]
        logmv = np.log(mv)
        ind = pd.Series({c: self.ind_map.get(c) for c in common})

        use_ind = ind if 'industry' in NEUTRALIZE_BY and ind.notna().any() else None
        pure = neutralize(mom, logmv=logmv if 'logmv' in NEUTRALIZE_BY else None,
                          industry=use_ind)
        pure = pure.dropna()
        if len(pure) < self.p.topn:
            return
        names = pure.sort_values(ascending=False).index[:self.p.topn].tolist()
        self.equal_weight_order(names, cur)
```

| 细节 | 说明 |
|---|---|
| `NEUTRALIZE_BY = ('logmv','industry')` | 想只做市值中性化？改成 `('logmv',)` 即可 |
| `if len(mom) < topn + 5` | 比单纯 `< topn` 更保守：回归需要足够样本 |
| `np.log(mv)` | 市值取对数 |
| `ind.notna().any()` | 一个行业都没映射上时，自动退化为"只做市值中性化" |

---

## 六、一次真实运行的轨迹

```
预加载市值面板 ...
构建行业映射（首次较慢，之后读缓存）...
  行业映射：16/31 个申万一级行业可用，共 2710 只股票
[3/3] 开始 backtrader 回测 ...
```

想直观看到"中性化前后选股不同"，加一行：

```python
raw = mom[common].sort_values(ascending=False).index[:5]
print(f'  [{cur}] 中性化前 Top5: {list(raw)}')
print(f'  [{cur}] 中性化后 Top5: {list(pure.sort_values(ascending=False).index[:5])}')
```

你会看到替换掉的多半是**小盘股**——这就是"动量里混着的市值暴露"。

---

## 七、与聚宽版的差异

| 维度 | 聚宽 | 本地版 |
|---|---|---|
| 行业分类 | `get_industry(security)`（申万/聚宽行业，覆盖全） | `industry_map()`（申万接口，**只覆盖约一半**） |
| 市值 | `get_fundamentals(valuation.market_cap)` | `value_panel('total_mv')` |
| 回归 | `statsmodels` / `sklearn` | `statsmodels.OLS` |
| 下单 | `order_target_value` | `equal_weight_order` |

---

## 八、回测结果怎么读

| 指标 | 数值 | 怎么理解 |
|---|---|---|
| 累计收益率 | **+180.89%** | 高于纯动量（+165.02%），但低于多因子（+295.75%） |
| 年化收益率 | **+13.04%** | —— |
| 最大回撤 | **−33.21%** | 介于两者之间 |
| 夏普比率 | **0.62** | 比纯动量（0.45）好 |
| 成交笔数 | 1334 | 月频 |

**要点：**

1. **中性化确实改善了风险收益比**（夏普 0.45 → 0.62），说明"剥离市值/行业暴露"让因子更"干净"；
2. 但**收益没有碾压**——因为剥离掉市值暴露，也就剥离掉了部分"小市值溢价"的收益；
3. **行业覆盖不全**（16/31）是本篇最大的实现缺陷，会让中性化效果打折扣。

> **教学价值**：这一篇把"因子研究"从"排序取前几名"推进到了"**控制变量**"的层次。这是从"民科式选股"走向"因子研究"的关键一步。

---

## 九、易混点与常见错误

| 症状 | 原因 | 正确做法 |
|---|---|---|
| 回归报错/矩阵奇异 | 行业哑变量没 `drop_first`，完全共线 | `pd.get_dummies(..., drop_first=True)` |
| 样本太少导致结果乱跳 | 变量数接近样本数 | 加 `mask.sum() < X.shape[1] + 5` 的保护 |
| 大量股票归入"未知"行业 | 行业接口覆盖不全 | 已知局限；可换 `NEUTRALIZE_BY=('logmv',)` 只做市值中性 |
| 直接用原始市值回归 | 分布右偏 | 取 `np.log` |
| 以为残差一定是正的 | 残差可正可负 | 排序取最大的即可 |

---

## 十、自测题（不写代码也能做）

1. 用一句话解释"动量因子里混着市值暴露"是什么意思。
2. 为什么回归要用 `log(市值)` 而不是市值本身？
3. 为什么要 `drop_first=True`？不写会出什么问题？
4. 如果行业数据只覆盖一半，中性化的结果会偏向哪边？

---

## 十一、改进方向（思考题）

1. **补全行业数据**：换用覆盖更全的行业分类源，或改用"行业 ETF 收益率"代理。
2. **只做市值中性**：`NEUTRALIZE_BY = ('logmv',)`，对比效果，隔离"行业覆盖不全"的影响。
3. **中性化别的因子**：把 `mom` 换成 `pb`（估值中性化），看"纯估值"因子。
4. **加风格因子**：Barra 模型里还有波动率、流动性、成长等，可以逐个加进来。