# 策略 6：双因子组合选股（Two-Factor Rank）· backtrader 本地版

> 策略类型：双因子选股（量价 + 规模） ｜ 难度：★★★☆☆ ｜ 前置知识：backtrader 的 next/Line 索引、pandas Series.rank、策略 1~5
> **运行框架：backtrader（本地回测 + 免费数据）** ｜ 本策略的**聚宽云端版**见 [docs/joinquant/beginner/s06_two_factor_rank.md](../../joinquant/beginner/06_two_factor_rank.md)

## 一、核心思路

单因子选股（如只看动量）容易受单一风格拖累，遇到该风格失效的年份会大幅跑输。本策略把两个逻辑互补的因子合起来：

| 因子 | 方向 | 经济含义 |
|------|------|----------|
| 动量 momentum | 越大越好 | 过去 60 个交易日涨得多的，短期惯性更强 |
| 市值 total_mv | 越小越好 | 小市值股票有"小盘溢价"，弹性更高 |

**为什么用"排名法（Rank Sum）"而不是"数值法"**：动量是一个百分比（如 0.08），市值动辄几百亿，两者量纲差太远，直接相加量级的项会一统天下。排名法先把每个因子在截面内排成"名次"（1、2、3…），让两列变成同一尺度再相加。

综合分公式为：

$$score_i = rank(\text{-momentum}_i) + rank(\text{total\_mv}_i)$$

其中 `rank(-momentum)` 等价于"动量越大、名次越小"，`rank(total_mv)` 是"市值越小、名次越小"，两项名次相加后，**综合名次越小**代表"动量强且市值小"，取最小的 TOPN 只。

> 给新手的直觉：高考填志愿，你按"体育成绩排名"和"个子大小排名"各排一次，两个名次相加，总分最低的人就是"又跑得快又个子小"的那批。排名法只看先后、不看差距（这点和策略 7 的 z-score 打分不同）。

## 二、算法结构（分步拆解）

```
每月首个交易日触发 on_rebalance(cur)
   │
   ├─ 1. 取市值快照
   │      └─ asof(self.mv, cur)  → 只取不晚于 cur 的市值面板，杜绝未来数据
   │
   ├─ 2. 逐标的算动量因子（量价类，来自行情）
   │      └─ self.hist_close(d, lookback+1)  → 最近 61 根收盘价(list)
   │          mom = closes[-1] / closes[0] - 1.0   (list[-1]=最新, list[0]=最旧)
   │
   ├─ 3. 两因子对齐到共同股票集合
   │      └─ mom.index.intersection( mv[mv>0].index )
   │
   ├─ 4. 排名打分：score = (-mom).rank() + mv.rank()
   │
   └─ 5. equal_weight_order(综合分最小的前 TOPN 只, cur)
          ├─ 先卖：不在名单且仍有持仓的标的 → self.close
          └─ 再买：名单内标的对齐到目标股数（整手取整）
```

## 三、代码逐段详解 + backtrader 语法解析

本策略是 `PanelStrategy`（`btlab/runner.py` 的多标的骨架）的子类。`PanelStrategy` 已经帮你做好了三件事：用 `__CAL__` 基准指数当"交易日历时钟"、按 `rebalance` 参数自动调度 `on_rebalance`、提供 `equal_weight_order` 等下单工具。你只需写"算因子 + 选股"这一层。

### 3.1 类声明与 params

```python
class TwoFactorRank(PanelStrategy):
    params = (('topn', TOPN), ('lookback', LOOKBACK), ('rebalance', 'monthly'),)
```

`params` 是 backtrader 的标准写法（见 `backtrader详解` §7.1），元组里每个 `(名字, 默认值)` 会被收集成 `self.p.xxx`。`rebalance='monthly'` 告诉骨架"每月第 1 个交易日触发一次 `on_rebalance`"（`daily`/`weekly`/`monthly` 三选一）。

### 3.2 `__init__` 里预加载面板

```python
def __init__(self):
    super().__init__()
    codes = [d._name for d in self.tradables]
    self.mv = value_panel(codes, 'total_mv')
```

`self.tradables` 是 `PanelStrategy` 过滤掉 `__CAL__` 后的"真正可交易标的"列表，每个 `d` 的 `._name` 是回测引擎里注册的名字（即 `load_universe` 传入的归一化代码）。`value_panel(codes, 'total_mv')`（`btlab/runner.py` §17.2）把多只股票的"总市值"拼成一张面板 DataFrame（index=日期, columns=代码）。**面板在 `__init__` 里一次性预加载**，调仓时只切片取当天那一行，避免每次都联网。

