# 策略 9：因子 IC / IR 加权（动态权重多因子）· backtrader 本地版

> **策略类型**：多因子进阶（因子有效性度量 + 动态加权） ｜ **难度**：★★★★★ ｜ **前置知识**：知道"相关系数"
> **运行**：`python strategies/backtrader/beginner/bt_s09_factor_ic_weight.py` ｜ **聚宽版**：[09_factor_ic_weight.md](../../joinquant/beginner/09_factor_ic_weight.md)
> **语法底座**：[backtrader详解.md](../../learning/2.库详解/数据分析与量化研究相关库/backtrader详解.md) 第 10 章

---

## 一、这一篇你将学到什么

策略 7 里，四个因子的权重是**拍脑袋定的 1:1:1:1**。这一篇要问：**凭什么动量就该和 ROE 一样重要？**

| 你会搞懂 | 一句话 |
|---|---|
| **IC（信息系数）** | 因子值和"下一期收益"的相关性 —— 衡量因子准不准 |
| **IR（信息比率）** | IC 的均值 ÷ 标准差 —— 衡量因子稳不稳 |
| **时序纪律** | 算 IC 只能用"上期因子 + 本期已实现收益"，多一步就是未来函数 |
| 动态权重 | IR 高的因子多给权重，IR 为负的直接归零 |

**读完你应该能回答**：为什么算 IC 的时候，必须用**上一期**的因子值，而不是本期的？

---

## 二、心智模型：一个"因子考试"的闭环

```
第 t 期（调仓日）
   │
   ├─ ① 记录本期因子快照：factors[t]、价格 price[t]
   │
   ├─ ② 用"上一期因子 + 本期收益"给因子打分：
   │        已实现收益 = price[t] / price[t-1] − 1
   │        IC = corr( factors[t-1] , 已实现收益 )      ← 因子准不准
   │
   ├─ ③ 用最近 6 期 IC 算 IR = mean(IC) / std(IC)      ← 因子稳不稳
   │        w = max(IR, 0)   （IR 为负 → 权重 0，不反向使用）
   │
   ├─ ④ 用权重合成综合分：
   │        score = w_roe·z(roe) − w_pb·z(pb) + w_mom·z(mom) − w_mv·z(mv)
   │
   └─ ⑤ 取 score 前 10 → 等权买入 → 次日开盘成交
```

**关键：这是一个"用因子自己的历史表现来决定它的话语权"的闭环。** 但它不是"预测未来"，而是"根据最近的实测效果调整权重"——所以**时序必须严格**。

---

## 三、核心思路

**IC（Information Coefficient）**：

$$IC_t = corr\left(factor_{t-1},\ r_t\right)$$

- 含义：**上一期的因子值，能不能预测本期的收益？**
- IC > 0：因子方向对（值越大、收益越高）；IC < 0：方向反了；IC ≈ 0：没有预测力。
- 实务上 |IC| > 0.03 就算"有效"，> 0.05 已经相当不错（因为它是横截面相关系数）。

**IR（Information Ratio）**：

$$IR = \frac{mean(IC)}{std(IC)}$$

- 光看"平均准不准"不够，还要看"稳不稳"。
- 一个因子平均 IC = 0.05 但每次都是 0.04~0.06 → IR 很高（稳定有效）；
- 另一个因子平均 IC 也是 0.05，但在 ±0.3 之间乱跳 → IR 很低（不可用）。

**本策略的加权规则**：

| 情况 | 权重 |
|---|---|
| IR > 0 | `w = IR`（越稳越重要） |
| IR ≤ 0 | `w = 0`（**不反向使用**，因为负 IC 往往不稳定） |
| IC 期数 < 3 | `w = 1.0`（样本不足，退回等权） |

> **⚠️ 最容易犯的未来函数**：很多教程写 IC 时用 `corr(factor_t, return_t)`，但 `return_t`（本期收益）在**本期调仓时还没实现**——你只能等到下一期。**本策略严格用"上期因子 + 本期收益"，并把这一刻记为 `prev_factors` / `prev_price`。**

---

## 四、算法结构

