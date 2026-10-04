# backtrader 详解 —— 本地量化回测的标准引擎

> 本文件是本仓库**本地回测**的语法底座。20 个 `strategies/backtrader/` 策略用到的每一个类、每一个函数，都能在这里查到签名、参数与用法。
> 环境版本：**backtrader 1.9.78.123** ｜ 安装：`pip install backtrader`

## 1. 库的定位与设计哲学

backtrader 是一个**纯 Python 的开源回测引擎**（MIT 协议，无账号、无云端、无收费）。它解决的是量化里最脏最累的那部分工作：

| 它替你做的事 | 你只需要做的事 |
|--------------|----------------|
| 按时间顺序推进行情（含多标的对齐、停牌处理） | 写"什么条件买、什么条件卖" |
| 撮合下单、算成交价与滑点 | 声明手续费规则 |
| 维护现金、持仓、保证金、盈亏 | 读 `self.position` / `self.broker` |
| 计算净值、回撤、交易统计 | 选一个分析器 |
| 指标递推计算（不用你手写移动窗口） | `bt.ind.SMA(...)` 一行 |

**核心设计哲学有三条，理解了就不会迷路：**

1. **一切皆 Line**。行情、指标、甚至策略自己的中间变量都是"按 K 线逐格推进的线"（Line），用统一的 `[0] / [-1]` 索引访问，所以 `close` 和 `SMA` 的用法完全一样。
2. **声明与执行分离**。指标在 `__init__` 里**声明一次**（只描述"怎么算"），引擎在每根 K 线上**自动递推**。这跟 pandas 一次性算整列不同——回测必须逐格推进，否则会用到未来数据。
3. **约定优于配置**。下单默认"下一根 K 线开盘价成交"，账户默认现货做多，滑点默认无。要改都通过 `params` 或 `broker` 显式改。

> 与聚宽的本质差别：聚宽是**云端平台**，你只写策略逻辑，撮合靠平台（代码只能在聚宽跑）；backtrader 是**库**，撮合和账务都在你本机跑（代码必须自己搭骨架）。两者策略思想完全相通，只是"谁提供引擎"不同。

## 2. 安装与依赖

```bash
pip install backtrader            # 引擎本体，无第三方依赖
pip install pandas matplotlib     # 喂数据与画图（本仓库需要）
```

```python
import backtrader as bt
print(bt.__version__)             # 1.9.78.123
```

> 注意：backtrader 已停止活跃开发（原作者转做其他项目），但**1.9.78.123 是稳定版**，功能完整、社区资料充足，做教学与中低频策略完全够用。不要用 `pip install backtrader2` 之类的非官方分叉。

## 3. 完整模块结构

| 模块 | 作用 | 本仓库用法 |
|------|------|------------|
| `bt.Cerebro` | 回测总控：装配数据/策略/分析器，然后 `run()` | `btlab/runner.py` |
| `bt.Strategy` | 策略基类，写买卖逻辑的地方 | 每个 `bt_*.py` |
| `bt.feeds` | 数据源。`PandasData` 把 DataFrame 变成行情 | `load_daily()` 的产物 |
| `bt.ind` | 60+ 技术指标 + 运算（SMA/EMA/RSI/MACD/ATR…） | 择时信号 |
| `bt.analyzers` | 事后统计：净值、回撤、交易明细、夏普 | `NavRecorder` / `Transactions` / `TradeAnalyzer` |
| `bt.observers` | 运行中观察：现金、市值、Trades | 绘图时用（本项目关掉） |
| `bt.sizers` | 仓位计算：下多少股 | 本项目手算整手，未启用 |
| `bt.CommInfoBase` | 手续费模型扩展点 | `AStockCommission` |
| `bt.Order` | 订单对象与状态机 | `notify_order()` |
| `bt.Broker` | 撮合与账务 | `cerebro.broker` |
| `bt.TimeFrame` | 周期常量（Days/Minutes…） | 重采样 |
| `bt.Writer` | 把运行过程写成 csv 等 | 调试用 |
| `bt.Signal` / `bt.SignalStrategy` | 用信号值驱动买卖的简化策略 | 本项目未用 |

## 4. 最小可运行模板（15 行）

先记住这个骨架，后面所有内容都是往里填。

```python
import backtrader as bt
import pandas as pd

df = pd.DataFrame({                      # 必须有 open/high/low/close/volume + DatetimeIndex
    'open': [...], 'high': [...], 'low': [...], 'close': [...], 'volume': [...]
}, index=pd.to_datetime([...]))

class MyStrategy(bt.Strategy):
    def __init__(self):                                  # 只跑一次：声明指标
        self.sma = bt.ind.SMA(self.data.close, period=20)

    def next(self):                                      # 每根 K 线跑一次：出信号下单
        if not self.position and self.data.close[0] > self.sma[0]:
            self.buy(size=100)
        elif self.position and self.data.close[0] < self.sma[0]:
            self.close()

cerebro = bt.Cerebro()
cerebro.adddata(bt.feeds.PandasData(dataname=df))
cerebro.addstrategy(MyStrategy)
cerebro.broker.setcash(1_000_000)
cerebro.run()
print('期末资产:', cerebro.broker.getvalue())
```

**执行顺序**：`adddata` 装行情 → `addstrategy` 装策略 → `run()` 开始逐根推进 → 每根 K 线调一次 `next()`。

## 5. 六个必须理解的核心概念

### 5.1 Line 与索引方向（最容易搞错的一条）

行情和指标都是 Line。索引 **正号朝未来、负号朝过去**：

| 写法 | 含义 | 能否在回测中用 |
|------|------|----------------|
| `self.data.close[0]` | **当根** K 线的收盘价 | ✅ 可以 |
| `self.data.close[-1]` | 上一根（**昨天**） | ✅ 可以 |
| `self.data.close[-2]` | 上上根（前天） | ✅ 可以 |
| `self.data.close[1]` | **下一根（明天）** | ❌ 未来数据 |
| `self.sma[0]` | 当根的均线值 | ✅ 可以 |

实测验证（6 根 K 线，收盘价 10.5→15.5）：

```
bar1: [0]=10.5  [-1]=15.5  [-2]=14.5  [1]=11.5
bar2: [0]=11.5  [-1]=10.5  [-2]=15.5  [1]=12.5
bar3: [0]=12.5  [-1]=11.5  [-2]=10.5  [1]=13.5
bar6: [0]=15.5  [-1]=14.5  [-2]=13.5  [1]=IndexError
```

