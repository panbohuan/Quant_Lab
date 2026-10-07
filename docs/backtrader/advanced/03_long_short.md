# 进阶 3：多空对冲策略（Long-Short Equity）· backtrader 本地版

> **策略类型**：绝对收益 / 市场中性 ｜ **难度**：★★★★★ ｜ **前置知识**：知道"做空""Beta"
> **运行**：`python strategies/backtrader/advanced/bt_a03_long_short.py` ｜ **聚宽版**：[03_long_short.md](../../joinquant/advanced/03_long_short.md)
> **语法底座**：[backtrader详解.md](../../learning/2.库详解/backtrader详解.md) 第 5 章、第 9.6 节（做空）

---

## 一、这一篇你将学到什么

前面所有策略都是"只做多"。这一篇第一次**同时做多和做空**，目标是**把大盘涨跌的影响剥离掉**。

| 你会搞懂 | 一句话 |
|---|---|
| **Alpha 与 Beta** | Beta = 跟着大盘涨跌的部分；Alpha = 选股带来的超额 |
| **做空怎么实现** | `self.sell(size=n)` 且当前无持仓 → 持仓变成负数 |
| `position.size` 的符号 | 正=多头、负=空头、0=空仓 |
| 多空平衡 | 多头市值 ≈ 空头市值 → 组合对大盘不敏感 |
| **风险熔断** | 净值跌破阈值就清仓停手 |

**读完你应该能回答**：为什么"多空对冲"能在大盘下跌时也赚钱？它的代价是什么？

---

## 二、心智模型：同时买最强、卖最弱

```
每月第一个交易日（收盘后）
   │
   ├─ 0. 先看风控：净值 < 初始资金 × 40% ？→ 清仓，本月不再交易
   │
   ├─ 1. 算 40 只股票的 60 日动量，排序
   │
   ├─ 2. 多头 = 最强的 10 只    空头 = 最弱的 10 只
   │         （两组不能重叠）
   │
   ├─ 3. 两组各占净值的 40%（合计总敞口 80%）
   │         多头每只 ≈ 4% 净值；空头每只 ≈ 4% 净值
   │
   ├─ 4. 先平掉不在名单里的持仓
   │
   ├─ 5. 多头：目标股数 = +（市值/价格 取整手）
   │      空头：目标股数 = −（市值/价格 取整手）
   │
   └─ 6. 次日开盘成交
```

**为什么这样能"对冲"？** 假设大盘明天跌 3%：

| 部分 | 大致损益 |
|---|---|
| 多头 40% 仓位 × (−3%) | −1.2% |
| 空头 40% 仓位 × (+3%)（做空，跌了赚） | +1.2% |
| **合计** | **≈ 0**（大盘涨跌被抵消） |

真正决定盈亏的，是"多头比空头**多涨**的那部分"——那就是 **Alpha**。

---

## 三、核心思路

**市场中性策略的逻辑**：

$$\text{组合收益} = \underbrace{\beta \cdot R_{market}}_{\text{市场涨跌（被对冲掉）}} + \underbrace{\alpha}_{\text{选股能力}} + \text{噪声}$$

- 传统多头策略：赚 = 选股 + 市场 β；熊市里 β 会吃掉一切；
- **多空对冲**：多头 + 空头，把 β 大致抵消，只留下 α。

**本策略的构造**：

| 部分 | 选谁 | 仓位 |
|---|---|---|
| 多头 | 动量**最强**的 10 只 | 净值的 40% |
| 空头 | 动量**最弱**的 10 只 | 净值的 40% |

**注意事项（很重要）**：

1. **多头空头不能重叠**：如果样本太少导致重叠，策略直接跳过（代码里有 `if set(longs) & set(shorts): return`）；
2. **总敞口 80% 而不是 100%**：留空间，避免极端行情把净值打到负数；
3. **A 股做空是受限的**——见下面的诚实提示。

