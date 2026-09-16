# 策略 1：双均线趋势跟踪（MA Cross）

> 策略类型：技术指标择时（单标的） ｜ 难度：★☆☆☆☆ ｜ 前置知识：Python 基础、K线/均线概念

## 一、核心思路

**均线（MA，Moving Average）** 是过去 N 个交易日收盘价的算术平均值，用于平滑价格波动、观察趋势方向：

- **短期均线**（如 5 日）对价格变化反应快；
- **长期均线**（如 20 日）更平滑，代表中期趋势。

当短期均线**从下方向上穿过**长期均线（**金叉**），通常被认为是上涨趋势启动的信号，策略买入；
当短期均线**从上方向下穿过**长期均线（**死叉**），被认为是下跌趋势信号，策略卖出。

这就是趋势跟踪（Trend Following）策略的雏形：**不预测涨跌，只跟随趋势，让利润奔跑、截断亏损。**

## 二、算法结构（分步拆解）

```
每天 14:50 触发 trade(context)
   │
   ├─ 1. 取过去 21 个交易日的收盘价（attribute_history）
   │
   ├─ 2. 计算今天与昨天的 5 日、20 日均线
   │
   ├─ 3. 判断交叉：
   │      金叉（short上穿long）→ order_target_value 满仓买入
   │      死叉（short下穿long）→ order_target_value 清仓
   │
   └─ 4. log.info 记录操作
```

## 三、代码逐段详解 + 函数解析

### 3.1 `initialize(context)` —— 策略的"入口"

聚宽回测引擎启动时会**先调用一次** `initialize`，用于配置全局设置和注册定时任务。`context` 是一个贯穿全局的上下文对象，里面保存了账户、持仓、当前时间等信息。

```python
def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_order_cost(OrderCost(...), type='stock')
    run_daily(trade, time='14:50')
```

### 3.2 `set_order_cost` —— 交易成本（重要！）

真实交易是有成本的，忽略它会导致回测收益虚高。`OrderCost` 常用参数：

| 参数 | 含义 | 本例取值 |
|------|------|----------|
| `open_tax` | 买入印花税 | 0 |
| `close_tax` | 卖出印花税 | 0.001（0.1%） |
| `open_commission` | 买入佣金 | 0.0003（0.03%） |
| `close_commission` | 卖出佣金 | 0.0003 |
| `min_commission` | 单笔最低佣金 | 5 元 |

简单使用例子：
```python
set_order_cost(OrderCost(open_tax=0, close_tax=0.001,
                         open_commission=0.0003, close_commission=0.0003,
                         min_commission=5), type='stock')
```

### 3.3 `run_daily(func, time=...)` —— 定时任务

这是聚宽最常用的"定时器"，让某个函数在**每个交易日**的指定时间运行。

- `time` 可取值：`'open'`（开盘）、`'before_open'`（开盘前）、`'after_close'`（收盘后）、`'14:50'` 等具体时刻，或 `'every_bar'`（每个 bar）。
- 本例选 `14:50` 是因为临近收盘、当日价格基本确定，信号更稳定、不易被盘中波动干扰。

```python
run_daily(trade, time='14:50')   # 每个交易日 14:50 运行 trade
```

> 对比：还有 `run_weekly(func, weekday, time)`（每周）和 `run_monthly(func, monthday, time)`（每月第 monthday 个交易日），后面的选股策略会用到。

### 3.4 `attribute_history(security, count, unit, fields, df=True)` —— 取历史行情

获取**单个标的**过去 `count` 个 `unit` 周期的数据，返回 DataFrame（`df=True`）或字典。

```python
closes = attribute_history('510300.XSHG', 21, '1d', 'close', df=True)['close']
# 返回一个 Series，索引是时间，值是收盘价，共 21 根日K线
```

- `unit`：`'1d'`（日线）、`'1m'`（分钟线）等。
- `fields`：`'close'`、`'open'`、`'high'`、`'low'`、`'volume'` 等，可传列表 `['close','volume']`。

### 3.5 均线计算与交叉判断（pandas 切片）

`closes` 是一个 pandas Series，`iloc` 按位置切片：

```python
short_ma_now  = closes.iloc[-5:] .mean()   # 最近5日收盘价均值 → 今天5日均线
short_ma_prev = closes.iloc[-6:-1].mean()  # 往前平移一天的5日均值 → 昨天5日均线
```

交叉判断逻辑：
```python
# 今天短>长，且昨天短<=长，说明短均线刚刚上穿 → 金叉
if short_ma_now > long_ma_now and short_ma_prev <= long_ma_prev:
    order_target_value(security, context.portfolio.total_value * 0.95)
```

### 3.6 `order_target_value(security, value)` —— 目标市值下单

把某个标的的持仓**调整到指定市值**（元）。这是聚宽最常用的下单函数之一，因为它天然带"再平衡"能力——函数会自动计算需要买入或卖出多少股。

```python
order_target_value('510300.XSHG', 100000)  # 把持仓调整到10万元市值
order_target_value('510300.XSHG', 0)       # 市值为0 → 清仓该标的
```

相关下单函数对照（后续策略会用到）：

| 函数 | 含义 |
|------|------|
| `order(security, amount)` | 按**股数**买入/卖出（amount 正买负卖） |
| `order_value(security, value)` | 按**金额**买入/卖出 |
| `order_target(security, amount)` | 调整到目标**股数** |
| `order_target_value(security, value)` | 调整到目标**市值** |
| `order_target_percent(security, pct)` | 调整到目标**仓位比例**（如 0.2 表示两成仓） |

## 四、回测说明

**回测参数（建议）：**
- 回测区间：2016-01-01 ～ 2026-01-01（约 10 年）
- 初始资金：100 万元
- 频率：日频（每天 14:50 判断一次）
- 基准：沪深300（000300.XSHG）
- 手续费/滑点：已在代码中设定

**需要重点关注的指标：**
- **年化收益率**：策略平均每年的收益水平
- **最大回撤**：从峰值到谷底的最大跌幅，衡量最坏情况（趋势策略在震荡市会反复被打脸，回撤较大）
- **夏普比率**：单位风险带来的超额收益，>1 较好
- **胜率**：盈利交易次数占比（趋势策略往往胜率不高但单笔盈利大）

**如实说明**：本策略需要在聚宽平台上运行才能得到真实回测数据（本仓库不预置回测数字，避免误导）。风险提示：历史回测不代表未来，均线策略在震荡行情下会频繁产生假信号、反复止损，请勿据此实盘。

## 五、改进方向（思考题）

1. 把均线换成 EMA（指数移动平均），对近期价格赋予更高权重，能否减少滞后？
2. 加入**过滤条件**：只有当长期均线向上时才允许做多，规避熊市；
3. 把单一标的换成多标的轮动（见策略 2），分散风险。
