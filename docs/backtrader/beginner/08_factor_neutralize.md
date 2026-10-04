# 策略 8：因子中性化选股（Factor Neutralize）· backtrader 本地版

> 策略类型：多因子进阶（因子提纯） ｜ 难度：★★★★☆ ｜ 前置知识：策略 6 的动量因子、pandas、statsmodels OLS、截面 vs 时序
> **运行框架：backtrader（本地回测 + 免费数据）** ｜ 本策略的**聚宽云端版**见 [docs/joinquant/beginner/s08_factor_neutralize.md](../../joinquant/beginner/08_factor_neutralize.md)

## 一、核心思路

原始因子往往"被别的风格污染"。例如动量因子经常和小市值、某些行业强相关——你以为在选"涨得好的股票"，实际可能只是"小盘股"或"某一行业"的代理。中性化就是把因子里"市值、行业"的影响**剔除**，留下更纯粹的暴露。

数学形式（截面回归）：

$$factor_i = \alpha + \beta \cdot \log(市值_i) + \sum_k \gamma_k \cdot 行业哑变量_{k,i} + \varepsilon_i$$

我们取**残差 $\varepsilon$** 作为"纯因子"：它衡量"在控制了市值和行业之后，这只股票相对同行的额外动量强弱"。按纯因子选股，组合就不会在市值/行业上无意间压了重注。

| 概念 | 含义 |
|------|------|
| 截面（cross-section） | 同一时点、横扫所有股票，做一次回归 |
| 时序（time-series） | 同一只股票、沿时间看 |
| 残差 $\varepsilon$ | 剔除系统性影响后，个股自身的"纯净度"（均值≈0） |

> 给新手的直觉：考试排名被"家庭收入"影响。你想比"聪明程度"，就先把"收入"对"成绩"做回归，取残差——残差大的才是"在同等家庭条件下依然成绩突出"的人。本策略对"动量"做了"市值+行业"的同样处理。

## 二、算法结构（分步拆解）

```
每月首个交易日触发 on_rebalance(cur)
   │
   ├─ 1. 预加载市值面板 + 行业映射（__init__ 完成）
   │
   ├─ 2. 取市值快照 asof(self.mv, cur)，算动量因子（同策略 6/7）
   │
   ├─ 3. 取对数市值 logmv = np.log(mv)，取行业哑变量 industry
   │      └─ ind_map.get(c) → 缺失归 '未知'（避免整只股票被剔除）
   │
   ├─ 4. neutralize(动量, logmv, industry)
   │      └─ OLS 截面回归取残差 → 纯因子
   │
   └─ 5. equal_weight_order(纯因子最大的前 TOPN 只, cur)
```

## 三、代码逐段详解 + backtrader 语法解析

### 3.1 预加载市值面板与行业映射

```python
class FactorNeutralize(PanelStrategy):
    params = (('topn', TOPN), ('lookback', LOOKBACK), ('rebalance', 'monthly'),)

    def __init__(self):
        super().__init__()
        codes = [d._name for d in self.tradables]
        self.mv = value_panel(codes, 'total_mv')
        self.ind_map = industry_map(codes)
```

`industry_map(codes)`（§17.2）返回 `{代码: 申万一级行业名}`。注意数据集限制：申万行业接口对部分行业返回异常结构，`industry_map` 实际**只能覆盖约一半申万一级行业**（本次回测日志显示 16/31 个可用，共 2710 只股票映射到了行业）。未映射到的股票在回归里统一归入"未知"类（见 3.3），这是本地版的已知近似。

### 3.2 中性化函数 `neutralize`

```python
def neutralize(factor, logmv=None, industry=None):
    y = pd.Series(factor, dtype=float)
    X = pd.DataFrame(index=y.index)
    if logmv is not None:
        X['logmv'] = pd.Series(logmv, dtype=float).reindex(y.index)
    if industry is not None:
        ind = pd.Series(industry).reindex(y.index).fillna('未知')
        dummies = pd.get_dummies(ind, prefix='ind', drop_first=True)
        X = pd.concat([X, dummies.astype(float)], axis=1)
    if X.shape[1] == 0:
        return y - y.mean()
    X = sm.add_constant(X, has_constant='add')
    mask = y.notna() & X.notna().all(axis=1)
    if mask.sum() < X.shape[1] + 5:
        return y - y.mean()
    model = sm.OLS(y[mask], X[mask]).fit()
    resid = pd.Series(np.nan, index=y.index)
    resid[mask] = model.resid
    return resid
```

逐行解析：