> **⚠️ 这一篇必须打折看（本仓库最"理想化"的策略）**
> 回测里 **`self.sell()` 就开出了空头**，隐含假设是：
> - **券源无限**、随时能借到券（真实 A 股：融券标的有限、券源紧张）；
> - **零融券成本**（真实：年化 8%~10% 的利息）；
> - **现金立即可用**（做空得到的现金能马上买多头）。
>
> 这三条都会显著削弱真实收益。**代码注释里已明确写出这一点**——请务必带着这个前提读下面那张收益表。

---

## 四、算法结构

```
main() → load_index_members → load_universe → __CAL__ → run_strategy
   │
   └─ LongShort.on_rebalance(cur)（每月）
         ├─ ① 熔断检查：getvalue() < startingcash × 0.40 → close_all + return
         ├─ ② 算动量，排序
         ├─ ③ longs = 前 10，shorts = 后 10
         ├─ ④ 若两组重叠 → return
         ├─ ⑤ capital_long = 净值×0.40÷10；capital_short 同理
         ├─ ⑥ 先平掉不在两名单里的持仓
         ├─ ⑦ 多头 → _target_size(+capital)
         └─ ⑧ 空头 → _target_size(−capital)
```

---

## 五、代码逐段详解

### 5.1 参数

```python
LOOKBACK = 60               # 动量回看期
LONG_NUM = 10               # 多头只数
SHORT_NUM = 10              # 空头只数
LONG_EXPOSURE = 0.40        # 多头市值 / 净值
SHORT_EXPOSURE = 0.40       # 空头市值 / 净值
STOP_EQUITY_RATIO = 0.40    # 净值跌破初始资金的该比例时停止交易
```

### 5.2 熔断与选股

```python
def on_rebalance(self, cur):
    # 0) 风控保险丝：用【初始资金】而不是硬编码常量
    if self.broker.getvalue() < self.broker.startingcash * STOP_EQUITY_RATIO:
        self.close_all(cur)
        print(f'  [{cur}] 净值跌破 {STOP_EQUITY_RATIO:.0%}，清仓停止交易')
        return

    mom = {}
    for d in self.tradables:
        if not self.live(d, cur):
            continue
        closes = self.hist_close(d, self.p.lookback + 1)
        if closes is None or closes[0] <= 0:
            continue
        mom[d._name] = closes[-1] / closes[0] - 1.0
    if len(mom) < self.p.long_num + self.p.short_num:
        return
    ranked = sorted(mom, key=mom.get, reverse=True)
    longs = ranked[:self.p.long_num]
    shorts = ranked[-self.p.short_num:]
    if set(longs) & set(shorts):        # 样本太少时可能重叠
        return
```

| 细节 | 说明 |
|---|---|
| `self.broker.startingcash` | **不是**硬编码的数字。写死 `1_000_000` 的话，一旦改初始资金，熔断线就错了 |
| `ranked[-short_num:]` | 取**最后 N 个**（动量最弱）= 空头标的 |
| `set(longs) & set(shorts)` | 两组不能重叠，否则同一只票既买又卖 |

### 5.3 目标仓位：正负号就是方向

```python
equity = self.broker.getvalue()
capital_long = equity * self.p.long_exposure / len(longs)     # 每只多头的目标市值
capital_short = equity * self.p.short_exposure / len(shorts)  # 每只空头的目标市值

for d in self.tradables:                       # 先平掉不在名单里的
    if d._name in longs or d._name in shorts:
        continue
    if self.getposition(d).size and self.live(d, cur):
        self.close(d)

for name in longs:
    self._target_size(name, capital_long, cur)
for name in shorts:
    self._target_size(name, capital_short, cur, short=True)
```

```python
def _target_size(self, name, capital, cur, short=False):
    d = self.getdatabyname(name)
    price = d.close[0]
    if price <= 0:
        return
    want = round_lot(capital / price)      # 目标股数（正数）
    if short:
        want = -want                        # ← 空头 = 负股数
    delta = want - self.getposition(d).size
    if delta > 0:
        self.buy(d, size=delta)
    elif delta < 0:
        self.sell(d, size=-delta)
```

**`delta` 这个写法是通用套路**：

```
delta = 目标股数 − 当前股数
delta > 0 → 买入 delta 股
delta < 0 → 卖出 |delta| 股
```

这样无论"从无到有""加仓""减仓""反手"都能用同一段代码处理。

