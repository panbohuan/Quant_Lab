# 策略 9：因子 IC/IR 加权选股（Factor IC Weight）· backtrader 本地版

> 策略类型：多因子进阶（因子有效性度量 + 动态加权） ｜ 难度：★★★★★ ｜ 前置知识：策略 7 的 z-score 合成、相关系数、滚动窗口
> **运行框架：backtrader（本地回测 + 免费数据）** ｜ 本策略的**聚宽云端版**见 [docs/joinquant/beginner/s09_factor_ic_weight.md](../../joinquant/beginner/09_factor_ic_weight.md)

## 一、核心思路

前面策略用"等权"合成因子，但不同因子的有效性随时间变化，且方向可能反转。本策略引入两个度量因子有效性的指标：

- **IC（信息系数）**：某一期因子值与"下一期实际收益"的截面相关系数。
  $$IC_t = corr(\,因子_t,\ 下一期收益_t\,)$$
  IC 为正表示"因子大的股票下一期确实涨得多"，因子有效；接近 0 表示无效；为负表示方向反了。
- **IR（信息比率）**：滚动 IC 的均值除以标准差。
  $$IR = \frac{mean(滚动\,IC)}{std(滚动\,IC)}$$
  IC 只告诉"方向对不对"，IR 还告诉我们"稳不稳"——一个 IC 高但波动大的因子并不可靠。

用 **IR 作为因子权重**动态加权：IR 高的因子多说话，IR 为负的因子直接归零（不反向使用，避免不稳定）。本策略取近 6 期（`IC_WINDOW=6`）滚动更新权重。

| 因子 | 方向 | 说明 |
|------|------|------|
| mom（动量） | + | 60 日涨幅 |
| roe（质量） | + | ROE |
| pb（估值） | - | 市净率（越低越好） |
| mv（规模） | - | 总市值（越小越好） |

> 给新手的直觉：四个评委历史打分准不准各有高低。你不再让他们平起平坐，而是看"谁最近预测得又准又稳"，给他更大投票权；预测已经变负分的，直接取消投票资格。

## 二、算法结构（分步拆解）

```
每月首个交易日触发 on_rebalance(cur)
   │
   ├─ 1. _current_factors(cur)：算本期四因子 + 对齐（同策略 7）
   │
   ├─ 2. _update_ic(price)：用「上期因子 + 本期已实现收益」更新各因子 IC
   │      └─ 时序纪律：本期收益要等本期结束才知道，只能拿上期因子来算
   │
   ├─ 3. _weights()：IR = mean(近6期IC) / std(近6期IC)；IR<0 → 0；不足→等权
   │
   ├─ 4. score = Σ w_k · 方向 · zscore(factor_k)
   │
   └─ 5. equal_weight_order(score 最高的前 TOPN 只, cur)
          └─ 末尾保存 prev_factors / prev_price 供下期算 IC
```

## 三、代码逐段详解 + backtrader 语法解析

### 3.1 状态初始化

```python
class ICFactorWeight(PanelStrategy):
    params = (('topn', TOPN), ('lookback', LOOKBACK), ('rebalance', 'monthly'),
              ('ic_window', IC_WINDOW),)

    def __init__(self):
        super().__init__()
        self.pb = value_panel(codes, 'pb')
        self.mv = value_panel(codes, 'total_mv')
        self.roe = roe_panel(codes, lag_days=ROE_LAG)
        self.prev_factors = None      # 上一期的因子快照
        self.prev_price = {}          # 上一期价格（算本期已实现收益）
        self.ic_hist = {k: [] for k in FACTORS}
```

与策略 7 相比多了三类**跨期状态**：`prev_factors`（上期因子值）、`prev_price`（上期收盘价）、`ic_hist`（每个因子的滚动 IC 列表）。这些挂在 `self` 上，随回测推进逐月累积——backtrader 的 `Strategy` 实例在整段回测中存活，所以把状态存 `self` 即可跨 `on_rebalance` 调用。

### 3.2 本期因子 `_current_factors`

逻辑与策略 7 一致：三张面板 `asof(cur)` + 动量 `hist_close`（list 语义 `closes[-1]/closes[0]-1`）+ 四因子交集对齐，额外记录 `price[d._name] = d.close[0]`（Line 语义，当根收盘价，用于下期算收益）。返回 `(dict, {code: price})`。

### 3.3 更新 IC —— 最易犯未来函数的地方

```python
def _update_ic(self, price):
    if self.prev_factors is None:
        return
    codes = [c for c in self.prev_factors['mom'].index
             if c in price and self.prev_price.get(c, 0) > 0]
    if len(codes) < 10:
        return
    realized = pd.Series({c: price[c] / self.prev_price[c] - 1.0 for c in codes})
    for k in FACTORS:
        f = self.prev_factors[k].reindex(codes)
        r = realized.reindex(codes)
        mask = f.notna() & r.notna()
        if mask.sum() >= 10:
            self.ic_hist[k].append(float(f[mask].corr(r[mask])))
```