两条**危险信号**：

1. 第一根 K 线上 `[-1]` 不会报错，而是**静默绕到数据集最后一行**（`bar1` 的 `[-1]` 返回 15.5 = 最后一根的收盘价）——因为内部是 `array[idx + ago]`，`idx=0` 时 `-1` 变成 Python 的"倒数第一个"。**这就是一次无声的未来函数泄漏。**
2. 最后一根 K 线上 `[1]` 会 `IndexError`（没有明天）。

**防护手段**：靠指标的 `minperiod` 自动挡（引擎在数据不足时调用 `prenext()` 而非 `next()`），或手动判断 `len(self) >= N`。**永远不要用正索引去"看后面"。**

取"最近 n 根"的两种写法：

```python
self.data.close.get(size=3)      # → [前天, 昨天, 今天]（list，最旧在最前）
list(self.data.close.get(size=3))[-1]   # 今天
# 注意：get() 是"取最近 n 个"，返回普通 list，list[-1] 是最后一个=最新
```

### 5.2 生命周期与回调顺序

引擎在一根 K 线上按固定顺序调用你：

```
Cerebro.run()
   │
   ├─ Strategy.__init__()              只调一次：声明指标/参数（禁止在这里做下单或读行情值）
   │
   ├─ 对每根 K 线循环：
   │    ├─ prenext()      数据还不够 minperiod 时调用（默认什么都不做 → 策略静默等待）
   │    ├─ nextstart()    数据刚够 minperiod 的那一根，调一次（默认转调 next）
   │    ├─ next()         正常逐根调用 ← 你的主逻辑
   │    └─ notify_order() / notify_trade() / notify_cashvalue() / notify_data()
   │                      事件回调：订单状态变化、成交、现金变化、数据状态
   │
   └─ stop()              回测结束调一次（收尾、打印统计）
```

**八股写法**：

```python
class S(bt.Strategy):
    def __init__(self):     self.sma = bt.ind.SMA(period=20)   # 建指标
    def prenext(self):      pass                                # 数据不足：默认啥也不做
    def next(self):         ...                                 # 主逻辑
    def notify_order(self, order): ...                          # 订单状态
    def notify_trade(self, trade): ...                          # 一笔交易开平仓
    def stop(self):         ...                                 # 收尾
```

> 关键：`__init__` 里**不能**访问 `close[0]` 这类"当前值"（此时还没有当前 K 线），只能拿 Line 对象去算指标。所有"读数值"的操作都放 `next()`。

### 5.3 DataFeed —— 把 DataFrame 喂进去

`bt.feeds.PandasData` 是最常用的数据源，会自动识别列名：

```python
data = bt.feeds.PandasData(
    dataname=df,                    # 必须：DatetimeIndex + open/high/low/close/volume 列
    datetime=None,                  # None = 用 DataFrame 的索引当时间
    open='open', high='high', low='low', close='close', volume='volume',
    openinterest=-1,                # -1 = 没有该列
)
cerebro.adddata(data, name='510300')     # name 给数据起名，便于多标的访问
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `dataname` | 必填 | DataFrame |
| `datetime` | `None` | `None`=用索引；也可给列名 |
| `open/high/low/close/volume/openinterest` | 自动 | 给列名，或 `-1` 表示无此列 |
| `timeframe` | `Days` | 周期，`bt.TimeFrame.Days/Minutes/...` |
| `compression` | 1 | 几根合成一根（如 5 分钟） |
| `sessionstart/sessionend` | None | 分钟级数据需要 |

其他数据源：`bt.feeds.GenericCSVData`（CSV 文件）、`YahooFinanceData`（联网）、`bt.feeds.PandasDirectData`（更快的 numpy 直供）。

### 5.4 Cerebro —— 总控

```python
cerebro = bt.Cerebro(
    preload=True,        # 预载数据（默认 True，快）
    runonce=True,        # 向量化模式（默认 True，最快）—— 语义与 runonce=False 一致
    stdstats=True,       # 是否加默认观察器（Broker/Trades/BuySell）
    maxcpus=None,        # 多核优化用
    optreturn=True,
    oldbuysell=False,
    oldtrades=False,
)
```

本仓库用 `bt.Cerebro(stdstats=False)`——关掉默认观察器，避免每次运行都弹图。

### 5.5 Broker —— 撮合与账务

```python
cerebro.broker.setcash(1_000_000)                 # 初始资金
cerebro.broker.getvalue()                          # 当前总资产（现金+持仓市值）
cerebro.broker.getcash()                           # 当前可用现金
cerebro.broker.getposition(data)                   # 持仓对象
cerebro.broker.setcommission(commission=0.0003)    # 简易佣金（按百分比）
cerebro.broker.set_slippage_perc(0.0002)           # 百分比滑点
```

| 下单/账户方法（`self.broker.xxx`） | 说明 |
|-----------------------------------|------|
| `getcash()` | 可用现金 |
| `getvalue()` | 总资产 |
| `getposition(data)` | 持仓，含 `.size`（股数，**负数=做空**）、`.price`（成本价） |
| `setcash(cash)` | 设初始资金 |
| `addcommissioninfo(info)` | 加自定义费用模型（见第 13 节） |
| `set_slippage_perc(perc, slip_open=True, slip_limit=True, slip_match=True, slip_out=False)` | 按百分比滑点 |
| `set_slippage_fixed(fixed, ...)` | 按固定价差滑点 |
| `set_coc(coc)` | Cheat-On-Close：是否允许当根收盘成交 |
| `set_checksubmit(bool)` | 是否校验保证金不足（默认 True） |
| `set_shortcash(bool)` | 做空时现金是增加还是减少 |
| `add_cash(amount)` | 中途出入金 |

### 5.6 成交时点：默认"下一根开盘"

这是 backtrader 最需要建立直觉的地方：

```
第 t 根 K 线的 next() 里调用 self.buy()
        ↓  订单被提交，但【不会】在第 t 根成交