- **`np.log(mv)`**：市值是右偏长尾分布（几百亿到上万亿），取对数压缩量纲，让线性回归的"市值影响"更线性、更稳。
- **`pd.get_dummies(ind, drop_first=True)`**：把"行业名"这种类别变量变成 0/1 哑变量矩阵。`drop_first=True` 是**关键**——若不丢弃一个基准行业，哑变量会完全共线（"行业"共 30 列但只有 29 个自由度），OLS 无法求解。
- **`sm.add_constant`**：加截距项 $\alpha$。
- **`mask = y.notna() & X.notna().all(axis=1)`**：只保留因子与所有解释变量都非缺失的样本。
- **样本数守卫**：`mask.sum() < X.shape[1] + 5` 时退化为 `y - y.mean()`（仅去均值），避免样本太少导致回归系数不可靠（过拟合/奇异矩阵）。
- **返回值 `model.resid`**：残差序列 = 纯因子。残差均值≈0，正数代表"在同等市值/行业下动量偏强"。

每次调仓都做一次**独立截面回归**——这是"截面"而非"时序"的典型用法。

### 3.3 `on_rebalance`：取因子并中性化

```python
mv = asof(self.mv, cur)
if mv is None:
    return
# ... 算动量 mom（list 语义，closes[-1]/closes[0]-1）...
if len(mom) < self.p.topn + 5:
    return
mv = mv[mv > 0]
common = mom.index.intersection(mv.index)
mom, mv = mom[common], mv[common]
logmv = np.log(mv)
ind = pd.Series({c: self.ind_map.get(c) for c in common})   # 缺失→None

use_ind = ind if 'industry' in NEUTRALIZE_BY and ind.notna().any() else None
pure = neutralize(mom, logmv=logmv if 'logmv' in NEUTRALIZE_BY else None,
                  industry=use_ind)
pure = pure.dropna()
if len(pure) < self.p.topn:
    return
names = pure.sort_values(ascending=False).index[:self.p.topn].tolist()
self.equal_weight_order(names, cur)
```

`get_dummies` 之前用 `fillna('未知')` 把没有行业映射的股票归入统一类别——这样它们仍留在回归样本里（哑变量 `ind_未知=1`），不会因缺失被整只剔除。`NEUTRALIZE_BY = ('logmv', 'industry')` 是可配置的中性化维度，若想只中性化市值，把 `industry` 去掉即可。

### 3.4 防未来函数

与策略 7 一致：`asof(self.mv, cur)` 只取 `≤ cur` 的市值；动量用 `hist_close` 长度守卫；`on_rebalance` 当根收盘触发、订单次日开盘成交。`industry_map` 是静态行业归属（文件头已注明：聚宽版用 `get_industry(stock, date)` 取"当时"行业，本地免费源只能取"当前"，属已知近似）。

### 3.5 `PanelStrategy` 的月份调度与 `__CAL__` 时钟

"每月触发一次"的调度与策略 6/7 相同（`runner.py` 里 key 取 `(年, 月)`，跨月才调 `on_rebalance`）。本策略的 `industry_map` 是**静态**映射，不随 `cur` 变化，所以时钟只影响"哪天算动量、哪天切片市值"，不影响行业归属——这正好解释了文件头注明的"本地只能取当前行业"：行业映射在 `__init__` 一次性建好，运行期不再按日期重查。

### 3.6 残差为何更"纯净"

OLS 残差 $\varepsilon$ 是"被市值和行业解释之后剩下的部分"。因为回归里加了截距项 $\alpha$，残差天然**均值≈0**：正的残差代表"同等市值/行业下动量偏强"，负的代表偏弱。按残差选股，等价于"在同市值、同行业的对照组里挑动量最突出的"，组合就不会无意间在市值或行业上压重注。注意残差仍可能含噪声（截面回归只剔除线性部分的市值/行业影响，非线性或非行业风格未被控制），因此纯因子并非绝对纯净。

### 3.7 哑变量与共线性的具体展开

为写清 `pd.get_dummies(ind, drop_first=True)`，假设只有 3 只股票、行业分别为 A/B/未知：

```
原始行业列:   [A,    B,    未知]
哑变量(去首列): ind_B=[0,1,0], ind_未知=[0,0,1]   # A 行业作为基准，全 0
```

回归变成 `momentum ~ const + logmv + ind_B + ind_未知`。`ind_B=1` 表示"相对基准行业 A，行业 B 的平均动量偏移多少"；`ind_未知=1` 同理。**若不去首列**（保留 `ind_A`），三列 `ind_A+ind_B+ind_未知` 每行都恒等于 1，与截距项 `const` 完全共线，OLS 设计矩阵奇异、无法求逆——这就是 `drop_first=True` 不可替代的原因（K 个行业只需 K-1 个哑变量，留一个当基准）。`industry_map` 只覆盖约半数申万一级，未映射的归"未知"单成一类，所以行业维度的中性化本就少了另一半行业的区分力，这是本地版的已知近似。