```
class ICFactorWeight(PanelStrategy):
    __init__:
        ├─ 预加载 pb / mv / roe 三张面板
        ├─ self.prev_factors = None      ← 上一期因子快照
        ├─ self.prev_price = {}          ← 上一期价格
        └─ self.ic_hist = {k: [] for k in ('mom','roe','pb','mv')}

    _current_factors(cur):
        → (本期四个因子的 Series 字典, 本期价格字典)

    _update_ic(price):
        ├─ 用 prev_factors + (price / prev_price − 1) 算已实现收益
        └─ 对每个因子算 IC，追加到 ic_hist

    _weights():
        └─ 每个因子：最近 6 期 IC → IR → w = max(IR, 0)

    on_rebalance(cur):
        ├─ factors, price = self._current_factors(cur)
        ├─ self._update_ic(price)          ← 用【上期】数据打分
        ├─ w = self._weights()
        ├─ score = w组合四个 z-score
        ├─ 取前 10 → equal_weight_order()
        └─ 保存本期快照：prev_factors / prev_price = 本期
```

---

## 五、代码逐段详解

### 5.1 状态初始化

```python
FACTORS = ('mom', 'roe', 'pb', 'mv')
IC_WINDOW = 6               # 滚动 IC 窗口（期）

def __init__(self):
    super().__init__()
    codes = [d._name for d in self.tradables]
    self.pb = value_panel(codes, 'pb')
    self.mv = value_panel(codes, 'total_mv')
    self.roe = roe_panel(codes, lag_days=ROE_LAG)
    self.prev_factors = None      # 上一期的因子快照
    self.prev_price = {}          # 上一期的价格
    self.ic_hist = {k: [] for k in FACTORS}
```

**为什么要存 `prev_price`？** 因为算 IC 需要"本期已实现的收益"，而收益 = 本期价格 ÷ 上期价格 − 1。价格必须在**上一期**就记下来。

### 5.2 算 IC（本策略的灵魂）

```python
def _update_ic(self, price):
    if self.prev_factors is None:      # 第一期没有上期数据 → 跳过
        return
    codes = [c for c in self.prev_factors['mom'].index
             if c in price and self.prev_price.get(c, 0) > 0]
    if len(codes) < 10:                # 样本太少不估 IC
        return

    realized = pd.Series({c: price[c] / self.prev_price[c] - 1.0 for c in codes})

    for k in FACTORS:
        f = self.prev_factors[k].reindex(codes)     # ← 用【上期】因子
        r = realized.reindex(codes)                 # ← 用【本期】已实现收益
        mask = f.notna() & r.notna()
        if mask.sum() >= 10:
            self.ic_hist[k].append(float(f[mask].corr(r[mask])))
```

| 这一行 | 为什么 |
|---|---|
| `if self.prev_factors is None: return` | 第一期没有"上期"，无法算 IC |
| `f = self.prev_factors[k]` | **时序纪律**：因子必须是上一期的（上期调仓时就已经知道） |
| `realized = 本期价/上期价 − 1` | 收益是**已经实现**的，不是预测的 |
| `f.corr(r)` | 横截面相关系数 = IC |

### 5.3 由 IC 算权重

```python
def _weights(self):
    w = {}
    for k in FACTORS:
        arr = [x for x in self.ic_hist[k][-self.p.ic_window:] if pd.notna(x)]
        if len(arr) >= 3 and np.std(arr) > 1e-9:
            ir = float(np.mean(arr) / np.std(arr))
        else:
            ir = 1.0                    # 样本不足 → 退回等权
        w[k] = max(ir, 0.0)             # 负 IR 归零，不反向用
    if sum(w.values()) <= 0:            # 全为负 → 全部退回等权
        w = {k: 1.0 for k in FACTORS}
    return w
```

### 5.4 合成与调仓

```python
def on_rebalance(self, cur):
    factors, price = self._current_factors(cur)
    if factors is None:
        return
    self._update_ic(price)              # ← 先用【上期】数据更新 IC
    w = self._weights()

    score = (w['roe'] * zscore(factors['roe'])          # 质量 +
             - w['pb'] * zscore(factors['pb'])          # 估值 −
             + w['mom'] * zscore(factors['mom'])        # 动量 +
             - w['mv'] * zscore(factors['mv']))         # 规模 −
    names = score.sort_values(ascending=False).index[:self.p.topn].tolist()
    self.equal_weight_order(names, cur)

    self.prev_factors = factors        # ← 最后才保存本期快照，供下一期用
    self.prev_price = price
```

