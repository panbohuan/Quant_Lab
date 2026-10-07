# 进阶策略 3：多空对冲策略（Long-Short Equity）· backtrader 本地版

> 类型：绝对收益 / 市场中性 ｜ 难度：★★★★★
> 前置知识：做空机制（负持仓）、`PanelStrategy`、`position.size` 符号、风险熔断
> **运行框架：backtrader（本地回测 + 免费数据）** ｜ 本策略的**聚宽云端版**见 [docs/joinquant/advanced/03_long_short.md](../../joinquant/advanced/03_long_short.md)

## 一、核心思路

这是整条学习路径里**最关键的一次认知升级**——理解「Alpha 和 Beta 的分离」。

- **Beta**：你"跟随市场"赚的钱。大盘涨 10%，你的股票也涨 10%，这 10% 就是 Beta。
- **Alpha**：你"跑赢市场"赚的钱。大盘涨 10%，你的股票涨 15%，多出的 5% 才是 Alpha。

普通多头策略赚"Alpha + Beta"。大盘暴跌时，Beta 会严重拖累收益——哪怕你选的股票都跑赢了市场，整体还是亏。

多空对冲做法：

```
1. 做多 一批最强股票（赚 Alpha + Beta）
2. 做空 一批最弱股票（赚 -Alpha - Beta，反向）
3. 多空市值相等 → Beta 部分抵消 → 剩"强股 Alpha - 弱股 Alpha" = 纯 Alpha
```

这样无论大盘涨跌，赚的是"选股能力的差价"，不赌市场方向——即"绝对收益 / 市场中性"。

本策略参数一览（文件顶部常量）：

| 参数 | 默认值 | 含义 |
|------|--------|------|
| `START` | `2015-01-01` | 回测起点 |
| `UNIVERSE_SIZE` | `40` | 沪深300 前 40 只成分股作候选池 |
| `LOOKBACK` | `60` | 动量因子回看期 |
| `LONG_NUM` / `SHORT_NUM` | `10` / `10` | 多头 / 空头只数 |
| `LONG_EXPOSURE` / `SHORT_EXPOSURE` | `0.40` / `0.40` | 多/空市值占净值比例（总敞口 0.8 倍） |
| `STOP_EQUITY_RATIO` | `0.40` | 净值跌破初始资金 40% → 清仓停交易 |

聚宽版是"多空各满仓（leverage=1.0）"，本地版保守到各 0.40，并额外加了聚宽没有的**风险熔断保险丝**。

## 二、算法结构（分步拆解）

```
每月第1个交易日 → on_rebalance(cur)
   │
   ├─ 0. 风控保险丝：总资产 < 初始资金 × 40% → close_all 并停止交易
   │
   ├─ 1. 算每只股票动量 mom = close[-1]/close[0] - 1（仅 live 标的）
   │      └─ 样本不足 long+short 只 → 跳过
   │
   ├─ 2. 排名：多头=前 long_num 只，空头=后 short_num 只（去重）
   │
   ├─ 3. 先平掉不在名单里的持仓（self.close(d)）
   │
   ├─ 4. 多头：_target_size(name, per_long, short=False)  → 目标正股数
   │
   └─ 5. 空头：_target_size(name, per_short, short=True)  → 目标负股数（做空）
```

## 三、代码逐段详解 + backtrader 语法解析（本篇重点：做空）

### 3.1 多空市值敞口参数

```python
LONG_EXPOSURE = 0.40        # 多头市值 / 净值
SHORT_EXPOSURE = 0.40       # 空头市值 / 净值
STOP_EQUITY_RATIO = 0.40    # 净值跌破初始资金 40% → 清仓停止
```

多空各占净值 40%，总敞口 0.8 倍（保守）。比聚宽示例"满仓多空（各 1.0 倍）"稳健，避免极端行情把净值打到负数。

### 3.2 做空在 backtrader 里如何实现 —— 负 `size`

backtrader **原生支持做空**：当 `self.sell()` 的股数超过当前持仓，持仓 `size` 变负数，即空头。本策略用 `_target_size` 统一表达：