### 3.8 可配置的中性化维度与守卫

`NEUTRALIZE_BY = ('logmv', 'industry')` 决定本次回测中性化哪些维度，`on_rebalance` 据此开关：

```python
use_ind = ind if 'industry' in NEUTRALIZE_BY and ind.notna().any() else None
pure = neutralize(mom,
                  logmv=logmv if 'logmv' in NEUTRALIZE_BY else None,
                  industry=use_ind)
```

- 想只中性化市值、保留行业暴露，把 `industry` 从 `NEUTRALIZE_BY` 删掉即可，`industry` 传 `None` 时 `neutralize` 内部不生成哑变量列；
- `ind.notna().any()` 守卫：若本批股票全无行业映射（极端情况），`use_ind` 置 `None`，退化为只做市值中性化，避免"全未知哑变量=单类"导致回归退化为去均值；
- 两个维度都关掉时，`neutralize` 的 `X.shape[1]==0` 分支直接返回 `y - y.mean()`（仅去均值），等价于"原始动量排名"。

这种开关式设计让同一套骨架能快速对比"不中性化 / 只中性化市值 / 市值+行业"三种效果。

### 3.9 行业覆盖的实证局限

本次回测日志第一行就写明：`行业映射：16/31 个申万一级行业可用，共 2710 只股票`。即本地免费源只成功映射了约一半行业——剩余行业全部被 `fillna('未知')` 合并成单类。后果是：行业中性化只在这 16 个行业内部做了区分，跨"已映射 vs 未知"的行业的暴露并未被控制。所以本策略的"行业中性化"是不完全的，解读收益时要记住这一层近似（聚宽版用 `get_industry(stock, date)` 能取当时全行业，无此局限）。

## 四、与聚宽版的差异

| 维度 | 聚宽云端版（s08） | backtrader 本地版（bt_s08） |
|------|-------------------|------------------------------|
| 行业归属 | `get_industry(codes, date)` 取**当时**申万一级行业 | `industry_map` 只能取**当前**行业（约半数行业可用） |
| 中性化变量 | `np.log(market_cap)` + 行业哑变量 | 同逻辑，`np.log(mv)` + 哑变量 |
| 回归 | `sm.OLS(factor, X)` 截面回归取残差 | 完全一致（statsmodels 是本地库，语法不变） |
| 触发/下单 | `run_monthly` + `order_target_value` | `on_rebalance` + `equal_weight_order`（整手） |
| 股票池 | 全市场 + 过滤 | 沪深300 当前前 40 只（幸存者偏差） |

**本地特有近似**：聚宽能逐期查"当时"行业，本地行业映射是静态的、且只覆盖约一半行业，因此中性化在行业维度上本就打了折扣；日志里 16/31 即印证。

## 五、回测结果（真实数据）

数据来源：`results/logs/bt_s08_factor_neutralize.log`（本地实跑，未编造）。

| 指标 | 数值 |
|------|------|
| 回测区间 | 2018-01-02 ~ 2026-09-30（2123 个交易日） |
| 初始 / 期末资金 | 100 万 → 2,808,882 元 |
| 累计收益率 | +180.89% |
| 年化收益率 | 13.04% |
| 基准（沪深300）累计 | +6.61% |
| 超额收益 | +174.28% |
| 最大回撤 | -33.21% |
| 夏普比率 | 0.62 |
| 年化波动率 | 24.78% |
| 日胜率 | 51.78% |
| 总成交笔数 | 1334 |
| 累计换手率 | 12518.51% |

**解读**：中性化后年化降到 13%、夏普 0.62，是 6~9 这几篇里最弱的。这并不意外——把动量里"小市值"和"行业"的成分剔除后，剩的纯因子 alpha 变薄了；换句话说，策略 6/7 里相当部分收益其实来自"小盘暴露"，中性化把它显式剥掉了。回撤 -33% 反而最深，说明纯动量残差波动并不小。

## 六、改进方向（思考题）

1. **补全国行业覆盖**：本地只覆盖约一半申万一级，可换更完整的行业数据源，让行业中性化真正生效。
2. **多因子中性化**：当前只中性化了动量一个因子，可对所有因子都做市值/行业中性化后再合成（结合策略 7/9）。
3. **加止损**：`equal_weight_order` 只做再平衡，可用 `self.buy_bracket` 给单票加止损腿，压低 -33% 的尾部回撤。