**时序纪律（核心）**：本期只能用"上一期因子值"和"本期已实现收益"算 IC——因为"下一期收益"要等下一期结束才知道。所以这里用 `self.prev_factors`（上月快照）对 `realized`（本月实际涨幅 = 本月价 / 上月价 - 1）做相关。日志里打印的 `最新一期 IC` 行情（如 `{'mom':0.01,'roe':0.387,'pb':0.412,'mv':0.027}` 到后期出现 `mom:-0.867`）正说明**IC 极不稳定、时正时负**，这正是要用 IR（稳定性）而非裸 IC 赋权的理由。

### 3.4 权重 `_weights`

```python
def _weights(self):
    w = {}
    for k in FACTORS:
        arr = [x for x in self.ic_hist[k][-self.p.ic_window:] if pd.notna(x)]
        if len(arr) >= 3 and np.std(arr) > 1e-9:
            ir = float(np.mean(arr) / np.std(arr))
        else:
            ir = 1.0
        w[k] = max(ir, 0.0)               # IR 为负 → 归零
    if sum(w.values()) <= 0:
        w = {k: 1.0 for k in FACTORS}     # 全负 → 退化为等权
    return w
```

取近 6 期 IC 算 IR；样本不足 3 个或标准差≈0 时退化为等权 1.0；`max(ir, 0.0)` 把负 IR 截断为 0（不使用反向因子）。若所有因子 IR 都 ≤0，则全体等权兜底，避免空集。

### 3.5 合成与下单

```python
score = (w['roe'] * zscore(factors['roe'])
         - w['pb']  * zscore(factors['pb'])
         + w['mom'] * zscore(factors['mom'])
         - w['mv']  * zscore(factors['mv']))
names = score.sort_values(ascending=False).index[:self.p.topn].tolist()
self.equal_weight_order(names, cur)
self.prev_factors = factors          # 保存本期快照
self.prev_price = price
```

权重 `w` 乘到对应 z-score 上（带方向正负号），合成综合分。`equal_weight_order` 先卖后买、`cap=0.98`、`round_lot` 整手（§三 / `backtrader详解` §7.4、§13）。末尾把本期因子和价格存进 `prev_*`，供下一期 `_update_ic` 使用——**这正是"用上期因子 + 本期收益算 IC"闭环的关键**。

### 3.6 防未来函数

1. `asof` 三面板 + `roe_panel(lag_days=45)` 滞后；
2. 动量 `hist_close` 长度守卫；
3. **IC 计算的时序纪律**：只用 `prev_factors` + 已实现收益，绝不拿"本期因子 + 本期收益"算（那会用到本期还没结束的未来）；
4. 订单次日开盘成交。

### 3.7 `PanelStrategy` 的月份调度与 `__CAL__` 时钟

"每月触发一次"由骨架完成（key 取 `(年, 月)`，`runner.py`），与策略 6/7/8 一致。本策略对时钟更敏感：IC 的"上一期因子 ↔ 本期收益"配对必须严格按 `cur` 的月份顺序推进——若某月因停牌漏触发，配对就会错位。跨期状态 `prev_factors`/`prev_price` 也依赖"每月恰好一次 `on_rebalance`"的节奏，否则会重复或跳过快照。`next()` 收盘后触发、订单次日开盘成交，与 IC 时序纪律共同保证无未来函数。

### 3.8 滚动 IR 的实例演算

取日志里 `roe` 因子某连续 6 期 IC（示意）：`[0.387, 0.187, -0.066, 0.477, -0.477, 0.537]`。按 `_weights` 算法：

```
mean = (0.387+0.187-0.066+0.477-0.477+0.537)/6 ≈ 0.174
std  = 这些数的标准差 ≈ 0.351
IR   = 0.174 / 0.351 ≈ 0.50          # >0，roe 权重取 0.50
```

若某因子 6 期 IC 全为负（如 `mv` 曾出现 `-0.106,-0.209,...`），则 `mean<0` → `IR<0` → `max(ir,0)=0`，该因子本期**完全不参与**合成。日志里 IC 在 `mom:-0.867~0.658`、`roe:-0.477~0.608` 间剧烈跳动，说明 6 期窗口算出的 IR 本身噪声很大——权重在噪声上追逐，正是本策略实盘年化反而低于等权（策略 7）的根因。这也提示：窗口越短，IR 越不稳；要发挥其价值应加长窗口或做 IC 衰减加权。

### 3.9 IC 权重影响"选谁"而非"买多少"