```python
def _target_size(self, name, capital, cur, short=False):
    d = self.getdatabyname(name)
    price = d.close[0]
    if price <= 0:
        return
    want = round_lot(capital / price)          # 目标股数（正数）
    if short:
        want = -want                            # 空头：目标股数取负
    delta = want - self.getposition(d).size     # 与目标之差
    if delta > 0:
        self.buy(d, size=delta)                 # 差为正 → 买入补到目标
    elif delta < 0:
        self.sell(d, size=-delta)               # 差为负 → 卖出（超过 0 即转做空）
```

要点：

- **`self.getposition(d).size`** 是当前持仓股数，**正数=多仓，负数=空仓，0=无持仓**。
- 若某股当前无持仓（`size=0`），而 `want` 是负数，`delta = -want < 0` → 走 `self.sell(d, size=-delta)`，卖出超过 0 → 形成负持仓 = 做空。无需任何"融券"配置，backtrader 引擎自动处理。
- 平仓用 `self.close(d)`：无论多空，`close` 都把该标的持仓归零，方向自动判。

### 3.3 做空时的现金与盈亏口径

这是新手最容易晕的地方，逐条说清：

- **账户总资产** = 现金 + Σ(各标的 `size × 现价`)。空头 `size<0`，贡献**负市值**。
- **做空收到现金**：卖空时你"借券卖出"拿到现金，所以可用现金**变多**，这正是 a03 文件头注释说的"做空会收到现金，能买入更多多头"。
- **空头盈亏方向**：股价下跌 → `size(负) × 更低价` 的负市值变小（绝对值变小）→ 总资产上升 = 盈利；与真实融券"先卖后买、跌了赚"方向一致。
- **`d.close[0]`**：取当根收盘价（做空计算用的现价），`[0]`=当根，没问题。

### 3.3.1 空头账本：一个具体数字例子

设净值 100 万，对某股做空 `per_short = 100万 × 0.40 / 10 = 4万` 元目标市值，现价 20 元：

```
want = round_lot(40000 / 20) = 2000 股 → 取负 → -2000 股
delta = -2000 - 0 = -2000
→ self.sell(d, size=2000)       卖空 2000 股，收到现金 4 万
```

此时账户状态：

| 项目 | 数值 |
|------|------|
| 现金 | 增加 4 万（卖空收到钱） |
| 该股持仓 `size` | `-2000`（空头） |
| 该股负市值 | `-2000 × 20 = -4 万` |
| 总资产 | 现金 + 多仓市值 - 4 万（不变，因收到现金抵消） |

若之后股价跌到 18 元：负市值变为 `-2000 × 18 = -3.6 万`，总资产**上升 0.4 万** = 空头盈利。方向相反于多头，正是 Beta 中性对冲的来源。

### 3.4 风险熔断（保险丝）

```python
if self.broker.getvalue() < CASH * STOP_EQUITY_RATIO:
    self.close_all(cur)
    print(f'净值跌破 {STOP_EQUITY_RATIO:.0%}，清仓停止交易')
    return
```

`self.broker.getvalue()` 返回当前总资产。一旦净值跌到初始资金 40% 以下，立即 `close_all`（平掉所有多空持仓）并跳过本次调仓——这是对"极端行情多空两头亏损、净值被击穿"的硬止损。聚宽版没有这个保险丝，本地版更稳健。

### 3.4.1 持仓相关 API 速查

| API | 作用 |
|-----|------|
| `self.getposition(d).size` | 该标的持仓股数（正=多、负=空、0=无） |
| `self.getposition(d).price` | 持仓成本均价 |
| `self.getpositionbyname('510300')` | 按名取持仓 |
| `self.close(d)` | 平掉该标的全部持仓（多空都归零，方向自动判） |
| `if not self.position:` | 判断首个标的是否空仓（`size == 0`） |

本策略的 `close_all`（`PanelStrategy` 提供）就是遍历 `self.tradables`，对 `getposition(d).size != 0` 且 `live` 的标的调用 `self.close(d)`。

### 3.5 `PanelStrategy` 与 `live()` 停牌过滤