### 3.3 `on_rebalance`：调仓主逻辑

骨架的 `next()` 在每根 K 线被调用，但内部已判断"月份是否变化"——只有进入新月份的第一根才真正调用 `on_rebalance(cur)`，`cur` 是当天的 `datetime.date`，也是你所有"防未来函数"的基准时间。

**(1) 市值快照——`asof` 严格按时间切片**

```python
mv = asof(self.mv, cur)
if mv is None:
    return
```

`asof(panel, cur)`（§17.2）的核心代码是 `panel.loc[:pd.Timestamp(cur)].iloc[-1]`：只取"不晚于 cur"的最近一行。哪怕数据里恰好有 cur 之后才公告的市值，也被这一刀切掉——这是本地回测防未来函数的第一道闸门。

**(2) 动量因子——`hist_close` 取最近 n 根收盘价**

```python
for d in self.tradables:
    if not self.live(d, cur):
        continue
    closes = self.hist_close(d, self.p.lookback + 1)   # list，含今日
    if closes is None or closes[0] <= 0:
        continue
    mom[d._name] = closes[-1] / closes[0] - 1.0
```

`self.live(d, cur)` 判断"这只票今天有没有行情"（停牌/未上市时它的时间会停在旧日期）。`self.hist_close(d, n)` 返回 `d.close.get(size=n)`——一个**普通 Python list**，`None` 表示数据不足 n 根。这里必须分清两种索引语义：

- **Line 对象** `d.close[0]` = 当根、`d.close[-1]` = 昨天（详见 `backtrader详解` §5.1，**绝不能用 `d.close[1]`，那是明天**）；
- **list** `closes[-1]` = 列表最后一个 = **最新**（今天），`closes[0]` = 最旧（60 天前）。这是 list 的常规语义，与 Line 的负索引恰好相反，切勿混淆。

动量 = `closes[-1]/closes[0] - 1` 即"60 个交易日累计涨幅"。`hist_close` 内部有 `if len(d) < n: return None` 的守卫，所以**拿到的全是已经走完的 K 线**，天然不会偷看未来。

**(3) 因子对齐**

```python
common = mom.index.intersection(mv[mv > 0].index)
if len(common) < self.p.topn:
    return
mom, mv = mom[common], mv[common]
```

两个因子来源不同（动量来自行情、市值来自面板），股票集合求交集，只保留两边都有效的标的，避免某只股票只有一个因子有值而报错。

**(4) 排名打分与选股**

```python
score = (-mom).rank() + mv.rank()
names = score.sort_values().index[:self.p.topn].tolist()
self.equal_weight_order(names, cur)
```

`Series.rank()` 默认升序排名：市值越小名次越靠前（数值越小）。动量要"越大越好"，所以先取 `-mom` 再排名，等价于"动量越大名次越小"。两者相加后 `sort_values()` 升序，取最前面的 TOPN 只。

### 3.4 `equal_weight_order`：先卖后买 + 整手取整

`PanelStrategy.equal_weight_order`（§17.2）把名单内标的都调到"等权市值"：

```python
per = self.broker.getvalue() * cap / len(live_names)   # cap=0.98 留 2% 现金缓冲
for d in self.tradables:
    if d._name not in live_names and self.getposition(d).size and self.live(d, cur):
        self.close(d)                                    # 1) 先卖：腾出现金
for name in live_names:
    d = self.getdatabyname(name)
    price = d.close[0]                                    # 当根收盘价
    delta = round_lot(per / price) - self.getposition(d).size
    if delta > 0:
        self.buy(d, size=delta)                          # 2) 再买/调仓
    elif delta < 0:
        self.sell(d, size=-delta)
```

要点：

- `self.broker.getvalue()` 是当前总资产（现金+持仓市值），乘 `cap=0.98` 是**留 2% 现金缓冲**，防止手续费/价格波动导致买入时现金不足被拒（`Margin`）。
- **先卖后买**的顺序很关键：先把不在名单里的持仓清掉，腾出现金，再买入新标的，避免"想买却没钱"。
- `round_lot(per/price)` 把股数**向下取整到 100 的整数倍**（A 股 1 手 = 100 股，详见 `backtrader详解` §7.4 坑 5）。backtrader 本身不懂整手，必须自己取整。
- `self.getposition(d).size` 是当前持仓股数；`delta` 是"目标股数 − 当前股数"的**差额**，正数补买、负数卖出，天然实现再平衡。
- 成交时点遵循 backtrader 默认规则（`§5.6`）：`next()` 在当根收盘后调用 → 订单在**下一根开盘价**成交，自动免疫未来函数。

