# 进阶策略 6：ETF 轮动策略（ETF Rotation）· backtrader 本地版

> 类型：资产配置 / ETF 轮动 ｜ 难度：★★★★☆ ｜ 前置知识：backtrader 多数据源、Line 索引、PanelStrategy 调仓骨架
> **运行框架：backtrader（本地回测 + 免费数据）** ｜ 本策略的**聚宽云端版**见 [docs/joinquant/advanced/06_etf_rotation.md](../../joinquant/advanced/06_etf_rotation.md)

## 一、核心思路

前面的策略都在「选个股」，ETF 轮动第一次升级到「**选资产**」。ETF（交易型开放式指数基金）是「一篮子股票的打包」，像股票一样买卖，但底层是一整个指数。本策略在宽基、成长、商品、跨境、债券五类 ETF 之间，买入近期表现最强的几只，实现大类资产配置。

为什么有效？大类资产之间存在「跷跷板」效应：股市弱时黄金/债券可能强，A 股弱时纳指/黄金可能强。永远满仓单一资产会暴露在该资产的系统性风险里；而能在资产间轮动，就能「东方不亮西方亮」，捕捉结构性机会、平滑波动。

本地的 backtrader 版相比聚宽版多做了一件事——**风险开关**：每月比较各 ETF 的动量，若最强的一只动量仍为负（意味着所有风险资产都在跌），就一次性把所有仓位转到国债 ETF（511010）避险。这是「趋势跟踪 + 尾部防御」的极简模板。

给新手的直觉：动量 = 「最近谁涨得好就买谁」；风险开关 = 「如果所有资产都在跌，就躲进债券」。

```
动量得分（过去 LOOKBACK 日累计涨幅）：
    mom = close[-1] / close[0] - 1.0          # 注意：close 来自 list.get()，list[-1] 是最新一根
    其中 close[0] = LOOKBACK+1 根前（最旧），close[-1] = 当根（最新）
```

> 数据口径提示：本地版 ETF 用「不复权价 + 加回历史累计分红」的含分红口径（见 btlab.datasource 的 `_apply_etf_dividend`），以避免新浪 ETF 接口只给不复权价导致收益被低估。详见第四节。

### 大类资产配置直觉（给新手）

「不把鸡蛋放一个篮子里」大家都知道，但 ETF 轮动比「随便分散」更讲究：

- **相关性低才是关键**。债券和股票常「股债跷跷板」，黄金与 A 股相关性也低。把高度相关的资产拼一起不算分散（比如同时买沪深300ETF 和中证500ETF，本质还是 A 股大盘）。
- **动量轮动 vs 风险平价**。本策略是动量轮动（追涨强的）；风险平价是「按波动贡献相等」配权重，不看涨跌。两者可结合：先动量选资产，再风险平价分配权重。
- **为什么持有 TOPN=3 而不是 1**。只买最强 1 只会把风险压在单一资产上；持有 3 只既能吃到轮动收益，又保留一定分散。但 7 只候选池很小，权重天然集中——这是 ETF 轮动固有限制。
- **国债 ETF 是「避风港」不是「收益源」**。它的长期收益远低于股票 ETF，风险开关只在「全市场都在跌」时起作用，平时应让风险资产去赚钱。

## 二、算法结构（分步拆解）

```
每月第 1 个交易日触发 on_rebalance(cur)
   │
   ├─ 1. 遍历 self.tradables（7 只 ETF，国债除外）
   │      └─ live(d, cur) 过滤停牌/未上市 → hist_close(d, LOOKBACK+1) 取回看窗口
   ├─ 2. 计算每只动量 mom = closes[-1] / closes[0] - 1.0
   ├─ 3. 按动量降序取 TOPN 只
   │
   ├─ 4. 风险开关判断
   │      ├─ 最强动量 best <= 0 且定义了 defensive
   │      │      └─ equal_weight_order([国债ETF]) → 全仓避险，return
   │      └─ 否则 equal_weight_order(target) → 持有最强 TOPN 只
   └─ （每次调仓先卖不在名单的持仓，再买名单内标的，均经 round_lot 取整手）
```