和 a02 一样继承 `PanelStrategy`，用 `self.live(d, cur)` 过滤停牌/未上市个股；股票池用 `load_universe` 剔除上市太晚的标的（候选 40 → 数据可用 35，日志可见）。动量计算同样用 `hist_close(d, lookback+1)` 的 序列语义，无未来函数。

### 3.6 索引方向复核

| 写法 | 含义 | 本策略用法 |
|------|------|-----------|
| `d.close[0]` | 当根收盘价 | 算现价、`_target_size` |
| `closes[-1]`（list） | 最新一根收盘 | 动量分子（序列语义！） |
| `closes[0]`（list） | 最旧一根收盘 | 动量分母 |

全程未出现 Line 正索引 `[1]`，无未来函数。

## 四、与聚宽版的差异

| 维度 | 聚宽云端版 | backtrader 本地版 |
|------|-----------|-------------------|
| 做空表达 | `order_target_value(s, -市值)`（融券卖出） | **负 `size`**：`sell` 超过持仓 → `position.size<0`（本地直接表达空仓） |
| 融券限制 | 受券源/标的/利息约束（回测已简化） | **完全理想化**：不计融券利息、不做券源校验（回测收益偏乐观） |
| 多空敞口 | `leverage=1.0`，多空各满仓（总敞口 2 倍） | 各 0.40（总敞口 0.8 倍，保守） |
| 风险熔断 | 无 | 净值跌破 40% 强制 `close_all` 停交易 |
| 触发方式 | `run_monthly(rebalance, 1, time='09:30')` | `PanelStrategy` 的 `(年,月)` 变化检测 |
| 股票池 | `get_index_stocks('000300')` + `filter_stocks`（ST/涨跌停） | `load_index_members` + `load_universe` + `live()` 过滤 |
| 下单口径 | `order_target_value`（目标市值） | `round_lot` 后 `buy/sell(size=差额)`（目标股数） |
| 数据来源 | 聚宽平台 | akshare 免费源（当前沪深300成分，幸存者偏差） |

核心差异是**做空机制**：聚宽靠"融券（`order_target_value` 传负）"表达，本地靠"负持仓"表达——二者盈亏方向一致，但本地不计融券成本，回测绝对收益会偏乐观，实盘需打折。

## 五、回测结果（真实数据）

区间 2015-01-05 ~ 2026-09-30（2855 个交易日），初始资金 100 万元，基准沪深300。数据来自 `results/logs/bt_a03_long_short.log`。

| 指标 | 数值 |
|------|------|
| 累计收益率 | 17.66% |
| 年化收益率 | 1.45% |
| 基准累计收益率 | 19.66% |
| 超额收益 | -2.01% |
| 最大回撤 | -33.00% |
| 夏普比率 | 0.20 |
| 年化波动率 | 9.42% |
| 日胜率 | 50.94% |
| 总成交笔数 | 3288 笔 |
| 累计换手率 | 9695.84% |

解读：多空对冲并**没有跑赢**沪深300（超额 -2.01%），夏普仅 0.20，是 5 篇里最弱的一篇。原因：动量因子在 A 股多头无效 + 空头也亏，Beta 中性没带来稳定 Alpha；且 3288 笔成交、9695% 换手意味着摩擦成本极高。但**回撤 -33.00% 与基准接近、波动 9.42% 偏低**，说明"多空抵消 Beta"在波动层面有效，只是选股 Alpha 没赚出来。结论：市场中性策略的难点从来不是"对冲"，而是"选股 Alpha 是否真存在"。

## 六、改进方向（思考题）

1. **更严格 Beta 中性**：用回归算每只股票 Beta，按 Beta 加权多空（而非简单等市值），或在行业内配对（`industry_map`），剥离行业 Beta。
2. **多因子替代动量**：动量在 A 股易失效，可叠加估值/质量/低波因子（`value_panel` 取 PE/PB），做"多低估值空高估值"的基本面中性。
3. **加止损与熔断细化**：除净值熔断外，对单只空头设 `buy_bracket` 止损腿，防止轧空（空头亏损无上限）；并对空头单独限制占比，避免单一票爆雷。