第 t+1 根 K 线的【开盘价】成交
```

**为什么这样设计**：`next()` 是在第 t 根 K 线**收完之后**才被调用的，此时你能看到第 t 根的收盘价，但现实中收盘后你已经来不及按收盘价买了。所以默认把成交推迟到下一根开盘——**这是天然的防未来函数机制**，也是本仓库 20 个策略赖以成立的前提。

如果你确实想"当根收盘成交"（例如尾盘 14:50 下单），需要显式开 Cheat-On-Close：

```python
cerebro.broker.set_coc(True)      # 允许 self.buy() 按当根收盘价成交
```

> `set_coc(True)` 会**削弱**防未来函数保护，只在你能证明逻辑上确实收盘前就能决策时才用。本仓库**一律不用**。

## 6. Cerebro 完整 API

| 方法 | 签名/说明 |
|------|-----------|
| `adddata(data, name=None)` | 加一个数据源 |
| `addstrategy(strategy, *args, **kwargs)` | 加策略（kwargs 传给 `params`） |
| `addindicator(indcls, *args, **kwargs)` | 加一个独立指标（跑在策略级别，便于绘图） |
| `addanalyzer(ancls, *args, _name=..., **kwargs)` | 加分析器，`_name` 是取结果时的键 |
| `addobserver(obscls, *args, **kwargs)` | 加观察器 |
| `addsizer(sizercls, *args, **kwargs)` | 加仓位管理器 |
| `addsizer_byidx(idx, sizercls, *args, **kwargs)` | 给指定数据单独设 sizer |
| `addwriter(wrtcls, *args, **kwargs)` | 加 writer，把运行过程写文件 |
| `add_timer(when, offset=..., repeat=..., weekdays=[], monthdays=[], ...)` | 定时回调（`notify_timer`） |
| `add_signal(sigtype, sigcls, *args, **kwargs)` | 加信号（配合 `SignalStrategy`） |
| `addcalendar(cal)` | 换交易日历 |
| `setbroker(broker)` / `getbroker()` | 换/取 broker |
| `addtz(tz)` | 设时区 |
| `resampledata(dataname, name=None, **kwargs)` | 把数据重采样成更大周期（日→周） |
| `replaydata(dataname, name=None, **kwargs)` | 重放（把大周期拆成小周期逐步推进） |
| `rolloverdata(...)` | 期货换月 |
| `chaindata(...)` | 多数据源串接（拼历史） |
| `optstrategy(strategy, *args, **kwargs)` | 参数优化（配合 `run(maxcpus=...)`） |
| `run(**kwargs)` | 开始回测，返回策略实例列表。常用：`run(runonce=False)`、`run(maxcpus=4)` |
| `runstop()` | 在策略内部请求停止回测 |
| `plot(plotter=None, numfigs=1, iplot=True, start=None, end=None, width=16, height=9, dpi=300, tight=True, use=None, **kwargs)` | 画图（需 matplotlib） |

## 7. Strategy 完整 API

### 7.1 params —— 策略参数

```python
class S(bt.Strategy):
    params = (
        ('fast', 5),          # 名字, 默认值
        ('slow', 20),
        ('stake', 0.95),
    )

    def __init__(self):
        print(self.p.fast, self.p.slow)     # 用 self.p.xxx 读；self.params.xxx 也行
```

```python
cerebro.addstrategy(S, fast=10, slow=60)    # 运行时覆盖
```

- 参数元组也支持 `dict(fast=5, slow=20)` 形式。
- 参数可以参与指标声明：`bt.ind.SMA(period=self.p.slow)`。

### 7.2 生命周期方法一览

| 方法 | 调用时机 | 典型用途 |
|------|----------|----------|
| `__init__()` | 一次 | 声明指标、初始化计数器 |
| `start()` | 一次（比 `__init__` 晚，此时可读账户） | 打印初始资金 |
| `prenext()` | 数据不足 `minperiod` 时每根调用 | 默认空；可转调 `next()` 以"尽早开始" |
| `nextstart()` | 首次满足 `minperiod` 的那一根 | 默认转调 `next()` |
| `next()` | 每根正常 K 线 | **主逻辑** |
| `prenext_open()` / `nextstart_open()` / `next_open()` | 同上，但发生在**开盘前**（Cheat-On-Open 场景） | 按开盘价决策 |
| `once()` / `preonce()` / `oncestart()` | 向量化模式下的批量版本 | 一般不重写 |
| `notify_order(order)` | 订单状态变化 | 判断成交/拒单，重置挂单标记 |
| `notify_trade(trade)` | 一笔交易开仓/平仓 | 统计盈亏笔数 |
| `notify_cashvalue(cash, value)` | 现金/资产变化 | 记录净值（本项目改用 Analyzer） |
| `notify_data(data, status, dt)` | 数据源状态变化（如停牌、新数据） | 处理停牌 |
| `notify_timer(timer, when, *args)` | 定时器触发 | 定时调仓 |
| `notify_store(...)` | store 事件 | 实盘接入 |
| `stop()` | 回测结束一次 | 打印统计、保存结果 |

### 7.3 访问数据

```python
self.data                    # 第一个（或唯一）数据源；等价 self.datas[0]
self.datas                   # 所有数据源列表
self.getdatanames()          # ['510300', '000300', ...]（adddata 时给的 name）
self.getdatabyname('510300') # 按名字取数据源
self.data.close[0]           # 当前收盘价
self.data.close[-1]          # 昨收
self.data.close.get(size=5)  # 最近 5 根收盘价（list，最旧→最新）
len(self.data)               # 该数据源已有多少根 K 线（用于判断停牌/上市时间）
self.data.datetime.date(0)   # 当前日期（datetime.date 对象）
self.datetime.date(0)        # 同上（策略级的当前时间）
len(self)                    # 策略已推进多少根（= 主数据源的 bar 数）
```

> 多标的时，判断"今天这只票有没有行情"的方法：
> `len(d) > 0 and d.datetime.date(0) == cur_date`
> —— 停牌或未上市时它的时间会停在旧日期。本仓库 `PanelStrategy.live()` 就是这么写的。

### 7.4 下单方法全家桶

```python
self.buy(data=None, size=None, price=None, plimit=None, exectype=None,
         valid=None, tradeid=0, oco=None, trailamount=None, trailpercent=None,
         parent=None, transmit=True, **kwargs)
self.sell(data=None, size=None, price=None, plimit=None, exectype=None, ...)
self.close(data=None, size=None, **kwargs)
self.cancel(order)
self.order_target_size(data=None, target=0, **kwargs)
self.order_target_value(data=None, target=0.0, price=None, **kwargs)
self.order_target_percent(data=None, target=0.0, **kwargs)
self.buy_bracket(data=None, size=None, price=None, plimit=None, exectype=2,
                 stopprice=None, stopexec=3, limitprice=None, limitexec=2, ...)