## 三、代码逐段详解 + backtrader 语法解析

### 3.1 多 ETF 数据源的组织

backtrader 不区分「股票」和「ETF」数据源，统一用 `bt.feeds.PandasData` 装入。本策略把 7 只 ETF 的日线装进一个 `dict`，键是带中文名的字符串，值是 akhsare 返回的 DataFrame：

```python
data = {}
for code, name in POOL.items():                 # POOL：6 只风险资产
    data[f'{name}({code})'] = load_daily(code, start=START, end=END)
data[f'{DEFENSIVE_NAME}({DEFENSIVE})'] = load_daily(DEFENSIVE, ...)   # 国债ETF
data['__CAL__'] = load_daily(BENCHMARK, ...)    # 基准当日历源（每交易日都有行情）
```

`__CAL__` 是 backtrader 本地版多标的的「时钟源」：`PanelStrategy` 用它判断「今天是不是交易日」，避免某只 ETF 停牌时 `next()` 拿不到当前日期（详见 base doc §4.3）。`self.tradables` 自动排除 `__CAL__`。

### 3.2 `PanelStrategy.on_rebalance(cur)` 与调仓触发

`PanelStrategy`（`btlab/runner.py`）把「每月第 1 个交易日」的调度写进了基类：它在 `next()` 里读 `self.cal.datetime.date(0)` 得到当前日期，按 `(年, 月)` 去重，月份一变就调一次 `on_rebalance(cur)`。`cur` 是 `datetime.date` 对象，作为「今天」传给策略。

子类只需实现 `on_rebalance(cur)`，不用自己写定时器——这是 backtrader 与聚宽 `run_monthly` 的对应物（对照表见 base doc §13）。把调仓逻辑放在 `on_rebalance` 里而非 `next`，能强制「收盘出信号、次日开盘成交」的默认时序（base doc §9.1）。

### 3.3 动量计算与 Line/get 的索引语义（重点）

```python
closes = self.hist_close(d, self.p.lookback + 1)
scores[d._name] = closes[-1] / closes[0] - 1.0
```

`hist_close(d, n)` 内部调 `d.close.get(size=n)`，返回的是 **`array.array`**（不是 Python list；最旧在前、最新在后），不是 backtrader 的 Line 对象。因此这里的 `closes[0]` 是窗口最旧一根、`closes[-1]` 是当根（最新）——与 base doc §2.2 强调的「Line 语义」不同：

| 写法 | 含义 |
|------|------|
| `d.close[0]` | Line 索引：当根收盘价（backtrader 专用） |
| `d.close[-1]` | Line 索引：上一根（昨天） |
| `d.close.get(size=n)` 返回的 array | `[0]`=最旧、`[-1]`=最新（数组，索引语义同 list） |

`hist_close` 在 `len(d) < n` 时返回 `None`，天然挡住了「首根 K 线负索引绕圈」的未来函数陷阱（base doc §2.2 危险信号 1）。

### 3.4 风险开关与防御资产切换

```python
target = sorted(scores, key=scores.get, reverse=True)[:self.p.topn]
best = max(scores.values())
if best <= 0 and self.p.defensive:
    d = self.getdatabyname(self.p.defensive)
    if self.live(d, cur):
        self.equal_weight_order([self.p.defensive], cur)
        return
self.equal_weight_order(target, cur)
```

防御资产（国债 ETF）在第一步动量排序时被 `if d._name == self.p.defensive: continue` 排除，所以它**永远不参与「谁最强」的排名**，只在风险开关触发时才被选中。日志显示风险开关在 2015-09、2018-05、2022-02 触发过 3 次。

### 3.5 `equal_weight_order` 的权重归一化与 cap

`equal_weight_order(names, cur, cap=0.98)`（`btlab/runner.py:273`）：先把每个标的目标市值设为 `broker.getvalue() * cap / len(names)`，`cap=0.98` 留 2% 现金缓冲防 `Margin` 拒单；对名单内每只，算目标股数 `round_lot(per / price)`，`round_lot` 向下取整到 100 股（A 股整手），再 `self.buy/sell(size=delta)` 把差额补齐。`equal_weight_order` 先清掉不在名单里的旧持仓、再买入，避免同日买卖冲突。