注意一个易混点：`equal_weight_order(names, cur)` 内部仍是**等权**分配资金（每只标的市值相同）。IC/IR 加权只改变了 `score` 的**排序**——即"哪些股票入选 TOPN"——并不改变入选后的持仓比例。换句话说，本策略是"动态加权选股 + 静态等权配置"：权重高（IR 高）的因子更能决定入围名单，但一旦入围，大家平起平坐。若想让 IR 同时影响个股权重，应改用 `value_weight_order(weights, cur)`（§17.2）按 IR 归一化后的权重分配市值，而非 `equal_weight_order`。这是"因子有效性"与"仓位管理"两件事，别混为一谈。

### 3.10 样本数守卫的意义

`_weights` 里 `len(arr) >= 3` 是 IR 估计的下限：IC 本质是相关系数，少于 3 个样本算出的均值/标准差毫无统计意义，此时退化为等权 1.0。回测前期 `ic_hist` 为空或不足 3 期，权重全 1.0——即开局若干月等价于策略 7 的等权 z-score；只有当某因子积累了 ≥3 个有效 IC 后，IR 才开始起作用。这也是为什么本策略前段的收益特征会与策略 7 接近，差异主要在样本充足的后期才显现。

### 3.11 日志里的 IC 打印

`_update_ic` 末尾有一行 `print(f' 最新一期 IC: {latest}')`，把刚算出的各因子 IC 打到控制台（回测日志里大量 `最新一期 IC: {...}` 即此）。它**只用于诊断**，不参与交易决策——你可以通过它观察因子有效性随时间的起伏：例如 `mom` 在 `0.658` 与 `-0.867` 间反复横跳，正是 3.8 所说"IR 噪声大"的直观证据。实盘或批量跑 20 个策略时，可注释掉这行以减少噪声（与 `backtrader详解` §9 的日志控制思路一致）。

## 四、与聚宽版的差异

| 维度 | 聚宽云端版（s09） | backtrader 本地版（bt_s09） |
|------|-------------------|------------------------------|
| 触发方式 | `run_monthly(monthly, 1, '09:30')` | `on_rebalance(cur)` 月份变化触发 |
| 基本面来源 | `get_fundamentals` 一次 join + `history` 批量算动量 | `value_panel`×2 + `roe_panel(lag_days=45)` + `hist_close` |
| IC 计算 | 用 `g.snapshots` 存上期因子/价格 | 用 `self.prev_factors`/`self.prev_price` 跨期状态（逻辑等价） |
| 滚动窗口 | `g.ic_window=12` | `IC_WINDOW=6`（更短，更快适应） |
| 下单口径 | `order_target_value` | `equal_weight_order` 整手再平衡 |
| 股票池 | 全市场 + 过滤 | 沪深300 当前前 40 只（幸存者偏差） |

**差异本质**：聚宽用全局容器 `g` 存历史快照，本地用 `self` 实例属性存——backtrader 的 `Strategy` 实例贯穿全程，等价于 `g` 的持久化角色。

## 五、回测结果（真实数据）

数据来源：`results/logs/bt_s09_factor_ic_weight.log`（本地实跑，未编造）。

| 指标 | 数值 |
|------|------|
| 回测区间 | 2018-01-02 ~ 2026-09-30（2123 个交易日） |
| 初始 / 期末资金 | 100 万 → 2,281,843 元 |
| 累计收益率 | +128.18% |
| 年化收益率 | 10.29% |
| 基准（沪深300）累计 | +6.61% |
| 超额收益 | +121.57% |
| 最大回撤 | -33.57% |
| 夏普比率 | 0.54 |
| 年化波动率 | 23.40% |
| 日胜率 | 50.90% |
| 总成交笔数 | 1388 |
| 累计换手率 | 15432.94% |

**解读**：动态加权反而跑输等权合成的策略 7（年化 10.3% vs 17.7%），夏普 0.54 也是这几篇最低。原因很现实：日志显示各因子 IC 剧烈波动（如 `mom` 在 -0.867~0.658 间乱跳），用仅 6 期窗口估计的 IR 噪声极大，权重在噪声上追涨杀跌，反而增加了换手摩擦却没换来稳定 alpha。这正印证了"参数优化/动态加权不是免费午餐"。

## 六、改进方向（思考题）

1. **拉长 IC 窗口**：6 期太短、IR 估计噪声大，可加长到 12~24 期（聚宽版即 12）让权重更平滑。
2. **IC 衰减加权**：对越近的 IC 给越高权重（指数衰减），而非简单等权滚动平均。
3. **配合中性化**：先对因子做策略 8 的市值/行业中性化再算 IC，避免权重被风格暴露干扰。
4. **方向稳定性**：对连续多期 IR 为负的因子，可进一步降权或剔除，而非仅当期截断，减少权重抖动。