```

| 方法 | 含义 | 备注 |
|------|------|------|
| `buy(size=n)` | 买 n 股 | `size` 省略则交给 sizer 算 |
| `sell(size=n)` | 卖 n 股 | 卖出超过持仓 → 变成**做空** |
| `close()` | 平掉该标的的持仓 | 最省心的离场方式，自动算方向与数量 |
| `cancel(order)` | 撤销挂单 | 常配合 `notify_order` |
| `order_target_size(target=n)` | 调仓到**目标股数** n | 自动买/卖差额 |
| `order_target_value(target=100000)` | 调仓到**目标市值**（元） | 与聚宽 `order_target_value` 同名同义 |
| `order_target_percent(target=0.2)` | 调仓到**目标仓位比例** | 与聚宽 `order_target_percent` 同名同义 |
| `buy_bracket(...)` | 一次下"主单+止损单+止盈单"三腿 | 止损止盈一体 |

**和聚宽下单函数的对照**：

| 聚宽 | backtrader | 是否同名 |
|------|-----------|----------|
| `order(security, amount)` | `self.buy/sell(data=..., size=amount)` | 否 |
| `order_value(security, value)` | 需自己按价换算股数 | 否 |
| `order_target(security, amount)` | `self.order_target_size(data=..., target=amount)` | 否 |
| `order_target_value(security, value)` | `self.order_target_value(data=..., target=value)` | ✅ 同名同义 |
| `order_target_percent(security, pct)` | `self.order_target_percent(data=..., target=pct)` | ✅ 同名同义 |

> ⚠️ **A 股必须自己取整手**。backtrader 不知道"1 手 = 100 股"，你传 137 股它就真买 137 股。本仓库统一用 `round_lot(size)` 向下取整到 100 的整数倍。
> ```python
> def round_lot(size, lot=100):
>     size = int(size)
>     return size - size % lot
> ```

### 7.5 持仓与账户

```python
self.position                       # 当前（第一个）标的的持仓
self.getposition(data)              # 指定标的持仓
self.getpositionbyname('510300')    # 按名字
self.positions                      # 全部持仓（list）
self.getpositions()                 # 全部持仓
self.positionsbyname                # dict
```

持仓对象 `Position` 的常用属性：

| 属性 | 含义 |
|------|------|
| `size` | 持有数量。**正数=多仓，负数=空仓，0=空仓无持仓** |
| `price` | 持仓成本均价 |
| `price_orig` | 未计算佣金前的成本价 |
| `adjbase` | 复权基准价 |
| `upopened` / `upclosed` | 是否在本根 K 线内开/平 |

```python
if not self.position:                 # 空仓（size == 0）
    ...
if self.position.size < 0:            # 持有空头
    ...
```

**做空**就是下"卖单超过持仓"，之后 `position.size` 变负数；平空用 `self.close()`。backtrader 原生支持，不需要额外配置。

### 7.6 订单通知（notify_order）

订单是一个**状态机**，必须靠回调追踪：

```python
def notify_order(self, order):
    if order.status in (order.Submitted, order.Accepted):
        return                                        # 中间态，忽略
    if order.status == order.Completed:
        if order.isbuy():
            print(f'买入成交 价={order.executed.price:.2f} 量={order.executed.size} '
                  f'手续费={order.executed.comm:.2f}')
        else:
            print(f'卖出成交 价={order.executed.price:.2f} 量={order.executed.size}')
    elif order.status in (order.Canceled, order.Margin, order.Rejected):
        print('订单未成交:', order.getstatusname())
    self.pending = None                               # 释放挂单标记
```

订单状态常量（`order.status`）：

| 常量 | 含义 |
|------|------|
| `order.Created` | 刚创建 |
| `order.Submitted` | 已提交给 broker |
| `order.Accepted` | broker 已受理 |
| `order.Partial` | 部分成交 |
| `order.Completed` | 完全成交 |
| `order.Canceled` / `order.Cancelled` | 已撤销 |
| `order.Margin` | **保证金/现金不足被拒** ← 最常见 |
| `order.Rejected` | 被拒 |
| `order.Expired` | 超时失效 |

订单常用属性/方法：

| 成员 | 含义 |
|------|------|
| `order.executed.price` | 成交均价 |
| `order.executed.size` | 成交量（买正卖负） |
| `order.executed.value` | 成交金额 |
| `order.executed.comm` | 手续费 |
| `order.isbuy()` / `order.issell()` | 方向 |
| `order.getstatusname()` | 状态的中文/英文名 |
| `order.ref` | 订单编号 |
| `order.alive()` | 是否仍是活单（未终态） |

> 订单类型常量在 `order.exectype`：`Market`(市价)、`Close`(收盘)、`Limit`(限价)、`Stop`(止损)、`StopLimit`、`StopTrail`、`StopTrailLimit`。默认是 `Market`。

**notify_trade** —— 一笔"交易"= 一次完整的开仓到平仓：

```python
def notify_trade(self, trade):
    if trade.isclosed:
        print(f'平仓 毛利={trade.pnl:.2f} 净利(扣费)={trade.pnlcomm:.2f}')
```

## 8. 指标 Indicator（bt.ind）

### 8.1 用法

指标在 `__init__` 里声明，**返回值就是一条 Line**，之后在 `next()` 里按索引读：

```python
def __init__(self):
    self.sma20 = bt.ind.SMA(self.data.close, period=20)
    self.rsi   = bt.ind.RSI(self.data.close, period=14)

def next(self):
    print(self.sma20[0], self.sma20[-1])     # 当前值 / 上一根值