`value_weight_order` 与之不同：按 `{name: 权重}` 字典，先 `total_w = sum(weights.values())` 做**归一化**，再 `total * cap * w / total_w` 算每只目标市值——权重不必先归一，工具层帮你归一。本策略用等权，故调 `equal_weight_order`。

### 3.6 关键参数表

| 参数 | 默认 | 含义 |
|------|------|------|
| `POOL` | 6 只风险 ETF | 候选资产池（宽基/成长/商品/跨境） |
| `DEFENSIVE` | 511010 国债ETF | 避险资产（不参与动量排序） |
| `TOPN` | 3 | 持有动量最强几只 |
| `LOOKBACK` | 60 | 动量回看交易日数 |
| `rebalance` | 'monthly' | 每月第 1 个交易日触发 |

### 3.7 backtrader 索引方向速查（防未来函数，必记）

| 写法 | 含义 | 能否在回测中用 |
|------|------|----------------|
| `d.close[0]` | 当根收盘价（**Line 索引**） | ✅ |
| `d.close[-1]` | 上一根（昨天） | ✅ |
| `d.close[-2]` | 上上根（前天） | ✅ |
| `d.close[1]` | 下一根（明天） | ❌ 未来数据，禁用 |
| `d.close.get(size=n)` 返回的 array | `[0]`=最旧、`[-1]`=最新（数组） | ✅（序列语义，与 Line 相反） |

两个易错点：**(1)** `line[1]` 是未来，永远不能用；**(2)** 首根 K 线上的 `[-1]` 会静默绕到数据集最后一行（base doc §2.2 危险信号 1），本策略靠 `hist_close` 的 `len(d) < n` 判空挡住。注意 `get()` 返回的是 `array.array`（不是 list），`[-1]` 是「最新」——这与 Line 的 `[-1]=昨天` 正好相反，务必分清。

### 3.8 `getdatabyname` 与多标的持仓查询

防御资产切换用 `self.getdatabyname(self.p.defensive)` 按名字取数据源。backtrader 多标的下**不能用 `self.data`**（`self.data` 只指向第一个 adddata 的数据源），必须用 `getdatabyname(name)` 或遍历 `self.tradables`。`self.getposition(d).size` 读某标的持仓股数，`size == 0` 即空仓——`equal_weight_order` 内部正是用它判断是否要卖出旧持仓。

### 3.9 回测时序：收盘出信号 → 次日开盘成交

`on_rebalance(cur)` 在当根 K 线收完后被调用（`cur = self.cal.datetime.date(0)`），`self.buy/sell` 默认在**下一根开盘**成交（base doc §9.1）。这是 backtrader 天然的防未来函数保护：你今天收盘看到信号、明天开盘才真成交，不可能用到明天的价格。本仓库 20 个策略一律如此，文件头已注明「当根收盘出信号 → 次日开盘成交」。

### 3.10 一个完整例子：某月动量排序

假设某调仓日 6 只风险 ETF 的 60 日动量分别为：沪深300 +0.05、中证500 +0.08、创业板 +0.12、上证50 +0.03、黄金 +0.02、纳指 -0.01。排序后 TOPN=3 = [创业板, 中证500, 沪深300]，国债 ETF 不参与排名。若最强动量（创业板 +0.12）> 0，则等权买入这 3 只；若全部为负（如 2015-09、2018-05、2022-02 真实触发），则整仓转入国债 ETF。日志里这三次风险开关触发，正是「动量全负」的尾部防御。

### 3.11 ETF 轮动的常见坑

1. **动量追高**：动量最强的资产可能已涨到高位，追进去正好接盘；风险开关缓解但不根治（只对「全负」反应）。
2. **换手成本**：ETF 虽免印花税，但月频轮动 + 6~7 只大池仍有佣金和滑点，回测显示累计换手率 28441%（见第五节）。
3. **跨境/商品 ETF 特殊性**：纳指 ETF 受汇率和美股时差影响，黄金 ETF 受国际金价影响，波动规律与 A 股不同，不能简单当成「另一个 A 股 ETF」。
4. **候选池过小**：7 只候选池让轮动空间有限，权重天然集中（TOP3 各 1/3），这是 ETF 轮动固有限制，池子越大越能分散。