**顺序很重要**：`_update_ic(price)` 必须在 `prev_factors` 被覆盖**之前**调用——否则就变成"用本期因子算本期 IC"，那是未来函数。

> **注意**：`equal_weight_order` 内部仍是**等权**分配资金。IC/IR 只影响 `score` 的**排序**（选谁），不影响入选后的仓位比例。这就是"**动态加权选股 + 静态等权配置**"。

---

## 六、一次真实运行的轨迹

```
最新一期 IC: {'mom': -0.312, 'roe': 0.084, 'pb': 0.021, 'mv': 0.156}
最新一期 IC: {'mom': 0.658, 'roe': 0.012, 'pb': -0.043, 'mv': 0.091}
...
```

看得见的教学点：

- **`mom` 在 0.658 和 −0.312 之间反复横跳** → 说明它 IR 低、不稳定 → 权重会被压低；
- **`mv` 长期为正** → 小市值方向稳定 → 权重会较高；
- 这些 IC 只用于**诊断和调权**，不参与直接交易。

---

## 七、与聚宽版的差异

| 维度 | 聚宽 | 本地版 |
|---|---|---|
| 因子面板 | `get_fundamentals` 一次取 | 估值/财务分两个源 |
| IC 计算 | 同样用 pandas `corr` | 同 |
| 权重 | 自己实现 | 自己实现（无内置） |
| 下单 | `order_target_value` | `equal_weight_order` |

---

## 八、回测结果怎么读

| 指标 | 数值 | 怎么理解 |
|---|---|---|
| 累计收益率 | **+128.18%** | **低于**静态等权的策略 7（+295.75%） |
| 年化收益率 | **+10.29%** | —— |
| 最大回撤 | **−33.57%** | 与策略 7 接近 |
| 夏普比率 | **0.54** | 也低于策略 7（0.82） |
| 成交笔数 | 1388 | 月频 |

**"动态加权反而更差"这件事，本身就是最好的一课：**

1. **IC 是噪声很大的估计**：6 期 IC 的均值/标准差，统计上非常不稳，很容易"追高权重、然后失效"；
2. **典型的"过度反应"**：某因子最近几期表现好 → 权重调高 → 风格切换 → 亏得更多；
3. 这说明 **"更复杂"不等于"更好"**。策略 7 那个"朴素等权"反而更稳。

> **教学价值**：这一篇教的是**方法论**（怎么度量因子有效性、怎么做时序对齐），而不是"一个更好的策略"。**能看出"动态加权没赚到便宜"，说明你真的读懂了回测。**

---

## 九、易混点与常见错误

| 症状 | 原因 | 正确做法 |
|---|---|---|
| IC 高得离谱 | 用了**本期**因子算本期 IC（未来函数） | 用 `prev_factors` + 本期已实现收益 |
| 第一期就报错 | 没有 `prev_factors` | 首期直接 `return` |
| 权重永远是 1.0 | IC 期数 < 3（走兜底分支） | 正常；随回测推进会开始生效 |
| 权重全为 0 | 所有因子 IR 都为负 | 代码里已兜底为等权 |
| 以为权重会改变持仓比例 | 只改排序 | 等权由 `equal_weight_order` 决定 |

---

## 十、自测题（不写代码也能做）

1. IC 和 IR 分别在衡量因子的什么性质？为什么光看 IC 不够？
2. 为什么算 IC 只能用"上期因子 + 本期收益"？用"本期因子 + 本期收益"错在哪？
3. 这个策略的收益比策略 7 低，说明"动态加权"这个想法错了吗？还是有别的原因？

---

## 十一、改进方向（思考题）

1. **拉长 IC 窗口**：`IC_WINDOW` 从 6 改成 12/24，看是否更稳（减少噪声）。
2. **用 Rank IC**：改成 Spearman 相关（对异常值更稳健）。
3. **平滑权重**：`w_new = 0.7*w_old + 0.3*w_target`，避免权重剧烈跳动。
4. **只保留正 IC 因子**：`w = max(IR, 0)` 已是如此，可以再尝试"至少 3 期 IC 为正才启用"。