```

不传数据时默认用 `self.data`：

```python
self.sma20 = bt.ind.SMA(period=20)           # 等价 SMA(self.data.close, period=20)（对单线数据）
```

### 8.2 常用指标与参数（实测默认值）

| 指标 | 写法 | 默认参数 | lines（可读的线） |
|------|------|----------|-------------------|
| 简单均线 | `bt.ind.SMA(period=30)` | `period=30`（**默认是 30，不是 20！**） | `sma` |
| 指数均线 | `bt.ind.EMA(period=30)` | `period=30` | `ema` |
| 加权均线 | `bt.ind.WMA(period=30)` | `period=30` | `wma` |
| 平滑均线 | `bt.ind.SMMA(period=30)` | `period=30` | `smma` |
| 双/三指数 | `bt.ind.DEMA/TEMA` | `period=30` | — |
| 相对强弱 | `bt.ind.RSI(period=14)` | `period=14, upperband=70, lowerband=30` | `rsi` |
| MACD | `bt.ind.MACD()` | `period_me1=12, period_me2=26, period_signal=9` | `.macd` `.signal` `.histo`（`MACDHisto`） |
| 布林带 | `bt.ind.BBands(period=20)` | `period=20, devfactor=2.0` | `.mid` `.top` `.bot` `.pctb` |
| 真实波幅 | `bt.ind.ATR(period=14)` | `period=14` | `atr` |
| 随机指标 | `bt.ind.Stochastic()` | `period=14, period_dfast=3, period_dslow=3` | `.percK` `.percD` |
| 交叉 | `bt.ind.CrossOver(a, b)` | — | `>0` 上穿，`<0` 下穿 |
| 上穿 | `bt.ind.CrossUp(a, b)` / `CrossDown` | — | 布尔 |
| 最高/最低 | `bt.ind.Highest(period=n)` / `Lowest` | `period=1` | 最近 n 根的最高/最低 |
| 涨跌幅 | `bt.ind.PctChange(period=30)` | `period=30` | 相对 n 根前的变化率（小数） |
| 标准差 | `bt.ind.StdDev(period=20)` | `period=20` | 滚动标准差 |
| 动量 | `bt.ind.Momentum(period=12)` | `period=12` | `close - close[-n]` |
| 变动率 | `bt.ind.ROC(period=12)` / `ROC100` | `period=12` | 百分比变化 |
| CCI | `bt.ind.CCI(period=20)` | `period=20, factor=0.015` | `cci` |
| 威廉指标 | `bt.ind.WilliamsR(period=14)` | `period=14, upperband=-20, lowerband=-80` | `willr` |
| 趋势强度 | `bt.ind.ADX(period=14)` | `period=14` | `adx` |
| 累积和 | `bt.ind.CumSum()` | `seed=0.0` | 累加 |
| 求和 | `bt.ind.Sum(n)` | — | 最近 n 根之和 |
| 百分位排名 | `bt.ind.PercentRank(period=50)` | `period=50` | 当前值在近 n 根中的分位 |
| 线性回归 | `bt.ind.OLS_Slope_InterceptN(period=10)` | `period=10` | `.slope` `.intercept`（滚动 OLS） |
| 抛物线 SAR | `bt.ind.ParabolicSAR` / `PSAR` | — | `psar` |
| 一目均衡 | `bt.ind.Ichimoku` | — | 多条线 |
| 量价 | `bt.ind.PPO` / `bt.ind.PGO` / `bt.ind.Vortex` | — | 各类振荡 |

> `bt.ind` 里同时存在**短名和全称别名**（`SMA` = `MovingAverageSimple` = `SimpleMovingAverage`），任选，推荐短名。

### 8.3 指标运算（LineActions）

Line 之间可以直接做算术和比较，引擎会逐格算：

```python
self.spread = self.ma_fast - self.ma_slow          # 两线相减
self.ratio  = self.data.close / self.sma20          # 相除
self.up     = self.data.close > self.sma20          # 布尔线
self.mom    = bt.ind.PctChange(self.data.close, period=20)
self.rank   = bt.ind.PercentRank(self.data.close, period=250)
```

### 8.4 minperiod —— 自动挡未来函数

引擎会自动算出所有指标的"最小需要根数"（如 SMA(20) 需要 20 根）。在满足之前，引擎调用 `prenext()` 而不是 `next()`，于是你的主逻辑自然就不会在数据不足时执行。

```python
def __init__(self):
    self.sma60 = bt.ind.SMA(period=60)     # minperiod 自动变成 60

def prenext(self):
    pass                                   # 前 59 根什么都不做（默认行为）
```

**这也是 `[-1]` 绕圈陷阱的天然防线**：因为 `next()` 最早在第 60 根才被调用，`[-1]` 一定指向真实的历史数据。

如果要让策略"从第 1 根就开始运行"（自己判断数据够不够）：

```python
def prenext(self):
    self.next()                            # 让 prenext 转调 next
```

### 8.5 自定义指标

```python
class MyRange(bt.Indicator):
    lines = ('rng',)                                        # 声明输出线
    params = (('period', 10),)                              # 参数
    plotinfo = dict(subplot=True)                           # 绘图时独立子图

    def __init__(self):
        hh = bt.ind.Highest(self.data.high, period=self.p.period)
        ll = bt.ind.Lowest(self.data.low, period=self.p.period)
        self.lines.rng = hh - ll                            # 给输出线赋值
```

## 9. Analyzer —— 事后统计

```python
cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
cerebro.addanalyzer(bt.analyzers.DrawDown,      _name='dd')
strat = cerebro.run()[0]
res = strat.analyzers.trades.get_analysis()      # 用 _name 取
```

| 分析器 | 产出 |
|--------|------|
| `bt.analyzers.TradeAnalyzer` | 交易统计：总笔数、胜率、盈亏比、最大连续盈亏 |
| `bt.analyzers.DrawDown` | 最大回撤、回撤区间、当前回撤 |
| `bt.analyzers.TimeReturn` | 按周期（月/年）的收益率序列 |
| `bt.analyzers.SharpeRatio` | 夏普比率（可设 `timeframe`、`riskfreerate`） |
| `bt.analyzers.SharpeRatio_A` | 年化夏普 |
| `bt.analyzers.AnnualReturn` | 每年收益率 |
| `bt.analyzers.Calmar` / `SQN` / `VWR` | Calmar / 系统质量分 / 变动率加权收益 |
| `bt.analyzers.Transactions` | **逐笔成交明细**（本项目用它统计笔数与换手） |
| `bt.analyzers.PositionsValue` | 每日各持仓市值 |
| `bt.analyzers.GrossLeverage` | 杠杆率 |
| `bt.analyzers.PyFolio` | 生成 pyfolio 需要的全套时间序列 |

**自定义 Analyzer**（本项目用它记录每日净值）：

```python
class NavRecorder(bt.Analyzer):
    def start(self):                                 # 回测开始
        self._d, self._v = [], []
    def _rec(self):
        self._d.append(self.strategy.datetime.date(0))
        self._v.append(self.strategy.broker.getvalue())
    def prenext(self):  self._rec()                  # 数据不足时也要记录
    def nextstart(self): self._rec()
    def next(self):     self._rec()
    def get_analysis(self):                          # 回测结束后取结果
        return pd.Series(self._v, index=pd.to_datetime(self._d), name='nav')