### 3.12 费用与滑点如何在 backtrader 落地

`run_strategy` 内部调 `build_cerebro`，已装配 `AStockCommission`（base doc §9.4）：佣金双边 0.03%、印花税仅卖出 0.05%、单笔最低 5 元。`_getcommission(size, price, pseudoexec)` 里用 `size < 0` 判卖出方向才加印花税。滑点用 `set_slippage_perc(0.0002)`（单边 0.02%）：买入成交价 = 价 ×(1+0.02%)、卖出 = 价 ×(1-0.02%)。这些费用真实计入净值——高换手策略若忽略，收益会被虚高好几点，所以本仓库 20 个策略统一用这套 A 股口径。

## 四、与聚宽版的差异

| 维度 | 聚宽版 a06 | backtrader 本地版 |
|------|-----------|-------------------|
| 候选池来源 | `get_all_securities(['etf'])` 动态取全市场 ETF（约 10 只） | 硬编码 7 只代表性 ETF（含国债），保证长历史可复现 |
| 风险开关 | 无 | 新增：最强动量≤0 时全仓国债 ETF |
| 触发方式 | `run_monthly(rebalance, 1)` | `PanelStrategy` 按 `(年,月)` 去重触发 `on_rebalance` |
| 下单口径 | `order_target_value(sec, v)` 目标市值 | `equal_weight_order` → `round_lot` 整手股数 |
| 费用/滑点 | `set_order_cost(type='fund')` + `FixedSlippage(0.02)` | `AStockCommission`（佣金双 0.03%、印花卖 0.05%、最低 5 元）+ `set_slippage_perc(0.0002)` |
| 复权口径 | 平台 `use_real_price` 给真实价 | **ETF 不复权价 + 加回历史累计分红**（含分红口径） |
| 数据可得性 | 云端有完整 ETF 历史 | 免费源仅固定几只长历史 ETF，故候选池更小 |

ETF 复权口径是本例特有差异：聚宽端用真实价直接算收益；本地端新浪只给不复权价，`load_daily` 对 ETF 请求 hfq 时调用 `_apply_etf_dividend`，把「截至当日累计分红」加回 open/high/low/close，使得 `(价末-价初)/价初` 等于「价格涨跌 + 期间分红」的真实总收益。两只口径长期收益接近，但短期分红密集期会有差异。

## 五、回测结果（真实数据）

来源：`results/logs/bt_a06_etf_rotation.log`（区间 2014-01-02 ~ 2026-09-30，3100 个交易日，初始资金 100 万）。

| 指标 | 数值 |
|------|------|
| 累计收益率 | 252.68% |
| 年化收益率 | 10.79% |
| 最大回撤 | -54.07% |
| 夏普比率 | 0.46 |
| 年化波动率 | 30.41% |
| 基准（沪深300）累计收益 | 87.67% |
| 超额收益 | 165.01% |
| 总成交笔数 | 573 |
| 累计换手率 | 28441.63% |

解读：策略显著跑赢沪深300（超额 165%），但最大回撤高达 -54%、夏普仅 0.46——说明「资产轮动 + 国债避险」虽降低了单一资产崩盘风险，却没逃过 2015、2018、2022 等系统性下跌（风险开关只在动量全负时触发，对「缓跌」反应滞后）。回撤大、夏普低是这类高波动多资产策略的典型特征，改进方向见第六节。

## 六、改进方向（思考题）

1. **加趋势/波动过滤**：月内若基准处于下行通道则降仓到国债，而不只等「动量全负」才触发，可压低 -54% 的最大回撤。
2. **改权重为风险平价**：先用波动率倒数分配权重，再叠加动量选资产，降低单一高波动 ETF（如纳指）的权重集中度。
3. **扩大候选池**：接入 `get_all_securities` 等价的本地 ETF 清单（债券、REITs、海外），让轮动空间更大；若拿到分钟级数据，可把调仓频率提到周度捕捉更快趋势。