### 3.5 `PanelStrategy` 的月份调度与 `__CAL__` 时钟

你只写了 `on_rebalance`，但"每月触发一次"是骨架替你做的。核心在 `runner.py`：

```python
def next(self):
    cur = self.cal.datetime.date(0)          # 当前交易日（来自 __CAL__ 基准指数）
    mode = self.p.rebalance
    key = (cur.year, cur.month) if mode == 'monthly' else cur  # 月份变化=新 key
    if key == self._last_key:
        return                                 # 同月，跳过
    self._last_key = key
    self.on_rebalance(cur)

def prenext(self):
    self.next()                                # 数据不足期也尽量推进，尽早开始
```

`self.cal` 是喂进来的 `__CAL__` 基准指数（每个交易日都有行情），专门当"时钟"——否则某只股票停牌时你无法判断今天是几号（`backtrader详解` §14）。`(cur.year, cur.month)` 作 key，跨月才触发一次 `on_rebalance`，天然实现"每月首个交易日调仓"。`prenext` 转调 `next` 让策略在上市初期数据不足时也尽早进入调度。注意：`next()` 在当根**收盘后**被调用，订单默认**次日开盘**成交（§5.6），信号不踩未来。

## 四、与聚宽版的差异

| 维度 | 聚宽云端版（s06） | backtrader 本地版（bt_s06） |
|------|-------------------|------------------------------|
| 触发方式 | `run_monthly(rebalance, 1, time='09:30')` 定时器 | `PanelStrategy` 的 `next()` 判断月份变化 → `on_rebalance(cur)` |
| 股票池 | `get_all_securities` 全市场 + `filter_stocks` 过滤 ST/停牌/次新/涨跌停 | `load_index_members('000300')[:40]` 取沪深300**当前**前 40 只 |
| 市值来源 | `get_fundamentals(query(valuation.market_cap))` | `value_panel(codes,'total_mv')` + `asof` 切片 |
| 动量计算 | `attribute_history(s, 60, '1d', 'close')` | `self.hist_close(d, 61)` 取 list 后算涨幅 |
| 下单口径 | `order_target_value(s, per_value)` 按金额 | `equal_weight_order` 先算目标股数再 `self.buy/sell(size=...)` 整手 |
| 数据时效 | 云端实时基本面 | 免费源（东方财富估值约 2018 年起），非历史成分 → 有幸存者偏差 |
| 手续费 | `OrderCost(...)` 同口径 | `AStockCommission`（佣金双边0.03%、印花税仅卖出0.05%、最低5元、滑点0.02%） |

**最关键的本地差异**：聚宽用 `get_all_securities` 能拿到"当时"的全市场，本地免费源只给"当前"指数成分股，且估值数据从 2018 年才有——因此本策略实际只在沪深300 当前前 40 只里选股，且候选 40 → 数据可用 38 只。**收益偏乐观，属典型幸存者偏差**，实盘勿直接套用。

## 五、回测结果（真实数据）

数据来源：`results/logs/bt_s06_two_factor_rank.log`（本地 backtrader 实跑，未编造）。

| 指标 | 数值 |
|------|------|
| 回测区间 | 2018-01-02 ~ 2026-09-30（2123 个交易日） |
| 初始 / 期末资金 | 100 万 → 8,836,258 元 |
| 累计收益率 | +783.63% |
| 年化收益率 | 29.52% |
| 基准（沪深300）累计 | +6.61% |
| 超额收益 | +777.01% |
| 最大回撤 | -26.40% |
| 夏普比率 | 1.17 |
| 年化波动率 | 24.73% |
| 日胜率 | 53.35% |
| 总成交笔数 | 1210 |
| 累计换手率 | 19054.72% |

**解读**：双因子排名法在 2018–2026 这轮里显著跑赢沪深300（年化 29.5% vs 基准个位数），夏普 1.17 也不错，回撤控制在 -26%。但 +783% 的累计收益建立在"沪深300 当前成分股 + 小市值暴露"上，**幸存者偏差与小规模股溢价被放大**，且 19054% 的超高换手率意味着摩擦成本敏感度极高，真实环境收益会明显打折。

## 六、改进方向（思考题）

1. **加去极值/中性化**：排名法对极端值不如 z-score 稳健，可先对动量做分位截尾（`Winsorize`），或参考策略 8 对市值做中性化。
2. **换行业中性化**：当前小市值暴露过强，组合可能在某一行业上集中，可加入行业约束分散风险。
3. **降换手**：每月全换仓导致累计换手近 20 倍，可改为"只换出/换入变动较大的标的"或对调仓加阈值，降低摩擦成本。