```

| Analyzer 生命周期方法 | 时机 |
|-----------------------|------|
| `start()` | 回测开始一次 |
| `prenext()` / `nextstart()` / `next()` | 同 Strategy |
| `stop()` | 结束一次 |
| `get_analysis()` | 取结果（在 `cerebro.run()` 之后调用） |

## 10. Observer 与绘图

Observer 是"运行中同步观察"的组件（默认有 Broker / Trades / BuySell）：

```python
cerebro = bt.Cerebro(stdstats=False)          # 关掉默认观察器
cerebro.addobserver(bt.observers.Broker)      # 想开哪个单独开
```

绘图：

```python
cerebro.plot(style='candlestick', iplot=False)   # 需要 matplotlib
```

> 本仓库**不用** `cerebro.plot()`——它要求交互式后端，批量跑 20 个策略时会卡住。我们用 `btlab.metrics.plot_equity()` 直接由净值序列画图（`matplotlib.use('Agg')` 无界面保存 PNG）。

## 11. Sizer —— 仓位管理

```python
cerebro.addsizer(bt.sizers.FixedSize, stake=100)      # 固定 100 股
cerebro.addsizer(bt.sizers.PercentSizer, percents=95) # 用 95% 可用资金
```

| Sizer | 说明 |
|-------|------|
| `FixedSize(stake=)` | 每次固定股数 |
| `FixedSizeTarget` | 目标固定股数 |
| `FixedReverser` | 反手（多空互换） |
| `PercentSizer(percents=)` | 按可用现金百分比 |
| `PercentSizerInt` | 同上但取整 |
| `AllInSizer` / `AllInSizerInt` | 全仓 |

sizer 只在 `size=None` 时生效：

```python
self.buy()            # 用 sizer 算
self.buy(size=100)    # 忽略 sizer
```

> 本仓库手算整手股数，**未启用 sizer**——因为 A 股的"整手 + 目标权重"约束用 sizer 表达反而更绕。

## 12. Cheat-On-Open / Cheat-On-Close

| 开关 | 效果 | 风险 |
|------|------|------|
| 默认 | `next()` 决策 → **下一根开盘**成交 | 无（推荐） |
| `cerebro.broker.set_coc(True)` | 决策 → **当根收盘**成交 | 需要证明"收盘前已能决策"，否则是未来函数 |
| `cerebro.broker.set_coo(True)` | 决策 → **当根开盘**成交 | 需要证明"开盘前已能决策" |

```python
cerebro.broker.set_coc(True)     # 允许当根收盘成交
cerebro.broker.set_coo(True)     # 允许当根开盘成交
```

对应地，策略可以重写 `next_open()`（开盘前回调）：

```python
def next_open(self):
    ...    # 此时只知今天的开盘价，决策后默认在今天开盘成交（需 set_coo）
```

> 本仓库全部策略用**默认模式**（收盘决策、次日开盘成交），并在文件头注明。这是"隔夜决策"的真实约束，自动免疫未来函数。

## 13. 交易成本与滑点（A 股实战）

### 13.1 简易方式

```python
cerebro.broker.setcommission(commission=0.0003)             # 双边 0.03%
cerebro.broker.set_slippage_perc(0.0002)                     # 单边 0.02%
```

`setcommission` 的参数：

| 参数 | 默认 | 说明 |
|------|------|------|
| `commission` | 0.0 | 费率；`percabs=True` 时 0.0003 = 0.03% |
| `margin` | None | 期货保证金 |
| `mult` | 1.0 | 合约乘数 |
| `commtype` | None | `COMM_PERC`（按比例）/`COMM_FIXED`（按手数） |
| `stocklike` | False | True=股票/ETF（无保证金概念） |
| `percabs` | True | True=绝对值（0.001 即 0.1%）；False=需再除 100 |
| `leverage` | 1.0 | 杠杆 |
| `interest` | 0.0 | 融资利率 |

### 13.2 精确方式：自定义 CommInfoBase

A 股的真实规则是"佣金双边 + 印花税仅卖出 + 单笔最低 5 元"，`setcommission` 表达不了，必须扩展 `bt.CommInfoBase`：

```python
class AStockCommission(bt.CommInfoBase):
    params = (
        ('stocklike', True),
        ('commtype', bt.CommInfoBase.COMM_PERC),
        ('percabs', True),        # 0.0003 即 0.03%
        ('commission', 0.0003),   # 佣金（买卖双边）
        ('stamp_duty', 0.0005),   # 印花税，仅卖出（2023-08-28 起减半为 0.05%）
        ('min_comm', 5.0),        # 单笔最低佣金 5 元
    )

    def _getcommission(self, size, price, pseudoexec):
        value = abs(size) * price
        if value <= 0:
            return 0.0
        comm = value * self.p.commission
        if size < 0:                                  # size<0 即卖出方向
            comm += value * self.p.stamp_duty
        return comm if comm > self.p.min_comm else self.p.min_comm

cerebro.broker.addcommissioninfo(AStockCommission())
```

| 扩展点 | 说明 |
|--------|------|
| `_getcommission(size, price, pseudoexec)` | **必须实现**：返回这笔（伪）成交的手续费。`pseudoexec=True` 表示"试算"，用于校验现金够不够 |
| `get_margin(price)` | 期货保证金，股票不用 |
| `confirmexec(...)` | 高级：自定义成交确认逻辑 |

> **为什么必须自己算**：忽略印花税与最低佣金，一个高换手策略的回测收益会虚高好几个百分点；反过来，`min_comm=5` 对小额交易的影响极大（买 1000 元股票，5 元佣金 = 0.5%）。本仓库 20 个策略统一用这套口径。

### 13.3 滑点

```python
cerebro.broker.set_slippage_perc(
    perc=0.0002,        # 单边 0.02%
    slip_open=True,     # 开盘价单也滑
    slip_limit=True,    # 限价单也滑
    slip_match=True,    # 滑点后若超出行情范围，则裁剪到最高/最低价
    slip_out=False,     # True=允许滑到当日价格区间之外
)
```

买入时成交价 = `price * (1 + perc)`，卖出时 = `price * (1 - perc)`。

## 14. 多数据源与交易日历

```python
cerebro.adddata(bt.feeds.PandasData(dataname=df_a), name='510300')
cerebro.adddata(bt.feeds.PandasData(dataname=df_b), name='510500')
cerebro.adddata(bt.feeds.PandasData(dataname=df_cal), name='__CAL__')

def next(self):
    d = self.getdatabyname('510500')
    self.buy(d, size=100)
