# backtrader 详解（教程版）—— 从「读得懂」到「会改」

> 本文件是 Quant_Lab **本地回测**的语法底座：`strategies/backtrader/` 里 20 个策略用到的每一个类、函数、参数，都在这里有解释和例子。
>
> **读法**：不需要你在电脑上敲代码。每段代码后面都会有「这段在干什么 / 逐行在做什么 / 运行后你会看到什么」。
>
> **环境**：backtrader **1.9.78.123**（`pip install backtrader`）。
> 文中标了「**实测**」的结论，都是在这个版本上真跑出来的；没有实测的推断，会写成「据源码」。

## 目录

- [第 0 章 先建立心智模型（完全不用看代码）](#第-0-章-先建立心智模型完全不用看代码)
- [第 1 章 最小骨架：15 行逐行讲](#第-1-章-最小骨架15-行逐行讲)
- [第 2 章 Line：backtrader 的世界观](#第-2-章-linebacktrader-的世界观)
- [第 3 章 生命周期：一根 K 线上到底发生了什么](#第-3-章-生命周期一根-k-线上到底发生了什么)
- [第 4 章 DataFeed：把数据喂进去](#第-4-章-datafeed把数据喂进去)
- [第 5 章 Strategy：策略里的每个函数](#第-5-章-strategy策略里的每个函数)
- [第 6 章 Indicator：指标](#第-6-章-indicator指标)
- [第 7 章 Analyzer：事后统计](#第-7-章-analyzer事后统计)
- [第 8 章 Observer / Sizer / Writer](#第-8-章-observer--sizer--writer)
- [第 9 章 Broker：撮合、费用、滑点、成交时点](#第-9-章-broker撮合费用滑点成交时点)
- [第 10 章 多标的与组合调仓](#第-10-章-多标的与组合调仓)
- [第 11 章 Cerebro：总控](#第-11-章-cerebro总控)
- [第 12 章 参数优化](#第-12-章-参数优化)
- [第 13 章 聚宽 API ↔ backtrader 对照](#第-13-章-聚宽-api--backtrader-对照)
- [第 14 章 本仓库 btlab 工具层](#第-14-章-本仓库-btlab-工具层)
- [第 15 章 最常见的坑（含实测证据）](#第-15-章-最常见的坑含实测证据)
- [第 16 章 完整可运行模板 + 输出解读](#第-16-章-完整可运行模板--输出解读)
- [第 17 章 自测题（不写代码也能做）](#第-17-章-自测题不写代码也能做)
- [第 18 章 学习路径](#第-18-章-学习路径)

---

## 第 0 章 先建立心智模型（完全不用看代码）

### 0.1 回测引擎到底在替你做什么

回测的本质是：**拿历史数据，按时间顺序「假装」交易一遍，看最后钱变成了多少，以及这个过程中最惨的时候亏了多少。**

「假装交易」听起来简单，但真要动手，你会发现有一堆必须处理的琐事：

| 你必须自己操心的事（如果手写回测） | backtrader 替你做了 |
|---|---|
| 按日期把多个标的的数据对齐，某只票停牌怎么办 | 行情推进与多数据源对齐 |
| 下单后按什么价成交？开盘价还是收盘价？ | 撮合引擎 + 成交价规则 |
| 现金够不够？买了之后还剩多少？ | 账务、现金、持仓、盈亏 |
| 手续费、印花税、滑点怎么扣 | CommInfo 费用模型（可自定义） |
| 每天的总资产是多少、最大回撤多少 | Analyzer 分析器 |
| 均线要一个个算窗口，还容易算错 | 60+ 内置指标，声明即用 |

所以你写策略时，**只需要回答一个问题**：*今天我要买什么、卖什么、买多少。* 其余的交给引擎。

### 0.2 为什么必须「逐根 K 线」，而不是像 pandas 那样一次算完

用 pandas 算均线，一行就够了：

```python
df['ma20'] = df['close'].rolling(20).mean()      # 一次算出全部 3000 行
```

这在**研究**阶段很方便，但**不能直接拿来回测**。原因：当你站在第 100 根 K 线上做决策时，现实世界里第 101~3000 根的价格**还不存在**。如果代码里不小心用到了整列数据（比如 `df['close'].max()` 拿的是全期最高价），回测就会"偷看未来"，收益虚高。

backtrader 的做法是**把时间切成一根一根 K 线**，每一根只把"到今天为止"的数据交给你：

```
第 1 根  → 你只能看到第 1 根
第 2 根  → 你只能看到第 1~2 根
...
第 100 根 → 你只能看到第 1~100 根
```

这从结构上就不给你偷看未来的机会——**这是 backtrader 最核心的价值**。

### 0.3 一张图看懂 backtrader 的「一天」

假设我们用沪深300ETF做"MA5 上穿 MA20 就买"的策略。某一天 backtrader 内部发生的顺序是这样的（数字是编的，重点看**顺序**）：

| 步骤 | 引擎做什么 | 你的代码在做什么 | 此时你"知道"什么 |
|---|---|---|---|
| ① | 把第 t 根 K 线喂进数据源 | —— | close=4.00，MA5=3.95，MA20=3.90 |
| ② | 先处理**上一根**挂着的订单 | —— | 上一根的单子按**今天开盘** 3.98 成交了 |
| ③ | 计算所有指标（SMA/RSI/…）到第 t 根 | —— | 指标已更新 |
| ④ | 调用 `next()` | 你写：判断 MA5>MA20 → `self.buy()` | 只能看到第 t 根及之前 |
| ⑤ | 记录净值 | —— | 今天的总资产 |
| ⑥ | 第 t+1 根的数据到来 | —— | 你昨天下的单，在**今天开盘**成交 |

**请特别记住第 ②/⑥ 步**：你在 `next()` 里下的单，**不会**在本根 K 线成交，而是排到下一根 K 线的开盘价成交。原因见 0.4。

### 0.4 由此推出的三条「必然」——理解了就不会迷路

**(1) 指标为什么必须写在 `__init__` 里？**
`__init__` 只在回测开始时执行**一次**，你的工作是"声明我要算 MA5 和 MA20"；之后引擎每推进一根 K 线，就自动把这两条线往前算一格。你**不能**在 `__init__` 里读 `close[0]`（那时还没有任何 K 线），所有读数值的操作都要放到 `next()`。

**(2) 为什么下单默认在"下一根开盘"成交？**
因为 `next()` 是在第 t 根 K 线**收盘之后**才被调用的。此时你确实看到了 t 的收盘价，但现实中"收盘了你已经买不到了"。把成交推迟到 t+1 的开盘，才是真实世界能做到的。**这条默认规则，等于免费送了你一层防未来函数保护。**

**(3) 为什么需要 `minperiod`？**
MA20 需要 20 根 K 线才有值。引擎会自动算出"所有指标里需要的最多根数"（这里=20），在前 19 根**不调用** `next()`，而是调用 `prenext()`。这样你就不会在均线还是空值的时候下单。这个机制叫 `minperiod`（最小周期），详见第 3.4 节。

---

## 第 1 章 最小骨架：15 行逐行讲

### 1.1 完整代码

```python
import backtrader as bt
import pandas as pd

df = pd.DataFrame({                       # ① 行情数据：必须有 OHLCV + 日期索引
    'open': [...], 'high': [...], 'low': [...], 'close': [...], 'volume': [...]
}, index=pd.to_datetime([...]))

class MyStrategy(bt.Strategy):            # ② 策略 = 继承 bt.Strategy 的类
    def __init__(self):                   # ③ 只跑一次：声明指标
        self.sma20 = bt.ind.SMA(self.data.close, period=20)

    def next(self):                       # ④ 每根 K 线跑一次：出信号、下单
        if not self.position and self.data.close[0] > self.sma20[0]:
            self.buy(size=100)            # ⑤ 买入 100 股（下一根开盘成交）
        elif self.position and self.data.close[0] < self.sma20[0]:
            self.close()                  # ⑥ 清仓

cerebro = bt.Cerebro()                    # ⑦ 总控
cerebro.adddata(bt.feeds.PandasData(dataname=df))   # ⑧ 喂数据
cerebro.addstrategy(MyStrategy)           # ⑨ 挂策略
cerebro.broker.setcash(1_000_000)         # ⑩ 初始资金
cerebro.run()                             # ⑪ 开始回测
print(cerebro.broker.getvalue())          # ⑫ 看期末总资产
```

### 1.2 逐行讲解

| 编号 | 这一行在做什么 | 不写会怎样 / 常见坑 |
|---|---|---|
| ① | 准备行情：**必须**有 `open/high/low/close/volume` 五列，索引是日期 | 少一列 → 报错；索引不是 datetime → `PandasData` 解析失败 |
| ② | 定义一个策略类，继承 `bt.Strategy` | 必须继承，否则 `addstrategy()` 会拒绝 |
| ③ | `__init__` 声明指标。**只声明、不读值** | 在这里读 `close[0]` → 报错（此时还没有 K 线） |
| ④ | `next()` 每根 K 线调用一次，写买卖逻辑 | 逻辑写在这里；写在 `__init__` 里不会重复执行 |
| ⑤ | `self.buy(size=100)` 下买单 | 不写 `size` 且没配 sizer → 报错或按默认 sizer 走 |
| ⑥ | `self.close()` 平掉当前持仓 | 等价于"卖出全部"；空仓时调用无副作用 |
| ⑦ | `bt.Cerebro()` 回测总控 | `stdstats=False` 可关掉默认观察器（本项目这么用） |
| ⑧ | 把 DataFrame 变成行情喂进去 | 见第 4 章（列名、时区、复权都要在这层决定） |
| ⑨ | 把策略类挂到引擎上 | 参数用 `cerebro.addstrategy(MyStrategy, period=10)` 传 |
| ⑩ | 设初始资金 | 不设默认 10,000 |
| ⑪ | `run()` 开始逐根推进 | 返回策略实例**列表**（多策略时用得上） |
| ⑫ | 读期末总资产 | 也可以用 `strategy.broker.getvalue()`（第 5.5 节） |

### 1.3 运行它：你会看到什么

**默认什么都看不到**——backtrader 不会自动打印任何东西。想看到过程，有三种办法（由浅入深）：

```python
# 办法 1：在 next() 里 print（最简单，调试够用）
def next(self):
    print(self.datetime.date(0), self.data.close[0], self.sma20[0])

# 办法 2：加观察器，画图时能看到现金/市值/买卖点
cerebro = bt.Cerebro(stdstats=True)      # 默认就是 True
cerebro.plot()                           # 需要 matplotlib

# 办法 3：加 Writer，把整个运行过程写成文件（数据量大时最好用）
cerebro.addwriter(bt.WriterFile, csv=True, out='run.csv')
```

**你会看到的典型输出**（办法 1）：

```
2024-01-02 100.0 nan
2024-01-03 101.0 nan
...
2024-02-01 122.0 110.3      ← 从第 20 根开始才有 MA20
```

看到 `nan` 不要慌——这是 `minperiod` 在起作用（第 3.4 节）。

### 1.4 骨架里 5 个可以换掉的位置

| 位置 | 换什么 | 去哪一节看 |
|---|---|---|
| 数据源 | CSV / 数据库 / 在线接口 | 第 4 章 |
| 策略逻辑 | 均线、动量、多因子…… | 第 5 章 + `strategies/backtrader/` |
| 手续费模型 | A 股佣金+印花税+最低 5 元 | 第 9.4 节 |
| 成交时点 | 默认次日开盘（推荐）；也可当根收盘 | 第 9.2 节 |
| 统计口径 | 夏普、回撤、交易明细 | 第 7 章 |

---

## 第 2 章 Line：backtrader 的世界观

### 2.1 什么是 Line

**Line 就是"一条随 K 线逐格推进的数值序列"**，可以想成一行按时间排好的数字：

```
      [0]   [-1]  [-2]  [-3] ...
close 104.0 103.0 102.0 101.0      ← 当前是第 4 根
sma3  102.0 101.0 100.0   nan      ← 均线也是 Line
```

backtrader 里**所有东西都是 Line**：行情（`close`/`open`）、指标（`sma`/`rsi`）、你算的中间量（`self.spread`）。所以它们的用法完全一样——这是它最统一、也最省心的地方。

### 2.2 索引方向：`[0]` 是今天，`[-1]` 是昨天，`[1]` 是**明天**

| 写法 | 含义 | 能不能用 |
|---|---|---|
| `close[0]` | **当前**这根（今天） | ✅ 天天用 |
| `close[-1]` | 前一根（昨天） | ✅ 常用 |
| `close[-2]` | 前天 | ✅ |
| `close[1]` | **下一根（未来）** | ❌ 绝对不要 |
| `close[2]` | 后天 | ❌ |

**⚠️ 两个陷阱（都在 backtrader 1.9.78.123 上实测过）：**

**陷阱一：在"第 1 根"上写 `[-1]`，它会绕到数据集的最后一行。**

```text
# 实测（数据集共 12 根，close = 100,101,...,111）
第 1 根: close[0] = 100.0
第 1 根: close[-1] = 111.0        ← 不是"上一根"，而是数据集最后一根！
第 1 根: close[1] = 101.0         ← 未来（第 2 根）
```

原因：backtrader 为了速度，会**预载整段数据**（`preload=True`，默认开着）。索引在内部是一个环形数组，第 1 根上 `[-1]` 就是"往回绕一格"，于是绕到了末尾。**这不是报错，是静默给出未来数据**——所以它比 `close[1]` 更危险。

**什么时候会踩到？** 当你绕过 `next()`、直接在 `prenext()` 里读 `[-1]` 时。`next()` 本身是安全的（因为它最早在第 `minperiod` 根才被调用，见 3.4）。

> 本仓库的约定：**只允许 `[0]` 和负索引**，且 `prenext()` 里不读 `[-1]`。`bt_s01` 的注释里也专门写了这一条。

**陷阱二：`[1]` 不会报错，会直接给你未来数据。** 实测第 1 根上 `close[1] = 101.0`（第 2 根的收盘价）。所以在回测里看到正索引，基本可以直接判定"这里有未来函数"。

### 2.3 三种取数方式，别搞混

| 写法 | 返回 | 什么时候用 |
|---|---|---|
| `close[0]` / `close[-1]` | **单个数字** | 取某一根的值 |
| `close.get(size=5)` | **array**（`array.array`，最旧→最新） | 要算"最近 5 根"的统计 |
| `close.get(ago=-1)` | **array**（长度 1） | 取"上一根"（等价 `close[-1]`，但返回容器） |

**实测**：

```text
第 4 根: close.get(size=3)      -> [101.0, 102.0, 103.0]     # 最旧→最新
第 4 根: type(...)              -> array                      # ⚠️ 不是 list！
第 4 根: close.get(ago=1)       -> array('d', [104.0])        # ⚠️ ago 正数 = 未来！
```

> **两个反直觉点（很多教程写错）**：
> 1. `get(size=n)` 返回的是 **`array.array`，不是 Python list**。大多数时候它能像 list 一样用（索引、切片、`sum()`、`len()`），但 `array + array` 是拼接、`array + list` 会报错。要当 list 用，先 `list(...)`。
> 2. **`ago` 的正负和索引 `[]` 一致**：`get(ago=-1)` 是昨天，`get(ago=1)` 是**明天**。写 `get(ago=1)` 想表达"上一根"是最常见的未来函数来源之一。

```python
# 正确：取最近 5 根收盘价算均值（含今天）
ma5 = sum(self.data.close.get(size=5)) / 5

# 正确：取上一根的收盘
prev = self.data.close.get(ago=-1)

# 或者更简单，直接索引
prev = self.data.close[-1]
```

### 2.4 Line 之间可以直接做算术

两条 Line 相减、相除、比较，引擎会**逐格**帮你算，得到的还是一条 Line：

```python
def __init__(self):
    self.ma_fast = bt.ind.SMA(self.data.close, period=5)
    self.ma_slow = bt.ind.SMA(self.data.close, period=20)
    self.spread  = self.ma_fast - self.ma_slow       # 价差线
    self.ratio   = self.ma_fast / self.ma_slow       # 比值线（>1 表示短期在上）
    self.is_up  = self.ma_fast > self.ma_slow        # 布尔线

def next(self):
    print(self.spread[0], self.is_up[0])             # 在 next 里读数
```

> 注意：`self.spread` 这类"派生线"**必须在 `__init__` 里定义**，不要在 `next()` 里反复创建。

### 2.5 为什么一开始老是 `nan`

指标需要足够的历史。MA20 在第 19 根之前都是 `nan`（空值）。这不是 bug，而是"数据不够"。

判断办法：

```python
def next(self):
    if len(self.data) < 20:      # 保险起见自己再判一次
        return
```

但通常**不需要**这么写——`minperiod` 已经帮你挡住了（第 3.4 节）。你只需要知道：**看到 nan，先想"我是不是在数据不够的时候读值了"。**

### 2.6 本节错误对照表

| 现象 | 原因 | 正确写法 |
|---|---|---|
| 回测收益异常高 | 用了 `close[1]` 等正索引 | 改用 `[0]`/负索引 |
| 第 1 根就算出结果 | `prenext()` 里读了 `[-1]`（绕到最后一行） | `prenext()` 里不读数据，或自己判 `len()` |
| `array` 上做 `+` 报错 | `get(size=n)` 返回 array 不是 list | 先 `list(...)` |
| 取"昨天"取到了明天 | 写成 `get(ago=1)` | 改成 `get(ago=-1)` 或 `close[-1]` |
| 指标一直是 nan | 数据根数不足 `minperiod` | 正常；或缩小 `period` |
---

## 第 3 章 生命周期：一根 K 线上到底发生了什么

### 3.1 策略的完整回调清单

下面这些方法，你在策略类里"重写"哪个，引擎就会在对应时机调用它。**不需要全部写，按需重写**。

| 回调 | 什么时候调用 | 通常用来做 |
|---|---|---|
| `__init__()` | 回测开始前，**一次** | 声明指标、初始化变量 |
| `start()` | 比 `__init__` 稍晚，**一次** | 打印初始资金、读 `self.broker` |
| `prenext()` | 数据不足 `minperiod` 的每一根 | 默认什么都不做；想"提前运行"就转调 `next()` |
| `nextstart()` | **第一次**凑够 `minperiod` 的那一根 | 默认转调 `next()` |
| `next()` | 之后每一根 | **你的主逻辑** |
| `next_open()` 等 | 开盘前（需配合 Cheat-On-Open） | 按开盘价决策 |
| `notify_order(order)` | 订单状态**每一次**变化 | 知道成交价/手续费/被拒 |
| `notify_trade(trade)` | 一笔交易开仓或平仓 | 统计盈亏笔数 |
| `notify_cashvalue(cash, value)` | 现金/总资产变化 | 记录净值（本项目用 Analyzer 替代） |
| `notify_data(data, status, dt)` | 数据源状态变化 | 处理停牌/新数据 |
| `notify_timer(timer, when)` | 定时器触发 | 定时调仓 |
| `stop()` | 回测结束，**一次** | 打印统计、保存结果 |

### 3.2 一段真实执行轨迹（照着这张表读代码）

设数据是 12 根、策略是 `SMA(3)`。下面的表是**实测打印出来的**：

```
第 1 根: prenext 被调用   len(self)=1   close[0]=100.0
第 2 根: prenext 被调用   len(self)=2   (SMA 还没值)
第 3 根: next 被调用      len(self)=3   sma3[0]=101.0   ← minperiod=3，从这一根开始
第 4 根: next 被调用      len(self)=4   close[0]=103.0
...
```

**三条要记住的细节：**

1. **`len(self)` 在第一根就是 1，不是 0。**（很多教程会写错。）所以"如果在第一根做点什么"要写 `if len(self) == 1`，不是 `== 0`。
2. `next()` 第一次被调用的那一根，`len(self) == minperiod`（这里是 3）。
3. 在 `prenext()` 里 `close[0]` 是**有值**的（第 1 根就是 100.0）。所以"数据不足"指的是**指标**不足，不是数据没有。

### 3.3 `prenext` / `nextstart` / `next` 的分工

```python
class S(bt.Strategy):
    def __init__(self):
        self.sma20 = bt.ind.SMA(self.data.close, period=20)   # minperiod = 20

    def prenext(self):        # 第 1~19 根：想在这里做事就写
        pass

    def nextstart(self):      # 第 20 根（第一次够）：默认调用 next()
        self.next()

    def next(self):           # 第 20 根及以后：主逻辑
        ...
```

**默认行为**：`prenext()` 什么都不做；`nextstart()` 直接转调 `next()`。所以大多数策略**只需要写 `next()`**。

**什么时候要重写 `prenext()`？** 当你想在"指标还没算出来"的时候就开始记录/判断。本仓库的 `PanelStrategy` 就这么干：

```python
def prenext(self):
    self.next()      # 让日历第一根就开始调度调仓（内部靠 _last_key 防止重复）
```

⚠️ 重写 `prenext()` 后要自己保证**不读 `[-1]`**（第 2.2 节的绕圈陷阱）。

### 3.4 minperiod：引擎是怎么知道你"数据还不够"的

规则很简单：**策略的 minperiod = 所有指标 minperiod 的最大值**，而单条指标的 minperiod 由它的计算窗口决定。

**实测**：
- `SMA(period=3)` → minperiod = 3
- 同时用 `SMA(period=30)` 和 `SMA(period=3)` → 策略 minperiod = **30**（取大的那个）
- **不写 period 的 `SMA()` → minperiod = 30**（因为默认 period=30，见 6.2）

所以：

```python
def __init__(self):
    self.m20 = bt.ind.SMA(self.data.close, period=20)   # 20
    self.m60 = bt.ind.SMA(self.data.close, period=60)   # 60 → 策略 60 根后才开始 next()
```

**这就是它自动防未来函数的原理**：`next()` 最早在第 60 根才被调用，此时 `close[-59]` 一定指向真实的历史数据，不会绕圈。

**如果你想手动控制**（比如指标用了 60，但你想从第 1 根就自己判断）：

```python
def prenext(self):
    self.next()                    # 从第 1 根开始跑
def next(self):
    if len(self.data) < 60:        # 自己兜底
        return
    ...
```

### 3.5 `start()` 与 `stop()`

```python
def start(self):
    print('初始资金', self.broker.getcash())      # 这里可以读账户了

def stop(self):
    print('期末总资产', self.broker.getvalue())
    print('最大回撤', self.stats.drawdown.max.drawdown)   # 若加了 DrawDown 分析器
```

> `start()` 比 `__init__` 晚，所以**读账户信息要放在 `start()`**，不要放 `__init__`。

---

## 第 4 章 DataFeed：把数据喂进去

### 4.1 `bt.feeds.PandasData` 的每个参数

```python
data = bt.feeds.PandasData(
    dataname=df,          # 【必填】DataFrame，索引必须是日期
    datetime=None,        # None = 用 df 的索引当时间；也可给列名
    open='open',          # 列名（或 -1 表示没有这一列）
    high='high',
    low='low',
    close='close',
    volume='volume',
    openinterest=-1,      # 股票没有持仓量 → -1
    timeframe=bt.TimeFrame.Days,   # 周期
    compression=1,        # 几根合成一根（5 分钟线用 5）
)
cerebro.adddata(data, name='510300')   # name 用于多标的时按名字取
```

| 参数 | 默认 | 说明与坑 |
|---|---|---|
| `dataname` | 必填 | 传 DataFrame。backtrader 不复制它，传进去后别再改原表 |
| `datetime` | `None` | `None` = 用索引。若时间在某一列里，写列名 |
| `open/high/low/close/volume` | 自动识别 | 给列名，或 `-1` 表示"没有这列"。**列名大小写不敏感** |
| `openinterest` | `-1` | 股票/ETF 用不到，写 `-1` |
| `timeframe` | `Days` | 日线用 `Days`；分钟线用 `Minutes` |
| `compression` | `1` | 5 分钟线写 `5`。日线保持 1 |
| `sessionstart/sessionend` | `None` | 分钟级数据跨日时需要 |

**列名自动识别规则**：`PandasData` 默认会去找名为 `open/high/low/close/volume/openinterest` 的列（不区分大小写）。所以只要你的表是这套列名，就**不用逐个写参数**：

```python
cerebro.adddata(bt.feeds.PandasData(dataname=df))     # 五列齐全时，这么写就够
```

> 本仓库的 `load_daily()` 返回的正是这套列名（`open/high/low/close/volume`）+ DatetimeIndex，所以 `btlab.runner.add_feed()` 里直接用默认参数。

### 4.2 多数据源：一定要给它起名字

```python
cerebro.adddata(bt.feeds.PandasData(dataname=df_hs300), name='510300')
cerebro.adddata(bt.feeds.PandasData(dataname=df_zz500), name='510500')

def next(self):
    d = self.getdatabyname('510500')     # 按名字拿到那条数据线
    self.buy(d, size=100)                # 给"这条数据"下单
```

| 取法 | 说明 |
|---|---|
| `self.data` | 第一个数据源（等价 `self.datas[0]`） |
| `self.datas` | 所有数据源的列表 |
| `self.getdatanames()` | `['510300', '510500']`（`adddata` 时的 name） |
| `self.getdatabyname('510500')` | 按名字取 |
| `len(d)` | 这条数据已有多少根 K 线 |

### 4.3 多标的的"节拍"问题 —— 以及 `__CAL__` 日历源

backtrader 以**主数据源**（第一个 `adddata` 的）的 K 线数为节拍推进。如果各标的上市时间不同、或者某只票停牌，`next()` 的推进就会**错位**：你以为今天是 3 月 1 日，某只票的数据却还停在 2 月 20 日。

**本仓库的做法**：额外喂一条"每个交易日都有行情"的基准指数，命名为 `__CAL__`，专门当**时钟**：

```python
data['__CAL__'] = load_daily('000300')          # 沪深300 指数，天天有数据
# 加数据时：__CAL__ 会被单独识别出来

class PanelStrategy(bt.Strategy):
    def __init__(self):
        self.cal = self.getdatabyname('__CAL__')                       # 时钟
        self.tradables = [d for d in self.datas if d._name != '__CAL__']  # 真正能交易的

    def next(self):
        cur = self.cal.datetime.date(0)          # 今天（以日历为准）
        for d in self.tradables:
            if not self.live(d, cur):            # 这只票今天有行情吗？
                continue
            ...

    def live(self, d, cur):
        return len(d) > 0 and d.datetime.date(0) == cur
```

**`live()` 为什么这么写**：停牌时，那条数据线的当前日期**不会**前进。所以"它的日期 == 今天"就等价于"它今天有行情"。停牌期间它自动被跳过，不会用旧价格假装成交。

### 4.4 上市时间不同怎么办

```python
def live(self, d, cur):
    return len(d) > 0 and d.datetime.date(0) == cur
```

`len(d) > 0` 同时解决了"这只票还没上市"的情况——没上市时它的数据线是空的。

如果你的策略需要"至少上市 N 天才交易"，再加一条：

```python
if len(d) < 60:      # 上市不足 60 根，跳过
    continue
```

### 4.5 数据频率转换：`resampledata` 与 `replaydata`

```python
# 把日线重采样成周线，喂给策略（策略只需处理周线）
cerebro.resampledata(daily_data, timeframe=bt.TimeFrame.Weeks)

# 或者：把周线拆成一格一格"重放"，策略仍然逐日被调用
cerebro.replaydata(weekly_data, timeframe=bt.TimeFrame.Weeks)
```

| 方法 | 效果 | 什么时候用 |
|---|---|---|
| `resampledata` | 日 → 周，策略只看到周线 | 策略按周线逻辑写（每周一根） |
| `replaydata` | 日 → 周，但每天都被调用，周内数据逐步长出来 | 想"盘中也能看到本周正在形成的 K 线" |

> 本仓库的策略**没有用重采样**：需要"每周/每月调仓"的地方，都是在 `next()` 里自己判断 `(年, 周)`/`(年, 月)` 是否变化（见第 10 章）。这样更直观，也更容易和聚宽的 `run_weekly/run_monthly` 对照。

### 4.6 其他数据源

| 类 | 用途 |
|---|---|
| `bt.feeds.PandasData` | **最常用**：DataFrame 直接喂（本仓库用这个） |
| `bt.feeds.PandasDirectData` | 列按位置直接映射，比上面快一点（列顺序必须固定） |
| `bt.feeds.GenericCSVData` | 从 CSV 文件读（要自己指定列序号/日期格式） |
| `bt.feeds.YahooFinanceData` | 联网拉雅虎数据（A 股覆盖差，不建议） |
| `bt.feeds.BacktraderCSVData` | backtrader 自有格式 |

> 数据来源、复权、缓存这些"脏活"，本仓库都收在 `btlab.datasource` 里（第 14 章），策略层只需要拿到"列名正确的 DataFrame"。
---

## 第 5 章 Strategy：策略里的每个函数

### 5.1 `__init__`：能做什么、不能做什么

```python
def __init__(self):
    self.sma20 = bt.ind.SMA(self.data.close, period=20)   # ✅ 声明指标
    self.trades = 0                                        # ✅ 初始化自己的变量
    self.pending = None                                    # ✅ 记状态

    print(self.data.close[0])      # ❌ 报错：此时还没有任何 K 线
    self.buy(size=100)             # ❌ 不能在初始化阶段下单
```

**一句话**：`__init__` 是"布置舞台"，`next()` 才是"演出"。

### 5.2 `params`：策略参数

三种写法等价，选一种：

```python
class S(bt.Strategy):
    params = (('fast', 5), ('slow', 20), ('stake', 0.95))     # 元组（推荐，最省字）

class S2(bt.Strategy):
    params = dict(fast=5, slow=20)                            # 字典

class S3(bt.Strategy):
    params = (('fast', 5),)                                   # 组合：元组里放元组
```

读参数用 `self.p.fast`（`self.params.fast` 也行）：

```python
def __init__(self):
    self.ma = bt.ind.SMA(self.data.close, period=self.p.slow)   # 参数可以直接喂给指标
```

运行时覆盖：

```python
cerebro.addstrategy(S, fast=10, slow=60)      # 不改源码就能换参数
```

**为什么要用 params 而不是普通变量？** 因为 `optstrategy` 只能优化 `params` 里的参数（第 12 章）。

### 5.3 `next()`：主逻辑

**每一根 K 线调用一次**。你在这里读数据、判断、下单。

```python
def next(self):
    if not self.position:                      # 空仓
        if self.data.close[0] > self.sma20[0]:
            self.buy(size=100)
    else:                                      # 有持仓
        if self.data.close[0] < self.sma20[0]:
            self.close()
```

**注意**：`self.position` 只针对 **`self.data`（第一个数据源）**。多标的时要用 `self.getposition(d)`。

### 5.4 读数据：全部可用写法

| 写法 | 含义 |
|---|---|
| `self.data.close[0]` | 当前收盘 |
| `self.data.close[-1]` | 昨收（⚠️ 别在 `prenext` 里用，见 2.2） |
| `self.data.close.get(size=5)` | 最近 5 根（返回 array） |
| `self.data.open/high/low/close/volume[0]` | 当前 OHLCV |
| `self.data.datetime.date(0)` | 当前日期（`datetime.date` 对象） |
| `self.datetime.date(0)` | 同上（策略级时间） |
| `len(self.data)` | 这条数据已有多少根 |
| `len(self)` | 策略已推进多少根（第一根是 1） |
| `self.data._name` | 这条数据的名字（`adddata(name=...)` 给的那个） |

> 小技巧：`self.data` 就是 `self.datas[0]`。多标的时建议先 `d = self.getdatabyname('510300')` 拿到局部变量，代码会清爽很多。

### 5.5 读账户与持仓

```python
self.broker.getcash()          # 可用现金
self.broker.getvalue()         # 总资产 = 现金 + 持仓市值
self.getposition(self.data)    # 持仓对象（多标的时用）
self.position                  # 等价 self.getposition(self.data)
```

**`position` 对象**（实测的公开属性）：

| 属性 | 含义 |
|---|---|
| `position.size` | 持仓股数：**正数=多头，负数=空头，0=空仓** |
| `position.price` | 持仓成本价（加权平均） |
| `position.price_orig` | 未调整的原始成本价 |
| `position.adjbase` | 复权调整基准 |
| `position.upopened` / `position.upclosed` | 已开/已平的累计数量 |

**判断持仓的三种写法**：

```python
if not self.position:            # 空仓（推荐，最直观）
    ...
if self.position.size == 0:      # 同上
    ...
if self.position.size > 0:       # 多头
    ...
```

### 5.6 下单：`buy` / `sell` / `close` / `order_target_*`

#### （a）最常用的四个

```python
self.buy(size=100)                       # 买 100 股（下一根开盘成交）
self.sell(size=100)                      # 卖 100 股（可以是开空，也可以是平多）
self.close()                             # 平掉 self.data 的全部持仓
self.cancel(order)                       # 撤单（需要先拿到 order 对象）
```

`buy()` 的完整签名（实测）：

```python
buy(data=None, size=None, price=None, plimit=None, exectype=None, valid=None,
    tradeid=0, oco=None, trailamount=None, trailpercent=None,
    parent=None, transmit=True, **kwargs)
```

| 参数 | 说明 |
|---|---|
| `data` | 哪条数据（多标的必填，单标的可省略） |
| `size` | 股数。**不填**则交给 sizer（本项目手算，所以总是填） |
| `price` | 限价单的限价（配合 `exectype=bt.Order.Limit`） |
| `exectype` | 订单类型，见下表 |
| `valid` | 有效期（`datetime` 或 `timedelta`） |

**订单类型**（`bt.Order.xxx`）：

| 常量 | 含义 |
|---|---|
| `Market` | 市价单（**默认**） |
| `Close` | 收盘价单 |
| `Limit` | 限价单 |
| `Stop` | 止损/突破单 |
| `StopLimit` | 止损限价 |
| `StopTrail` / `StopTrailLimit` | 移动止损（/限价版） |

#### （b）"调到目标仓位"的三个函数

```python
self.order_target_size(target=1000)         # 调到 1000 股
self.order_target_value(target=500_000)     # 调到 50 万元市值
self.order_target_percent(target=0.5)       # 调到总资产的 50%
```

实测签名：`order_target_percent(data=None, target=0.0, **kwargs)`，返回订单对象（不成交则返回 `None`）。

**⚠️ A 股必须自己整手**：这三个函数是按 `目标市值 / 价格` 直接算股数的，**它不知道 A 股要 100 股一手**。所以本仓库没有直接用它们，而是自己算完再用 `round_lot()` 取整：

```python
size = round_lot(self.broker.getvalue() * 0.5 / self.data.close[0])   # 向下取到整手
if size > 0:
    self.buy(size=size)
```

**为什么用 `close[0]` 算股数、却按次日开盘成交？** 因为下单那一刻你只知道今天的收盘价。次日开盘价可能高开，所以本仓库统一留 **2% 缓冲**（`cap=0.98`），避免"算出来刚好够、实际因为高开导致现金不足被拒单"。

#### （c）下单会不会失败？

会。最常见的是**现金不足**，订单状态会变成 `Margin`（见 5.7）。所以：

- 留缓冲（不要用 100% 资金）；
- 或者重写 `notify_order()` 把失败打印出来，否则你会"以为买了其实没买"。

### 5.7 `notify_order`：订单状态机

订单不是"下了就成交"，而是一个状态机。**实测**：一次正常买入会经历 `Submitted → Accepted → Completed`。

| 状态常量 | 含义 |
|---|---|
| `order.Submitted` | 已提交给 broker |
| `order.Accepted` | broker 已受理 |
| `order.Partial` | 部分成交 |
| `order.Completed` | **完全成交** |
| `order.Canceled` / `Cancelled` | 已撤销 |
| `order.Margin` | **现金/保证金不足被拒**（最常见） |
| `order.Rejected` | 被拒 |
| `order.Expired` | 超时失效 |

**成交信息**（`order.executed`）：

| 属性 | 含义 |
|---|---|
| `order.executed.price` | 成交均价 |
| `order.executed.size` | 成交量（**买正、卖负**） |
| `order.executed.value` | 成交金额 |
| `order.executed.comm` | 手续费 |

**完整可抄的写法**：

```python
def notify_order(self, order):
    # 1) 中间态直接忽略（Submitted/Accepted 会调用很多次）
    if order.status in (order.Submitted, order.Accepted):
        return
    # 2) 成交
    if order.status == order.Completed:
        side = '买入' if order.isbuy() else '卖出'
        print(f'{self.datetime.date(0)} {side} '
              f'价={order.executed.price:.3f} 量={order.executed.size} '
              f'费={order.executed.comm:.2f}')
    # 3) 失败
    elif order.status in (order.Canceled, order.Margin, order.Rejected):
        print(f'{self.datetime.date(0)} 未成交: {order.getstatusname()}')
```

> `order.getstatusname()` 返回的是**英文**状态名（如 `'Completed'`、`'Margin'`），不是中文——实测确认。想输出中文就要自己映射。

**为什么必须有这个回调？** 因为"下单成功"≠"成交成功"。不写它，你永远不会知道订单被拒了。

### 5.8 `notify_trade`：一笔交易的盈亏

**"一笔交易（trade）"= 从开仓到完全平仓**。注意它和"一张订单"不是一回事：分批买入、一次卖出，可能只算一笔 trade。

```python
def notify_trade(self, trade):
    if trade.isclosed:                     # 平仓时
        print(f'毛利={trade.pnl:.2f} 净利(扣费)={trade.pnlcomm:.2f}')
```

| 属性 | 含义 |
|---|---|
| `trade.isclosed` | 是否已平仓 |
| `trade.size` | 当前数量（开仓中） |
| `trade.price` | 持仓均价 |
| `trade.pnl` | 毛利 |
| `trade.pnlcomm` | 扣费后净利 |

### 5.9 其他通知

```python
def notify_cashvalue(self, cash, value):
    """每天现金/总资产变化时调用（本项目改用 Analyzer 记录净值）"""
    print(cash, value)

def notify_data(self, data, status, dt=None):
    """数据源状态变化：如 DELAYED / LIVE / NOTSUBSCRIBED（回测里主要用于停牌）"""

def notify_timer(self, timer, when, *args, **kwargs):
    """配合 cerebro.add_timer() 使用，定时触发（如每天 14:50）"""
```

### 5.10 一个"照着读就能懂"的完整策略

下面这段把本章的知识点串起来，**每一行都有注释**：

```python
import backtrader as bt

class DoubleMA(bt.Strategy):
    """双均线：金叉买入（用 95% 资金），死叉清仓。"""

    params = (('fast', 5), ('slow', 20), ('stake', 0.95))

    def __init__(self):
        # ① 只声明，不读值。minperiod 会自动取 20
        self.ma_fast = bt.ind.SMA(self.data.close, period=self.p.fast)
        self.ma_slow = bt.ind.SMA(self.data.close, period=self.p.slow)
        self.cross = bt.ind.CrossOver(self.ma_fast, self.ma_slow)   # >0 金叉，<0 死叉

    def next(self):
        if not self.position:                      # ② 空仓才考虑买
            if self.cross[0] > 0:                  # ③ 今天发生金叉
                cash = self.broker.getcash()       # ④ 用现金（不是总资产）算股数
                size = int(cash * self.p.stake / self.data.close[0]) // 100 * 100
                if size > 0:
                    self.buy(size=size)            # ⑤ 下一根开盘成交
        elif self.cross[0] < 0:                    # ⑥ 持仓且死叉
            self.close()                           # ⑦ 清仓

    def notify_order(self, order):
        if order.status == order.Completed:
            side = '买' if order.isbuy() else '卖'
            print(f'{self.datetime.date(0)} {side} '
                  f'{order.executed.size} 股 @ {order.executed.price:.3f} '
                  f'手续费 {order.executed.comm:.2f}')
        elif order.status in (order.Margin, order.Rejected):
            print(f'{self.datetime.date(0)} 订单被拒：{order.getstatusname()}')
```

**运行后你会看到**：一串"买/卖"日志（只在金叉死叉那天出现），以及最后的总资产。中间那些 `nan` 阶段不会有任何输出，因为 `minperiod=20` 让 `next()` 从第 20 根才开始跑。
---

## 第 6 章 Indicator：指标

### 6.1 心智模型：你只"声明"，引擎负责"逐格算"

```python
def __init__(self):
    self.sma = bt.ind.SMA(self.data.close, period=20)     # 声明：我要一条 20 日均线
def next(self):
    print(self.sma[0])                                    # 读数：这条线当前的值
```

你**没有**写任何循环，也**没有**管窗口怎么滑动。引擎每推进一根 K 线，就把这条线往前算一格。这就是"声明式"。

**关键**：`bt.ind.SMA(...)` 必须**在一个策略内部**创建。单独写 `bt.ind.SMA()` 会报 `'NoneType' object has no attribute 'datas'`——因为指标需要一个"主人"（数据源）才知道算谁。

### 6.2 常用指标逐个讲（默认值均为实测）

#### 均线家族

| 写法 | 公式 | 默认 `period` | 输出的线 |
|---|---|---|---|
| `bt.ind.SMA(period=30)` 简单均线 | 最近 n 个收盘价的算术平均 | **30**（⚠️ 不是 20） | `.sma` |
| `bt.ind.EMA(period=30)` 指数均线 | 近期权重更大，`α=2/(n+1)` | 30 | `.ema` |
| `bt.ind.WMA(period=30)` 加权均线 | 权重 1,2,…,n | 30 | `.wma` |
| `bt.ind.SMMA(period=30)` 平滑均线 | 也叫 Wilder 均线（RSI/ATR 内部用） | 30 | `.smma` |
| `bt.ind.DEMA/TEMA` 双/三指数 | 对 EMA 再做一次 EMA，更平滑 | 30 | — |

**什么时候用哪种**：SMA 最直观、教学首选；EMA 反应快、适合趋势；WMA/SMMA 用得少，知道有就行。

**⚠️ 最容易踩的坑**：`bt.ind.SMA()` 不写 `period` 是 **30**，不是 20。所以**永远显式写 `period=`**。

```python
self.ma20 = bt.ind.SMA(self.data.close, period=20)    # ✅ 写清楚
self.ma   = bt.ind.SMA(self.data.close)               # ❌ 其实是 30 日线
```

#### 摆动类（判断超买超卖）

| 指标 | 写法 | 默认参数 | 怎么看 |
|---|---|---|---|
| RSI 相对强弱 | `bt.ind.RSI(period=14)` | `period=14, upperband=70, lowerband=30` | 70 以上超买、30 以下超卖 |
| 随机指标 KD | `bt.ind.Stochastic()` | `period=14, period_dfast=3, period_dslow=3` | 读 `.percK` `.percD` |
| 威廉指标 | `bt.ind.WilliamsR(period=14)` | `period=14, upperband=-20, lowerband=-80` | 反向的超买超卖 |
| CCI 顺势指标 | `bt.ind.CCI(period=20)` | `period=20, factor=0.015` | ±100 为界 |
| ADX 趋势强度 | `bt.ind.ADX(period=14)` | `period=14` | **只测强度、不测方向**；>25 算有趋势 |

#### 趋势与通道

| 指标 | 写法 | 默认 | 输出的线 |
|---|---|---|---|
| MACD | `bt.ind.MACD()` | `period_me1=12, period_me2=26, period_signal=9` | **实测**：`.macd` `.signal`（**没有 `.histo`**） |
| MACD 柱 | `bt.ind.MACDHisto()` | 同上 | `.histo`（是**另一个指标**，不是 MACD 的线） |
| 布林带 | `bt.ind.BBands(period=20)` | `period=20, devfactor=2.0` | **实测**：`.mid` `.top` `.bot`（**没有 `.pctb`**） |
| %B | `bt.ind.PercentB()` | — | `.pctb`（是**另一个指标**，表示价格在布林带里的位置） |
| 真实波幅 | `bt.ind.ATR(period=14)` | `period=14` | `.atr`，常用来设止损距离/仓位 |

> 这两条是**实测纠正**：旧版本文档把 `.histo` 写成 MACD 的线、把 `.pctb` 写成 BBands 的线，会让人写出 `self.macd.histo[0]` 这种报错代码。它们是独立指标。

#### 交叉与极值（择时最常用）

| 写法 | 含义 | 返回值 |
|---|---|---|
| `bt.ind.CrossOver(a, b)` | a 上穿/下穿 b | `>0` 金叉（上穿），`<0` 死叉（下穿），`0` 无 |
| `bt.ind.CrossUp(a, b)` / `CrossDown` | 只管一个方向 | 布尔（1/0） |
| `bt.ind.Highest(period=n)` | 最近 n 根的最高 | 数值（默认 `period=1`） |
| `bt.ind.Lowest(period=n)` | 最近 n 根的最低 | 数值 |

**怎么读 CrossOver**：

```python
if self.cross[0] > 0:      # 今天发生金叉 → 买入信号
    ...
if self.cross[0] < 0:      # 今天发生死叉 → 卖出信号
    ...
```

注意它只在"发生穿越的那一根"给非零值，**不是**"短均线在长均线上方就一直 >0"。要判断"当前谁在上面"，直接比大小：

```python
if self.ma_fast[0] > self.ma_slow[0]:     # 当前短均线在上（状态）
    ...
```

#### 统计与变换

| 写法 | 含义 | 默认 |
|---|---|---|
| `bt.ind.PctChange(period=30)` | 相对 n 根前的变化率（小数） | 30 |
| `bt.ind.StdDev(period=20)` | 滚动标准差（波动率） | 20 |
| `bt.ind.Momentum(period=12)` | `close - close[-n]`（价差，不是百分比） | 12 |
| `bt.ind.ROC(period=12)` / `ROC100` | 变动率（百分比版） | 12 |
| `bt.ind.PercentRank(period=50)` | 当前值在近 n 根中的分位 | 50 |
| `bt.ind.OLS_Slope_InterceptN(period=10)` | 滚动线性回归 | `period=10`，读 `.slope` `.intercept` |
| `bt.ind.CumSum()` | 累加 | `seed=0.0` |
| `bt.ind.Sum(n)` | 最近 n 根之和 | — |

> **别名**：`bt.ind.SMA` / `SimpleMovingAverage` / `MovingAverageSimple` 都是同义的（实测它们**不是同一个类对象**，但注册成了同义名，任选其一即可，推荐短名）。

### 6.3 指标之间可以直接运算

```python
def __init__(self):
    self.m20 = bt.ind.SMA(self.data.close, period=20)
    self.m60 = bt.ind.SMA(self.data.close, period=60)
    self.bias  = self.data.close / self.m60 - 1        # 偏离度（Line 运算）
    self.above = self.data.close > self.m20            # 布尔线
    self.z     = (self.bias - 0) / 0.02                # 也可以继续算
```

### 6.4 nan 与 minperiod 的实际表现

**实测**：`SMA(period=3)` 在第 1、2 根上是 `nan`，第 3 根开始有值（101.0）。同时：

- 指标的 `_minperiod` 会**汇总到策略**：策略的 `minperiod` = 所有指标里的最大值。
- 所以只要用了 `SMA(period=60)`，`next()` 就从第 60 根才开始被调用——**你几乎不会在 `next()` 里读到 nan**（除非用了会"后置才有值"的指标，如 MACD 的 signal）。

### 6.5 自定义指标

```python
class MyRange(bt.Indicator):
    lines = ('rng',)                       # ① 声明输出线（可以有多个）
    params = (('period', 10),)             # ② 参数
    plotinfo = dict(subplot=True)          # ③ 画图时单独一个子图

    def __init__(self):
        hh = bt.ind.Highest(self.data.high, period=self.p.period)
        ll = bt.ind.Lowest(self.data.low,  period=self.p.period)
        self.lines.rng = hh - ll           # ④ 给输出线赋值
```

用起来和内置指标一样：

```python
def __init__(self):
    self.rng = MyRange(self.data, period=10)
def next(self):
    print(self.rng.rng[0])
```

### 6.6 本节错误对照表

| 现象 | 原因 | 正确写法 |
|---|---|---|
| `AttributeError: 'MACD' object has no attribute 'histo'` | histo 不在 MACD 上 | 用 `bt.ind.MACDHisto()` |
| `AttributeError: ... 'pctb'` | pctb 不在 BBands 上 | 用 `bt.ind.PercentB()` |
| 均线是 30 日线的结果 | 忘了写 `period` | 永远显式写 `period=` |
| 单独 `bt.ind.SMA()` 报错 | 指标没有"主人" | 在策略 `__init__` 里创建 |
| 指标值一直是 nan | 数据根数不够 | 正常；或减小 `period` |

---

## 第 7 章 Analyzer：事后统计

### 7.1 用法三步

```python
cerebro.addanalyzer(bt.analyzers.DrawDown, _name='dd')    # ① 挂上去
strat = cerebro.run()[0]                                  # ② 跑，拿到策略实例
dd = strat.analyzers.dd.get_analysis()                    # ③ 用 _name 取结果
print(dd['max']['drawdown'])                              # 读需要的字段
```

`_name` 是**你自己起的键名**，不写的话 backtrader 会用类名的小写形式。

### 7.2 内置分析器：产出什么、怎么读

| 分析器 | 产出 | 读法示例 |
|---|---|---|
| `TradeAnalyzer` | 交易统计 | **实测**（无交易时）顶层只有 `total`；有交易后会有 `won/lost/long/short` 等块 |
| `DrawDown` | 回撤 | **实测**顶层键：`len` `drawdown` `moneydown` `max`；最大回撤在 `dd['max']['drawdown']`（单位 %） |
| `TimeReturn` | 按周期收益率 | `timeframe=bt.TimeFrame.Months` 得月度收益 |
| `SharpeRatio` | 夏普比率 | ⚠️ 见下方"为什么是 None" |
| `SharpeRatio_A` | 年化夏普 | 同上 |
| `AnnualReturn` | 每年收益率 | 字典 {年: 收益率} |
| `Calmar` / `SQN` / `VWR` | Calmar / 系统质量分 / 变动率加权收益 | 需额外参数 |
| `Transactions` | **逐笔成交明细** | 本项目用它算成交笔数与换手率 |
| `PositionsValue` | 每日各持仓市值 | 组合分析 |
| `GrossLeverage` | 杠杆率 | 检查有没有偷偷加杠杆 |
| `PyFolio` | 生成 pyfolio 所需全套序列 | 进阶 |

**⚠️ 实测：`SharpeRatio` 很容易返回 `{'sharperatio': None}`**，常见原因：

1. 净值曲线完全没有波动（收益标准差为 0）→ 分母为 0；
2. 数据根数太少；
3. `timeframe` / `compression` 与数据频率不一致（它默认 `riskfreerate=0.01`，按年化处理）。

**所以本项目没有用内置 SharpeRatio**，而是在 `btlab/metrics.py` 里用每日净值自己算：

```python
sharpe = rets.mean() / rets.std() * (252 ** 0.5)     # 无风险利率按 0 处理
```

好处是口径完全可控、和聚宽/研报的常用口径一致。**这也是一个通用经验：教学和实盘里，自己算指标往往比用黑盒分析器更放心。**

### 7.3 自定义 Analyzer（本项目记录净值用的就是它）

```python
class NavRecorder(bt.Analyzer):
    def start(self):                       # 回测开始：准备容器
        self._d, self._v = [], []

    def _rec(self):                        # 每根 K 线记录一次
        self._d.append(self.strategy.datetime.date(0))
        self._v.append(self.strategy.broker.getvalue())

    def prenext(self):  self._rec()        # 数据不足时也要记（否则曲线开头会缺）
    def nextstart(self): self._rec()
    def next(self):     self._rec()

    def get_analysis(self):                # 回测结束：把结果交给调用方
        return pd.Series(self._v, index=pd.to_datetime(self._d), name='nav')
```

| Analyzer 生命周期 | 时机 |
|---|---|
| `start()` | 回测开始一次 |
| `prenext()` / `nextstart()` / `next()` | 与策略同名回调同步 |
| `stop()` | 回测结束一次 |
| `get_analysis()` | 你主动取结果时调用 |

> 本仓库的 `NavRecorder` 还额外做了一件事：把当前日期写进手续费模型（用于按日期切换印花税）。这是"Analyzer 也能反过来影响引擎"的实用例子（第 9.4 节）。

### 7.4 一次取多个分析器结果

```python
strat = cerebro.run()[0]
print('期末资产', strat.broker.getvalue())
print('最大回撤', strat.analyzers.dd.get_analysis()['max']['drawdown'])
print('成交笔数', len(strat.analyzers.txn.get_analysis()))
```

---

## 第 8 章 Observer / Sizer / Writer

### 8.1 Observer：运行中的"仪表盘"

Observer 是画在图上、随回测实时更新的小面板（现金、市值、买卖点、交易盈亏）。它**不影响策略逻辑**，只影响画图。

```python
cerebro = bt.Cerebro(stdstats=False)     # 关掉默认观察器（本项目这么做，避免弹图）
cerebro.addobserver(bt.observers.Broker) # 想加哪个单独加
```

**什么时候关心它**：只有在你用 `cerebro.plot()` 图形化看回测时才需要。批量跑测试时关掉更清爽。

### 8.2 Sizer：让引擎决定"下多少股"

```python
cerebro.addsizer(bt.sizers.FixedSize, stake=100)   # 每次固定 100 股
def next(self):
    self.buy()          # 不写 size 时，由 sizer 决定
    self.buy(size=50)   # 写了 size，sizer 被忽略
```

内置的有 `FixedSize` / `FixedReverser` / `PercentSizer` / `AllInSizer` 等。

> **本项目为什么不用 Sizer**：A 股的约束是"整手（100 股）+ 目标权重 + 留缓冲 + 停牌不交易"，这些用 Sizer 表达反而绕。所以 `btlab.runner` 自己算股数（`round_lot`），逻辑写在策略里、一眼能看懂。

### 8.3 Writer：把运行过程写成文件

```python
cerebro.addwriter(bt.WriterFile, csv=True, out='run.csv')
```

它会把每根 K 线的数据、指标、订单、交易写成 CSV。**数据量大时，这比 `print()` 好用得多**（不会把终端刷爆，还能丢进 pandas 分析）。
---

## 第 9 章 Broker：撮合、费用、滑点、成交时点

### 9.1 默认撮合规则（最重要）

```
你在第 t 根的 next() 里下单
        ↓
订单进入队列，第 t 根【不成交】
        ↓
第 t+1 根【开盘价】成交（并扣除手续费/滑点）
```

**一个带数字的例子**（假设无手续费、无滑点）：

| 时间 | 价格 | 发生的事 |
|---|---|---|
| 第 t 根 | 收盘 4.00 | 你的 `next()` 判断 MA 金叉，调用 `self.buy(size=1000)` |
| 第 t+1 根 | 开盘 4.02 | 引擎以 **4.02** 成交 1000 股，花掉 4020 元 |
| 第 t+1 根 | 收盘 4.05 | 你的持仓市值变成 4050 元（浮盈 30 元） |

**为什么不是 4.00 成交？** 因为 4.00 是"昨天的收盘价"，你昨天收盘时才看到信号，现实中已经买不到了。

如果你在 `next()` 之外（比如 `next_open()`）下单，成交规则会不同——见 9.2。

### 9.2 Cheat-On-Open / Cheat-On-Close：什么时候允许"作弊"

| 开关 | 效果 | 什么时候可以开 |
|---|---|---|
| 默认 | 决策 → **下一根开盘**成交 | 绝大多数情况（推荐） |
| `cerebro.broker.set_coc(True)` | 决策 → **当根收盘**成交 | 只有你能证明"收盘前就已经决策完了"（例如用 14:50 的数据算信号） |
| `cerebro.broker.set_coo(True)` | 决策 → **当根开盘**成交 | 只有你能证明"开盘前就已经决策完了" |

```python
cerebro.broker.set_coc(True)     # Cheat-On-Close
cerebro.broker.set_coo(True)     # Cheat-On-Open
```

> **本仓库 20 个策略全部使用默认模式**（收盘决策 → 次日开盘成交）。理由：这是"隔夜决策"的真实约束，而且天然免疫未来函数。**看到别人回测收益异常高，先问一句"是不是开了 coc"。**

### 9.3 简易佣金：`setcommission`

```python
cerebro.broker.setcommission(commission=0.0003)     # 双边 0.03%
```

| 参数 | 默认 | 说明 |
|---|---|---|
| `commission` | 0.0 | 费率。`percabs=True` 时 `0.0003` = 0.03% |
| `commtype` | None | `COMM_PERC`（按金额比例）/ `COMM_FIXED`（按股数/手数） |
| `percabs` | True | True = 直接给小数（0.001 就是 0.1%）；False = 还要再除以 100 |
| `stocklike` | False | **股票/ETF 必须设 True**（否则按期货保证金逻辑算） |
| `margin` / `mult` | None / 1.0 | 期货保证金与合约乘数 |
| `leverage` / `interest` | 1.0 / 0.0 | 杠杆与融资利率 |

**它表达不了 A 股**：印花税只在卖出收、还有单笔最低 5 元——这两个必须自己扩展（9.4）。

### 9.4 A 股真实费用：自定义 `CommInfoBase`（与仓库代码一致）

A 股股票的三条规则：

1. **佣金**：买卖双边各 0.03%，**单笔最低 5 元**；
2. **印花税**：**只在卖出**收，2023-08-28 之前 0.1%、之后 0.05%；
3. **过户费**：小额，本仓库未单独建模（影响很小）。

```python
import datetime
import backtrader as bt

# 印花税减半的日子：2023-08-28 之前 0.1%，之后 0.05%
_STAMP_DUTY_CUTOFF = datetime.date(2023, 8, 28)


class AStockCommission(bt.CommInfoBase):
    """A 股费用模型：佣金双边（单笔最低 5 元）+ 印花税仅卖出。"""

    params = (
        ('stocklike', True),
        ('commtype', bt.CommInfoBase.COMM_PERC),
        ('percabs', True),           # commission 按绝对百分比解释：0.0003 = 0.03%
        ('commission', 0.0003),      # 佣金（买卖双边）
        ('stamp_duty', 0.0005),      # 印花税（仅卖出，2023-08-28 起）
        ('stamp_duty_pre', 0.0010),  # 印花税（2023-08-28 之前）
        ('min_comm', 5.0),           # 单笔最低佣金（元）
    )

    def _getcommission(self, size, price, pseudoexec):
        value = abs(size) * price
        if value <= 0:
            return 0.0
        comm = value * self.p.commission
        if comm < self.p.min_comm:        # 最低佣金只兜底"佣金"本身
            comm = self.p.min_comm
        if size < 0:                      # size<0 = 卖出方向
            today = getattr(self, 'today', None)
            rate = (self.p.stamp_duty_pre
                    if today is not None and today < _STAMP_DUTY_CUTOFF
                    else self.p.stamp_duty)
            comm += value * rate
        return comm


cerebro.broker.addcommissioninfo(AStockCommission())
```

**逐行讲清楚三件事：**

1. **`size < 0` 就是卖出**。backtrader 用正负号表示方向：买入 `size>0`、卖出 `size<0`。所以"只在卖出收印花税"写成 `if size < 0`。
2. **`min_comm` 只兜底佣金**，不是兜底总额。现实中"最低 5 元"指的是券商佣金，印花税另算。所以先 `max(佣金, 5)`，再加印花税（旧写法把总额和 5 比大小，会少算印花税）。
3. **`self.today` 是谁写进去的？** 是 `NavRecorder`（一个 Analyzer）每根 K 线写一次：

```python
class NavRecorder(bt.Analyzer):
    params = (('comm', None),)
    def _rec(self):
        if self.p.comm is not None:
            self.p.comm.today = self.strategy.datetime.date(0)   # ← 把"今天"告诉费用模型
        ...
```

因为 `_getcommission(size, price, pseudoexec)` **拿不到成交日期**，所以需要一个"时钟"把日期喂进来。这样 2023-08-28 前后的印花税就能自动切换。

> **为什么必须自己算**：忽略印花税 + 最低佣金，一个高换手策略的累计收益能虚高好几个百分点；反过来，**最低 5 元对碎单影响极大**——买 1000 元的股票，5 元佣金 = 0.5%，是 0.03% 的 16 倍。

### 9.5 滑点

```python
cerebro.broker.set_slippage_perc(
    perc=0.0002,        # 单边 0.02%
    slip_open=True,     # 开盘价单也滑（默认 True）
    slip_limit=True,    # 限价单也滑（默认 True）
    slip_match=True,    # 滑出当日区间时，裁剪回最高/最低价（默认 True）
    slip_out=False,     # True = 允许滑到当日价格区间之外（默认 False）
)
```

**实测签名**：`set_slippage_perc(self, perc, slip_open=True, slip_limit=True, slip_match=True, slip_out=False)`——注意**后四个参数默认全是 True/False 如上**。

效果：买入成交价 = `price × (1 + perc)`，卖出 = `price × (1 - perc)`。

**数字感受**：单边 0.02% 看起来很小，但一个月换手一次、一年 12 次，光滑点就是 `12 × 2 × 0.02% ≈ 0.48%`；加上佣金双向 0.03%×2 和印花税 0.05%，**一年摩擦成本约 1.7%**。这就是为什么高频策略在 A 股很难做。

### 9.6 做空与现金

backtrader 默认允许"卖空"：`size` 为负就是空头。

```python
self.sell(size=100)              # 没有持仓时 → 开空
self.buy(size=100)               # 有空头时 → 平空
```

| 开关 | 作用 |
|---|---|
| `cerebro.broker.set_shortcash(True/False)` | 做空时现金是增加还是减少（影响可用资金口径） |
| `cerebro.broker.set_checksubmit(True)` | 是否校验保证金/现金是否足够（**默认 True，别关**） |
| `cerebro.broker.add_cash(x)` | 中途出入金 |

> ⚠️ **A 股做空是受限的**：券源有限、要付融券利息、还有保证金比例。backtrader 默认"想空就空、还不收利息"，所以**任何 A 股多空策略回测都会偏乐观**。本仓库的 `bt_a03` 在注释里明确写了这一点。

### 9.7 Broker 开关速查

| 方法 | 用途 |
|---|---|
| `setcash(x)` / `getcash()` / `getvalue()` | 初始资金 / 可用现金 / 总资产 |
| `getposition(data)` | 持仓 |
| `addcommissioninfo(info)` | 自定义费用（9.4） |
| `setcommission(...)` | 简易费用（9.3） |
| `set_slippage_perc/fixed(...)` | 滑点 |
| `set_coc(bool)` / `set_coo(bool)` | 当根收盘/开盘成交（9.2） |
| `set_checksubmit(bool)` | 现金校验（建议保持 True） |
| `set_shortcash(bool)` | 做空现金口径 |

---

## 第 10 章 多标的与组合调仓

### 10.1 多标的的三个难点

1. **节拍**：以谁为准推进？（→ 用 `__CAL__` 日历源，第 4.3 节）
2. **停牌/未上市**：今天能不能交易这只票？（→ `live()`，第 4.3 节）
3. **调仓**：怎么把组合调到"目标权重"？（→ 本节）

### 10.2 `PanelStrategy` 的职责

本仓库把选股类策略的公共部分抽成了一个基类 `btlab.runner.PanelStrategy`，它只做三件事：

| 职责 | 实现 |
|---|---|
| 建立交易日历 | `self.cal = getdatabyname('__CAL__')` |
| 按周/月调度 | `next()` 里判断 `(年,周)` 或 `(年,月)` 是否变化，变了才调 `on_rebalance()` |
| 提供下单工具 | `equal_weight_order()` / `value_weight_order()` / `close_all()` |

子类只需要写一个方法：

```python
class MyPicker(PanelStrategy):
    params = (('topn', 10), ('rebalance', 'monthly'),)

    def on_rebalance(self, cur):          # 只写"选谁"
        scores = {}
        for d in self.tradables:
            if not self.live(d, cur):     # 停牌跳过
                continue
            closes = self.hist_close(d, 61)
            if closes is None:
                continue
            scores[d._name] = closes[-1] / closes[0] - 1.0
        names = sorted(scores, key=scores.get, reverse=True)[:self.p.topn]
        self.equal_weight_order(names, cur)   # 剩下的交给基类
```

### 10.3 等权调仓是怎么实现的（`equal_weight_order`）

它做的事，用自然语言说就是：**先卖掉不在名单里的，再把名单里的每只调到等额，并且股数取整手。**

```
1. 算出每个标的的目标市值 = 可用预算 × 0.98 ÷ 标的个数
2. 先卖：不在名单里的持仓（腾出现金）
3. 再买：名单里的标的，按"目标市值 ÷ 现价"算股数，向下取整到 100 股
4. 已经有持仓的，只调整差额（不多买也不少买）
```

**四个细节（都是踩过坑才加的）：**

| 细节 | 为什么 |
|---|---|
| 预算乘 **0.98** 而不是 1.0 | 次日开盘可能高开，留 2% 缓冲避免"算得刚好、实际被拒单" |
| **先卖后买** | 不卖就没现金买；顺序反了会大量 `Margin` 拒单 |
| 股数 **向下取整到 100** | A 股 1 手 = 100 股，backtrader 不懂这个规则 |
| 预算里**扣掉停牌持仓** | 停牌股今天卖不掉，那部分钱不能算进"可分配预算"，否则会超配 |

### 10.4 和聚宽 `order_target_value` 的差异

| | 聚宽 | 本仓库 |
|---|---|---|
| 接口 | `order_target_value(sec, 市值)` 一行搞定 | 自己算股数 → `self.buy/sell(size=...)` |
| 整手 | 平台自动处理 | 自己 `round_lot()` |
| 停牌 | 平台自动拒单 | 自己 `live()` 判断 |
| 顺序 | 平台内部保证 | 自己"先卖后买" |

**一句话**：聚宽把"整手、停牌、资金校验"都藏在平台里；backtrader 是库，这些必须你自己写。**理解了第 10.3 节，你就理解了"平台"到底替你做了什么。**

---

## 第 11 章 Cerebro：总控

### 11.1 构造参数

```python
cerebro = bt.Cerebro(
    preload=True,      # 预载数据（默认 True，快）；内存紧张时设 False
    runonce=True,      # 向量化模式（默认 True，最快）；调试时设 False 更接近逐根语义
    stdstats=True,     # 是否加默认观察器（本项目设 False）
    maxcpus=None,      # 参数优化时用多核
    optreturn=True,    # 优化时返回轻量结果
)
```

### 11.2 `add*` 全家桶：每个什么时候用

| 方法 | 作用 | 什么时候用 |
|---|---|---|
| `adddata(data, name=...)` | 加一个数据源 | 必用 |
| `addstrategy(S, **params)` | 挂策略 | 必用 |
| `addanalyzer(A, _name=...)` | 挂分析器 | 想统计回撤/夏普/交易明细时 |
| `addobserver(O)` | 挂观察器 | 想画图看现金/市值时 |
| `addsizer(S)` | 挂仓位管理器 | 想让引擎决定股数（本项目不用） |
| `addwriter(W, csv=True, out=...)` | 写运行日志到文件 | 调试、数据量大时 |
| `add_timer(when, ...)` | 定时回调 | 需要"每天 14:50 执行"这类逻辑 |
| `resampledata(...)` / `replaydata(...)` | 周期转换 | 日线转周线（第 4.5 节） |
| `optstrategy(S, **ranges)` | 参数优化 | 第 12 章 |
| `addindicator(I)` | 加一个"独立"指标（不属于策略） | 只想画图、不参与交易时 |
| `addcalendar(cal)` | 换交易日历 | 跨市场（A股+港股）时 |

### 11.3 `run()` 的返回值

```python
results = cerebro.run()        # 返回 list，每个元素是一个策略实例
strat = results[0]             # 单策略时就用第一个
```

| 参数 | 说明 |
|---|---|
| `run()` | 正常回测 |
| `run(maxcpus=4)` | 配合 `optstrategy` 做多进程优化 |
| `run(runonce=False)` | 强制逐根模式（调试时更容易定位问题） |
| `runstop()` | 在策略内部请求提前结束 |

---

## 第 12 章 参数优化

```python
cerebro.optstrategy(MyStrategy, fast=range(5, 21, 5), slow=range(20, 61, 10))
results = cerebro.run(maxcpus=4)

for r in results:                 # 每个组合一个策略实例
    strat = r[0]
    print(strat.p.fast, strat.p.slow, strat.broker.getvalue())
```

| 细节 | 说明 |
|---|---|
| `optstrategy` 会跑参数的**笛卡尔积** | 上面例子 = 4 × 5 = 20 次回测 |
| `maxcpus=1` | 单进程（好调试）；`>1` 多进程（快，但数据要能 pickle） |
| `optreturn=True`（默认） | 返回轻量对象；需要完整策略对象时设 `False` |

> ⚠️ **参数优化最容易自欺欺人**：在长历史上挑"最优参数"，往往只是拟合了那段历史的噪声。**判断标准不是"最优参数的收益有多高"，而是"参数在邻域内是否稳定"**——把 fast 从 5 改到 6、收益就崩掉，那多半是过拟合。
>
> 本仓库的策略都留了参数块，但**教学时不鼓励暴力搜参**。
---

## 第 13 章 聚宽 API ↔ backtrader 对照

**如果你已经会聚宽，这一章能让你在半小时内看懂本仓库的 backtrader 代码。** 反过来，如果你先学的是 backtrader，也能借此理解聚宽。

| 概念 | 聚宽（JoinQuant） | backtrader | 差异要点 |
|---|---|---|---|
| 策略入口 | `def initialize(context)` | `class S(bt.Strategy)` | 聚宽是"一个全局函数 + 全局变量"，backtrader 是"一个类 + 实例属性" |
| 每根 K 线 | `handle_data(context, data)` / `run_daily(func)` | `def next(self)` | 名字不同，作用相同 |
| 定时执行 | `run_daily/run_weekly/run_monthly` | 在 `next()` 里判断日期变化 | **backtrader 没有内置调度**，要自己写（第 10.2 节） |
| 全局参数 | `g.xxx = 5` | `params = (('xxx', 5),)` → `self.p.xxx` | 用 params 才能被 `optstrategy` 优化 |
| 基准 | `set_benchmark('000300.XSHG')` | 自己加载指数 + 自己对比 | backtrader 不会自动帮你算超额收益 |
| 手续费 | `set_order_cost(OrderCost(...))` | `addcommissioninfo(...)` | 语义相近，写法不同 |
| 滑点 | `set_slippage(FixedSlippage(0.02))` | `set_slippage_perc(0.0002)` | ⚠️ 聚宽用 0.02 表示 0.02%；backtrader 要写小数 0.0002 |
| 历史行情 | `attribute_history(sec, 20, '1d', 'close')` | `self.data.close.get(size=20)` | 返回类型不同（DataFrame/Series vs array） |
| 成分股 | `get_index_stocks('000300.XSHG')` | `btlab.datasource.load_index_members()` | 聚宽能取**历史**成分股，免费源只有**当前**成分股（幸存者偏差） |
| 财务数据 | `get_fundamentals(query(...))` | `btlab.runner.value_panel()/roe_panel()` | 免费源只给报告期，需自己模拟公告滞后 |
| 按股数下单 | `order(sec, 100)` | `self.buy(size=100)` | —— |
| 目标市值 | `order_target_value(sec, v)` | `self.order_target_value(target=v)` | ⚠️ backtrader 不会整手，A 股要自己取整 |
| 目标比例 | `order_target_percent(sec, 0.5)` | `self.order_target_percent(target=0.5)` | 同上 |
| 清仓 | `order_target_value(sec, 0)` | `self.close()` | —— |
| 持仓 | `context.portfolio.positions[sec]` | `self.getposition(data)` | backtrader 的 `self.position` 只对第一个数据源 |
| 可用现金 | `context.portfolio.available_cash` | `self.broker.getcash()` | —— |
| 总资产 | `context.portfolio.total_value` | `self.broker.getvalue()` | —— |
| 日志 | `log.info(...)` | `print(...)` | backtrader 没有日志系统，用 print 或 Writer |
| 回测区间 | 平台界面设置 | `load_daily(start=..., end=...)` | backtrader 直接在数据层切 |
| 初始资金 | 平台界面设置 | `cerebro.broker.setcash(...)` | —— |
| 运行 | 云端点"编译运行" | 本机 `python script.py` | backtrader 无额度限制、无账号 |

> **一句话总结**：**思路能平移，"触发方式"和"下单口径"必须重写。**
> 聚宽的 `run_monthly` 在 backtrader 里要自己写成"月份变化才调仓"；聚宽的 `order_target_value` 在 backtrader 里要注意整手取整。

---

## 第 14 章 本仓库 btlab 工具层

`btlab` **不是自研回测框架**：撮合、账务、盈亏 100% 由 backtrader 负责。它只是把 20 个策略共用的"脏活"收拢成 3 个模块。

### 14.1 `btlab.datasource` —— 免费长周期数据

| 函数 | 作用 | 备注 |
|---|---|---|
| `load_daily(code, start, end, adjust='qfq', kind=None)` | 取单标的日线（自动识别股票/ETF/指数） | 有磁盘缓存；`adjust` 支持 `'qfq'/'hfq'/''` |
| `load_many(codes, ...)` | 批量取，返回 `{代码: DataFrame}` | 失败的会跳过并提示 |
| `load_universe(codes, start, end, ...)` | 批量取 + 剔除"上市太晚"的标的 | 选股类策略用它建股票池 |
| `load_index_members(index_code)` | 指数成分股列表 | ⚠️ 只有**当前**成分股 |
| `load_stock_value(code)` | 个股每日估值（PE/PB/市值） | 东财，约 2018 年起 |
| `load_financial_indicator(code, start_year)` | 财务指标（ROE/净利润增长率…） | 新浪，按报告期 |
| `roe_series(code)` | 便捷取 ROE 序列 | —— |
| `sw_industries()` / `load_sw_index(code)` / `load_sw_members(code)` | 申万行业列表 / 行业指数 / 行业成分股 | 行业轮动与行业中性化用 |
| `load_index_pe(symbol)` | 指数 PE（月度） | 乐咕乐股，用于"市场温度" |
| `load_bond_universe()` / `listed_bonds()` / `load_bond_daily(code)` | 可转债列表 / 候选池 / 转债日线 | 见 `bt_a05` 的取舍说明 |
| `normalize_code()` / `classify()` | 代码归一化与类型判定 | `sz000001`=平安银行，`sh000001`=上证指数 |
| `clear_cache(prefix)` | 清缓存 | `data_cache/` 下按前缀删 |

### 14.2 `btlab.runner` —— 回测样板

| 函数/类 | 作用 |
|---|---|
| `build_cerebro(cash, commission, stamp_duty, min_comm, slippage)` | 建好一个配好 A 股费用与滑点的 Cerebro |
| `run_strategy(strategy_cls, data, cash, benchmark, ..., plot_path=...)` | **一键回测**：跑完自动出绩效报告、可选画净值图 |
| `add_feed` / `add_feeds` | 把 DataFrame 加进 Cerebro（支持 dict 起名） |
| `PanelStrategy` | 多标的调仓骨架（日历/调度/下单工具，见第 10 章） |
| `AStockCommission` | A 股费用模型（见 9.4） |
| `NavRecorder` | 记录每日净值的 Analyzer（也负责给费用模型喂日期） |
| `round_lot(size, lot=100)` | 取整手（按绝对值向下取整） |
| `asof(panel, cur)` | 取"不晚于 cur 的最近一期"数据（**逐列前向填充**，防未来函数） |
| `value_panel( codes, field)` / `roe_panel(codes, lag_days)` / `growth_panel(...)` | 把多只股票的基本面拼成面板（index=日期，columns=代码） |
| `event_calendar(codes, ...)` | 业绩事件日历（报告期 + 滞后天数近似公告日） |
| `industry_map(codes)` | 股票 → 申万一级行业映射 |

**`run_strategy` 的返回值**（dict）：

```python
res = run_strategy(...)
res['metrics']         # 绩效指标（含 drawdown_series）
res['nav']             # 每日净值 Series
res['benchmark_ret']   # 基准区间收益
res['trade_count']     # 成交笔数
res['turnover']        # 累计换手率
res['strategy']        # 策略实例（可以继续取 analyzers）
```

### 14.3 `btlab.metrics` —— 绩效与绘图

| 函数 | 作用 |
|---|---|
| `perf_from_nav(nav)` | 由每日净值算累计/年化/最大回撤/夏普/波动率/日胜率 |
| `format_report(metrics, ...)` | 把指标排版成终端里那份"绩效报告" |
| `plot_equity(nav, benchmark_nav, save_path, ...)` | 画"净值 + 回撤"上下两张图 |

**本仓库的绩效口径（和聚宽/研报常用口径一致）：**

| 指标 | 公式/口径 |
|---|---|
| 累计收益率 | `期末/期初 - 1` |
| 年化收益率 | `(期末/期初)^(1/年数) - 1`，年数 = 交易日 / 252 |
| 最大回撤 | `min(净值 / 历史最高净值 - 1)` |
| 夏普比率 | `日收益均值 / 日收益标准差 × √252`（无风险利率按 0） |
| 年化波动率 | `日收益标准差 × √252` |
| 日胜率 | **只统计有变化的日子**（排除 0 收益） |

---

## 第 15 章 最常见的坑（含实测证据）

| # | 症状 | 真正的原因 | 怎么改 |
|---|---|---|---|
| 1 | 回测收益高得离谱 | 用了未来数据（正索引、`get(ago=1)`、`[-1]` 绕圈） | 只用 `[0]` 和负索引；`prenext` 里别读 `[-1]` |
| 2 | 明明下了单却没买 | 现金不足 → 订单状态 `Margin` | 写 `notify_order` 打印状态；留 2% 缓冲 |
| 3 | 买了 137 股这种零头 | backtrader 不懂 A 股整手 | `round_lot(size)` 后再下单 |
| 4 | 第 1 根就算出结果 / 数值诡异 | 在 `prenext()` 里读了 `[-1]`，绕到了数据集末尾 | `prenext()` 里不读数据；或自己判 `len()` |
| 5 | 取"最近 3 根"时报类型错 | `get(size=n)` 返回 **array** 不是 list | 需要 list 就 `list(...)` |
| 6 | 取"昨天"却拿到明天 | 写成 `get(ago=1)` | 用 `get(ago=-1)` 或 `close[-1]` |
| 7 | `self.macd.histo[0]` 报错 | histo 不在 MACD 上 | 用 `bt.ind.MACDHisto()` |
| 8 | 指标一直是 nan | 数据根数 < `minperiod` | 正常现象；用 `prenext()` 处理等待期 |
| 9 | `SMA()` 出来是 30 日线 | 默认 `period=30` | 永远显式写 `period=` |
| 10 | 多标的时 `next()` 次数不对 | 以主数据源为节拍，停牌/上市时间错位 | 用 `__CAL__` 日历源（第 4.3 节） |
| 11 | SharpeRatio 返回 `None` | 净值无波动 / 数据不足 / timeframe 不匹配 | 自己算（第 7.2 节） |
| 12 | `cerebro.plot()` 卡死或弹不出来 | 交互式后端问题 | 批量跑时用 `Agg` 后端存图（本项目 `plot_equity` 已这么做） |
| 13 | 多进程优化跑不动 | 数据不能 pickle | `maxcpus=1` |
| 14 | 现金变成负数 | 关了保证金校验，或做空现金口径 | 保持 `set_checksubmit(True)`；注意 `set_shortcash` |
| 15 | 结果每次跑都不一样 | 用了随机数没固定种子 | 设 `random_state`（如 `RandomForestClassifier(random_state=42)`） |

---

## 第 16 章 完整可运行模板 + 输出解读

```python
# -*- coding: utf-8 -*-
"""双均线 Demo：日线收盘出信号 → 次日开盘成交，含 A 股费用与滑点。"""
import os

import backtrader as bt

from btlab.datasource import load_daily
from btlab.runner import run_strategy, round_lot

START, END = '2015-01-01', None
CASH = 1_000_000
SYMBOL, BENCHMARK = '510300', '000300'      # 沪深300ETF / 沪深300指数


class Demo(bt.Strategy):
    params = (('fast', 5), ('slow', 20), ('stake', 0.95))

    def __init__(self):
        self.ma_fast = bt.ind.SMA(self.data.close, period=self.p.fast)
        self.ma_slow = bt.ind.SMA(self.data.close, period=self.p.slow)
        self.cross = bt.ind.CrossOver(self.ma_fast, self.ma_slow)

    def next(self):
        if not self.position:
            if self.cross[0] > 0:                       # 金叉
                size = round_lot(self.broker.getcash() * self.p.stake
                                 / self.data.close[0])
                if size > 0:
                    self.buy(size=size)
        elif self.cross[0] < 0:                         # 死叉
            self.close()

    def notify_order(self, order):
        if order.status in (order.Submitted, order.Accepted):
            return
        if order.status == order.Completed:
            side = '买入' if order.isbuy() else '卖出'
            print(f'{self.datetime.date(0)} {side} '
                  f'{order.executed.size} 股 @ {order.executed.price:.3f} '
                  f'手续费 {order.executed.comm:.2f}')
        elif order.status in (order.Canceled, order.Margin, order.Rejected):
            print(f'{self.datetime.date(0)} 未成交：{order.getstatusname()}')


if __name__ == '__main__':
    df = load_daily(SYMBOL, start=START, end=END)
    print(f'区间 {df.index[0].date()} ~ {df.index[-1].date()}，共 {len(df)} 个交易日')

    run_strategy(
        Demo, {SYMBOL: df}, cash=CASH, benchmark=BENCHMARK,
        title='backtrader Demo（沪深300ETF·双均线）',
        plot_path=os.path.join('results', 'demo_result.png'),
    )
```

**这份报告怎么读**（终端里会打印成这样）：

```
初始资金        : 1,000,000 元
期末资产        : 1,234,567 元
累计收益率      :    23.46%
年化收益率      :     3.12%
基准累计收益率  :    72.62%
超额收益(vs基准):   -49.16%
最大回撤        :   -39.24%
夏普比率        :     0.10
年化波动率      :    18.42%
日胜率          :    47.33%
总成交笔数      : 224
累计换手率      :  1150.00%  (累计成交额/初始资金)
回测区间        : 2013-01-04 ~ 2026-09-30（3300 个交易日）
```

| 字段 | 怎么理解 | 该警惕什么 |
|---|---|---|
| 累计收益率 | 总共赚了多少 | 只看它会被"长期复利"骗；要看年化 |
| 年化收益率 | 折算成每年 | 和基准对比才有意义 |
| **超额收益** | 策略 - 基准 | ⚠️ **双均线在这段历史上跑输基准是常态**——趋势策略靠的是"少数大行情 + 严格止损" |
| 最大回撤 | 从最高点跌下来的最惨幅度 | **决定你能不能拿得住**（比收益更重要） |
| 夏普比率 | 每单位波动的收益 | < 0.5 通常说明"承担了很大波动却赚得不多" |
| 换手率 | 累计成交额 / 初始资金 | 越高，手续费+滑点吃掉的越多 |
| 成交笔数 | 一共成交多少笔 | 笔数异常多 → 检查是不是在反复"为凑整手"调仓 |

> **最重要的一句**：**回测数字不是用来判断"这个策略能不能赚钱"的**。它是用来回答"如果我按这个规则做，历史上会经历什么"——尤其是**最惨的时候要扛多大的回撤**。

---

## 第 17 章 自测题（不写代码也能做）

> 答案是开放式的，能用自己的话说清楚就算过关。做完这一章，说明你已经真的读懂了。

1. 为什么 `next()` 里下的单，不会在本根 K 线成交？如果改成"本根收盘成交"，会带来什么风险？
2. `close[-1]` 和 `close[1]` 分别是什么？为什么说第 1 根上的 `close[-1]` 比 `close[1]` 更危险？
3. `get(size=5)` 返回什么类型？`get(ago=1)` 和 `get(ago=-1)` 哪个是"昨天"？
4. 策略里同时用了 `SMA(20)` 和 `SMA(60)`，`next()` 会从第几根开始被调用？为什么？
5. `self.position` 和 `self.getposition(d)` 有什么区别？什么时候必须用后者？
6. 为什么 A 股回测必须自己算股数，不能用 `order_target_percent()` 的实现？
7. `AStockCommission` 里 `min_comm` 为什么只兜底"佣金"、不兜底"佣金+印花税"？
8. 为什么回测里"下单成功"不等于"买入成功"？你会怎么发现这件事？
9. 多标的回测时，为什么需要一个 `__CAL__` 日历源？不用会出什么问题？
10. 内置 `SharpeRatio` 返回 `None`，可能有哪些原因？本项目为什么不直接用它？
11. "双低转债"为什么在本地免费数据上做不了？（提示：数据可得性 → 未来函数）
12. 累计换手率 2400% 意味着什么？它对收益的影响有多大？

---

## 第 18 章 学习路径

```
第 1 步  读第 0 章（心智模型）+ 第 1 章（最小骨架）
            └─ 目标：说清楚"__init__ 声明、next 下单、次日开盘成交"这三件事
   │
第 2 步  精读第 2 章（Line 与索引）+ 第 3 章（生命周期）
            └─ 目标：能一眼看出代码里有没有未来函数
   │
第 3 步  读第 5 章（Strategy）+ 第 6 章（Indicator）
            └─ 目标：能自己写一个"双均线"策略
   │
第 4 步  读第 9 章（费用/滑点/成交时点）+ 第 7 章（统计）
            └─ 目标：能给策略配上真实的 A 股成本，并正确解读绩效
   │
第 5 步  读第 10 章（多标的调仓）
            └─ 目标：能写选股类策略，理解"整手/停牌/先卖后买"
   │
第 6 步  读 docs/backtrader/beginner/ 的 10 篇 → advanced/ 的 10 篇
            └─ 每篇对照 strategies/backtrader/ 下同名 .py 一起看
```

**配套文档**：

- 策略逐篇详解 → `docs/backtrader/beginner/`、`docs/backtrader/advanced/`
- 聚宽版对照 → `docs/joinquant/beginner/`、`docs/joinquant/advanced/`
- 环境与运行（装依赖、跑第一个策略）→ `docs/本地回测使用指南.md`
- 聚宽函数全解 → `docs/learning/3.聚宽函数详解/get_functions.md`

**遇到问题时的排查顺序**：

```
1. 先看第 15 章"最常见的坑" —— 80% 的问题都在里面
2. 打开 notify_order() 打印订单状态 —— 解决"为什么没成交"
3. 在 next() 里 print(len(self), self.datetime.date(0)) —— 解决"为什么次数不对"
4. 用 cerebro.run(runonce=False) 逐根跑 —— 解决"定位不到哪一根出错"
```