### 5.4 做空在 backtrader 里长什么样

```python
self.sell(d, size=100)      # 无持仓时 → position.size 变成 -100（空头）
self.buy(d, size=100)       # 有空头时 → 平掉空头，回到 0
```

| 概念 | 表现 |
|---|---|
| 空头持仓 | `self.getposition(d).size` 是**负数** |
| 空头盈亏 | 价格下跌 → 持仓市值变负得更少 → 净值上升 |
| 做空现金 | 默认做空会把现金**加**给你（相当于保证金交易），可用 `set_shortcash` 改 |

---

## 六、一次真实运行的轨迹

```
[btlab] 股票池：候选 40 只 → 数据可用 38 只
[3/3] 开始 backtrader 回测 ...
  [2022-04-01] 净值跌破 40%，清仓停止交易
```

**如果看到这行**，说明历史上真的触发过熔断——它是"净值被腰斩"的直白证据。本策略的回撤是 −33.00%，还没到 60% 的线，所以通常不会触发。

---

## 七、与聚宽版的差异

| 维度 | 聚宽 | 本地版 |
|---|---|---|
| 做空 | `order_target_value(sec, -v)` | `self.sell(size=负数目标)` |
| 融券成本 | 平台可配置 | **未建模**（诚实提示） |
| 券源校验 | 平台可校验 | **未做** |
| 熔断 | 自己写 | 自己写（用 `startingcash`） |
| 股票池 | 历史成分股 | 当前成分股（幸存者偏差） |

---

## 八、回测结果怎么读

| 指标 | 数值 | 怎么理解 |
|---|---|---|
| 累计收益率 | **+17.66%** | 11 年半只有 17.66% |
| 年化收益率 | **+1.45%** | 很低 |
| 最大回撤 | **−33.00%** | 号称"对冲"，回撤却不小 |
| 夏普比率 | **0.20** | 很差 |
| 成交笔数 | **3288** | 全场最高——多空双边调仓，换手巨大 |

**要点：**

1. **它没有实现"市场中性"的理想效果**：回撤 −33%、夏普 0.20，说明多头空头的 β 并没有被很好地抵消（A 股多空两端的风格差异很大）；
2. **换手 3288 笔是最大杀手**：每月双边调仓 20 只，成本持续放血；
3. **真实世界会更差**：融券利息 8%~10% 还没算进去。

> **教学价值**：这一篇教会你两件事——① 做空在代码里怎么写；② **"理论上对冲"和"实际对冲得住"是两回事**。真实的中性化组合需要严格的风险模型（行业、市值、风格都对齐），不是"买前 10 卖后 10"这么简单。

---

## 九、易混点与常见错误

| 症状 | 原因 | 正确做法 |
|---|---|---|
| 熔断线算错 | 硬编码了初始资金 | 用 `self.broker.startingcash` |
| 同一只票既买又卖 | long/short 名单重叠 | `if set(longs) & set(shorts): return` |
| 空头方向搞反 | 忘了 `want = -want` | 空头用负股数 |
| 以为回测的收益是真实的 | 没算融券成本/券源 | 明白这是理想化上界 |
| 净值变成负数 | 没留缓冲、敞口太大 | 控制总敞口（本策略 40%+40%） |

---

## 十、自测题（不写代码也能做）

1. 为什么"买最强 10 只 + 卖最弱 10 只"能对冲掉大盘涨跌？它真的完全对冲了吗？
2. 为什么这一篇的最大回撤（−33%）比"看起来更激进"的小市值策略（−29.58%）还大？
3. 如果把融券利息（年化 9%）加进回测，收益会变成多少？（估算一下）

---

## 十一、改进方向（思考题）

1. **行业/市值中性**：先按行业和市值分组，再在**组内**做多空（这才是真正的中性化）。
2. **加融券成本**：用 `setcommission` 或资金曲线扣减模拟 8%~10% 的利息。
3. **降低换手**：改成季度调仓，或加"排名掉出前 15/20 才换"的缓冲。
4. **Beta 对冲**：改成"多头 40% + 做空股指期货 40%"，比个股做空更可行。