```

**多标的的坑**：backtrader 以**主数据源**（第一个 adddata 的）的 K 线数为节拍。如果主数据源停牌，或者各标的上市时间不同，`next()` 的推进就会错位。

**本仓库的解法（PanelStrategy）**：额外喂一个"每个交易日都有行情"的基准指数，命名为 `__CAL__`，专门当**时钟**：

```python
self.cal = self.getdatabyname('__CAL__')          # 日历源
cur = self.cal.datetime.date(0)                   # 当前交易日
self.tradables = [d for d in self.datas if d._name != '__CAL__']   # 真正的交易标的

def live(self, d, cur):                           # 这只票今天有行情吗？
    return len(d) > 0 and d.datetime.date(0) == cur
```

## 15. 参数优化

```python
cerebro.optstrategy(S, fast=range(5, 21, 5), slow=range(20, 61, 10))
results = cerebro.run(maxcpus=4)          # 返回 list[list[Strategy]]
for r in results:
    strat = r[0]
    print(strat.p.fast, strat.p.slow, strat.analyzers.nav.get_analysis().iloc[-1])
```

- `optstrategy` 会把参数的**笛卡尔积**全部跑一遍。
- `maxcpus=1` 单进程（好调试），`>1` 多进程（快，但数据要能 pickle）。
- `Cerebro(optreturn=True)`（默认）返回的是轻量结果对象，需要完整策略对象时设 `optreturn=False`。

> 注意**参数过拟合**：在长历史上选出"最优参数"往往只是拟合了噪声。本仓库的策略都留了参数块，但教学时不鼓励暴力搜参。

## 16. 聚宽 API ↔ backtrader API 对照表

| 概念 | 聚宽（JoinQuant） | backtrader |
|------|-------------------|------------|
| 策略入口 | `def initialize(context)` | `class S(bt.Strategy)` + `__init__()` |
| 每根 K 线 | `def handle_data(context, data)` 或 `run_daily(func)` | `def next(self)` |
| 定时器 | `run_daily/run_weekly/run_monthly` | `next()` 里自己判断是否换月/换周 |
| 全局参数 | `g.xxx = ...` | `params = ((...),)` → `self.p.xxx` |
| 基准 | `set_benchmark('000300.XSHG')` | 自己加载指数并对比（`btlab` 的 `benchmark` 参数） |
| 真实价格 | `set_option('use_real_price', True)` | 数据层直接给复权价（`btlab.datasource` 处理） |
| 手续费 | `set_order_cost(OrderCost(...), type='stock')` | `addcommissioninfo(AStockCommission())` |
| 滑点 | `set_slippage(FixedSlippage(0.02))` | `set_slippage_perc(0.0002)` |
| 取历史行情 | `attribute_history(sec, N, '1d', 'close')` | `self.data.close.get(size=N)` |
| 成分股 | `get_index_stocks('000300.XSHG')` | `btlab.datasource.load_index_members()` |
| 财务数据 | `get_fundamentals(query(...))` | `btlab.runner.value_panel()/roe_panel()` |
| 按股数下单 | `order(sec, amount)` | `self.buy/sell(size=amount)` |
| 目标市值 | `order_target_value(sec, v)` | `self.order_target_value(target=v)` |
| 目标比例 | `order_target_percent(sec, p)` | `self.order_target_percent(target=p)` |
| 清仓 | `order_target_value(sec, 0)` | `self.close()` |
| 持仓 | `context.portfolio.positions[sec]` | `self.getposition(data)` |
| 可用现金 | `context.portfolio.available_cash` | `self.broker.getcash()` |
| 总资产 | `context.portfolio.total_value` | `self.broker.getvalue()` |
| 日志 | `log.info(...)` | `print(...)`（或 `bt.Writer`） |
| 回测区间 | 平台界面设置 | `load_daily(start=..., end=...)` 切数据 |
| 初始资金 | 平台界面设置 | `cerebro.broker.setcash(...)` |
| 运行方式 | 云端点"编译运行" | 本机 `python script.py` |

> 一句话总结：**思路能平移，"触发方式"和"下单口径"必须重写**。聚宽的 `run_monthly` 在 backtrader 里要自己写成"日期月份变化才调仓"，聚宽的 `order_target_value` 在 backtrader 里要注意整手取整。

## 17. 本仓库 btlab 工具层 API

`btlab` **不是自研回测框架**（撮合与账务 100% 由 backtrader 负责），只是把 20 个策略共用的样板代码收拢成 3 个模块。

### 17.1 `btlab.datasource` —— 免费长周期数据

| 函数 | 作用 |
|------|------|
| `load_daily(code, start='2010-01-01', end=None, adjust='qfq', kind=None)` | 取单个标的日线（自动识别 股票/ETF/指数） |
| `load_many(codes, start, end, adjust, kind, verbose)` | 批量取，返回 `{code: DF}` |
| `load_index_members(index_code='000300')` | 指数成分股（**当前**成分，注意幸存者偏差） |
| `load_stock_value(code)` | 估值面板：`close/total_mv/circ_mv/pe/pe_ttm/pb/ps` |
| `roe_series(code, start_year='2015')` | ROE 时间序列（报告期口径） |
| `load_financial_indicator(code, start_year)` | 财务指标表 |
| `sw_industries()` | 申万一级行业列表 |
| `load_sw_index(code, start, end)` | 申万行业指数行情（1999 年起） |
| `load_sw_members(code)` | 行业成分股 |
| `load_index_pe(symbol='沪深300')` | 指数市盈率（2005 年起，用于因子择时） |
| `load_bond_universe(top=None)` / `listed_bonds(before, top, min_size)` | 可转债列表 |
| `load_bond_daily(code, start, end)` | 可转债日线 |
| `classify(code)` / `normalize_code(code, kind=None)` / `is_index()` / `is_etf()` | 代码规范化（解决 `000001` 股票 vs `sh000001` 指数歧义） |
| `cache_dir()` / `clear_cache(prefix=None)` | 缓存管理（`data_cache/`） |

### 17.2 `btlab.runner` —— 回测样板

| 函数/类 | 作用 |
|---------|------|
| `build_cerebro(cash, commission, stamp_duty, min_comm, slippage)` | 建好带 A 股费用/滑点的 Cerebro |
| `run_strategy(strategy_cls, data, cash, benchmark, ..., plot_path=)` | **一键回测**：跑策略 → 打印报告 → 存净值图 |
| `AStockCommission` | A 股手续费模型（第 13.2 节） |
| `NavRecorder` | 逐日记录净值的 Analyzer |
| `PanelStrategy` | 多标的调仓骨架：`on_rebalance(cur)` + `equal_weight_order()` / `value_weight_order()` / `close_all()` / `live()` / `hist_close()` |
| `add_feed(cerebro, df, name)` / `add_feeds(cerebro, data)` | 加数据源 |
| `load_universe(codes, start, ...)` | 加载候选池并剔除"上市太晚"的标的 |
| `round_lot(size, lot=100)` | 股数取整手 |
| `asof(panel, cur)` | **防未来函数**：只取不晚于 `cur` 的最近一行面板数据 |
| `value_panel(codes, field)` / `roe_panel(codes, lag_days=45)` / `growth_panel(...)` | 估值/ROE/成长因子面板 |
| `event_calendar(codes, field, lag_days, threshold)` | 业绩事件日历 |
| `industry_map(codes)` | 股票 → 申万一级行业映射（行业中性化用） |
| `prepare_benchmark(code, start, end)` | 加载基准指数 |

### 17.3 `btlab.metrics` —— 绩效与绘图

| 函数 | 作用 |
|------|------|
| `perf_from_nav(nav, initial_cash=None)` | 由净值序列算：累计/年化收益、最大回撤、夏普、年化波动、日胜率 |
| `format_report(metrics, ...)` | 格式化成中文报告字符串 |
| `plot_equity(nav, benchmark_nav, save_path, title)` | 画"净值 + 回撤"双子图并存 PNG |

## 18. 常见错误与坑（12 条）

| # | 现象 | 原因 | 解法 |
|---|------|------|------|
| 1 | `next()` 里报 `close[-1]` 值很奇怪 | 首根 K 线上负索引**绕到数组末尾** | 靠 `minperiod` 或 `len(self) > N` 判断 |
| 2 | 用了 `close[1]` | 正索引 = 未来数据 | 只用 `[0]` 和负索引 |
| 3 | `__init__` 里读 `close[0]` 报错 | 此时还没有"当前值" | 数值操作全放 `next()` |
| 4 | 订单一直不成交 | `notify_order` 显示 `Margin`（现金不足） | 留缓冲（如用 95% 仓位）、`round_lot` 取整手 |
| 5 | 买了 137 股这种零头 | backtrader 不懂 A 股整手 | `round_lot(size)` |
| 6 | 多标的时 `next()` 触发次数不对 | 以主数据源为节拍，停牌/上市错位 | 用 `__CAL__` 日历源当节拍 |
| 7 | 回测收益离谱地高 | 未加手续费/滑点，或用了未来数据 | 配 `AStockCommission` + `set_slippage_perc` |
| 8 | `cerebro.plot()` 卡死 | 需要交互式图形后端 | 批量跑时用 `Agg` 后端自己存图 |
| 9 | 指标一开始就是 NaN | `minperiod` 未满足 | 正常现象；用 `prenext()` 处理等待期 |
| 10 | 参数优化后跑不动 | 多进程要求数据可 pickle | `maxcpus=1` 或减少数据体积 |
| 11 | `SMA()` 不写参数得到 30 日均线 | **默认 `period=30`**，不是 20 | 永远显式写 `period=` |
| 12 | 现金为负 | 未校验提交，或做空现金口径 | `set_checksubmit(True)`、注意 `set_shortcash` |

## 19. 完整可运行模板（防未来函数版）

```python
# -*- coding: utf-8 -*-
import os
import backtrader as bt

from btlab.datasource import load_daily
from btlab.runner import run_strategy, round_lot

START, END, CASH, SYMBOL, BENCHMARK = '2015-01-01', None, 1_000_000, '510300', '000300'


class Demo(bt.Strategy):
    """双均线：金叉买入，死叉清仓。日线收盘出信号 → 次日开盘成交。"""
    params = (('fast', 5), ('slow', 20), ('stake', 0.95))

    def __init__(self):
        # 指标只在这里声明一次；minperiod 由 SMA(slow) 自动决定
        self.ma_fast = bt.ind.SMA(self.data.close, period=self.p.fast)
        self.ma_slow = bt.ind.SMA(self.data.close, period=self.p.slow)
        self.cross = bt.ind.CrossOver(self.ma_fast, self.ma_slow)

    def next(self):
        if not self.position:                      # 空仓
            if self.cross[0] > 0:                  # 金叉
                size = round_lot(self.broker.getcash() * self.p.stake
                                 / self.data.close[0])   # 留 5% 缓冲
                if size > 0:
                    self.buy(size=size)
        elif self.cross[0] < 0:                    # 持仓 + 死叉
            self.close()

    def notify_order(self, order):
        if order.status in (order.Submitted, order.Accepted):
            return
        if order.status == order.Completed:
            side = '买入' if order.isbuy() else '卖出'
            print(f'{self.datetime.date(0)} {side} 价={order.executed.price:.3f} '
                  f'量={order.executed.size} 费={order.executed.comm:.2f}')
        elif order.status in (order.Canceled, order.Margin, order.Rejected):
            print(f'{self.datetime.date(0)} 未成交: {order.getstatusname()}')


if __name__ == '__main__':
    df = load_daily(SYMBOL, start=START, end=END)
    print(f'区间 {df.index[0].date()} ~ {df.index[-1].date()}，{len(df)} 个交易日')
    run_strategy(
        Demo, {SYMBOL: df}, cash=CASH, benchmark=BENCHMARK,
        title='backtrader 模板 Demo（沪深300ETF）',
        plot_path=os.path.join('results', 'demo_result.png'),
    )
```

运行：`python 本文件.py`。首次会联网拉数据到 `data_cache/`，之后秒开；净值图存到 `results/demo_result.png`。

## 20. 学习路径建议

```
第一步  读第 4 节模板，把它跑通 → 建立"声明指标 / next 下单"的肌肉记忆
   │
第二步  读第 5 节六个概念，重点吃透 5.1 索引方向 与 5.6 成交时点
   │
第三步  对照本文件第 16 节的对照表，把聚宽策略"翻译"一遍
   │
第四步  读 strategies/backtrader/beginner/bt_s01 ~ bt_s10，配合 docs/backtrader/beginner/
   │
第五步  进阶策略（docs/backtrader/advanced/）涉及做空、事件、多资产、ML
```

> 配套文档：
> - 策略逐篇详解 → `docs/backtrader/beginner/`、`docs/backtrader/advanced/`
> - 聚宽版对照 → `docs/joinquant/beginner/`、`docs/joinquant/advanced/`
> - 环境与运行 → `docs/本地回测使用指南.md`
> - 聚宽函数全解 → `docs/learning/3.聚宽函数详解/get_functions.md`
