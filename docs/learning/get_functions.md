# 聚宽（JoinQuant）常见函数详解 —— get_ 系列数据获取函数

> 本文档系统整理聚宽框架下 `get_` 系列数据获取函数，是量化策略与平台数据交互的核心入口。
> 每个函数均按「用途说明 → 核心参数 → 返回值 → 基本用法 → 简单例子 → 全部属性」展开，方便初学与速查。

---

## 目录

- [一、标的池获取](#一标的池获取)
  - [get_all_securities](#1-get_all_securities)
  - [get_index_stocks](#2-get_index_stocks)
  - [get_industry_stocks](#3-get_industry_stocks)
  - [get_concept_stocks](#4-get_concept_stocks)
- [二、行情数据获取](#二行情数据获取)
  - [get_price](#5-get_price)
  - [attribute_history](#6-attribute_history)
  - [history](#7-history)
  - [get_bars](#8-get_bars)
  - [get_current_data](#9-get_current_data)
- [三、基本面与因子数据获取](#三基本面与因子数据获取)
  - [get_fundamentals](#10-get_fundamentals)
  - [get_factor_values](#11-get_factor_values)
- [四、实时/单只标的信息获取](#四实时单只标的信息获取)
  - [get_security_info](#12-get_security_info)
  - [get_money_flow](#13-get_money_flow)

---

## 一、标的池获取

这类函数回答「有哪些股票可以选」，是选股策略的第一步——先圈定候选股票池，再做后续的因子计算与排序。

### 1. get_all_securities

**用途**：获取平台支持的全部证券标的（股票、基金、指数、期货等）。这是构建「全市场股票池」最常用的函数。

**核心参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `types` | list | 否 | 标的类型列表，如 `['stock']`、`['fund']`、`['index']`。默认返回全部类型 |
| `date` | str / datetime / date | 否 | 查询日期。默认取当天（回测中为当前回测日期） |

**返回值**：一个 `DataFrame`，**索引是证券代码**（如 `000001.XSHE`），包含每个标的的字段信息（见下方「全部属性」）。

**基本用法**

```python
from jqdata import *

# 获取某日全部 A 股股票
stocks = get_all_securities(types=['stock'], date='2023-12-31')

# 取所有股票代码（.index 就是代码列）
codes = stocks.index.tolist()
```

**简单例子**

```python
def initialize(context):
    pass

def handle_data(context, data):
    # 每天获取全市场股票，过滤后取前 20 只（示例）
    all_stocks = get_all_securities(types=['stock'], date=context.current_dt.date())
    print('全市场股票数量:', len(all_stocks))
```

**返回 DataFrame 的全部属性（列名）**

| 字段 | 说明 |
|------|------|
| `display_name` | 证券中文名称，如「平安银行」 |
| `name` | 证券代码缩写（拼音字母），如 `PAYH` |
| `start_date` | 上市日期（datetime.date） |
| `end_date` | 退市日期（datetime.date），未退市为 `2200-01-01` |
| `type` | 证券类型，如 `stock`、`fund`、`index` |

> 注意：`get_all_securities` 返回的股票**不含退市过滤**，若需剔除退市股，应配合 `end_date` 或 `get_security_info` 判断。用 `date` 参数传入历史日期，可避免「未来函数」——即只使用当时已上市的股票。

---

### 2. get_index_stocks

**用途**：获取指定指数在某交易日的成分股列表。是「以指数成分股为股票池」策略（如沪深300增强）的核心入口。

**核心参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `index_symbol` | str | 是 | 指数代码，如 `000300.XSHG`（沪深300）、`000905.XSHG`（中证500） |
| `date` | str / datetime / date | 否 | 查询日期，默认当天 |

**返回值**：一个 `list`，元素为股票代码字符串，如 `['000001.XSHE', '600000.XSHG', ...]`。

**基本用法**

```python
from jqdata import *

# 获取沪深300在 2024-01-01 的成分股
hs300 = get_index_stocks('000300.XSHG', '2024-01-01')
print(hs300[:5])   # 打印前 5 只
```

**简单例子**

```python
def initialize(context):
    # 每月第一个交易日换仓
    run_monthly(rebalance, 1, time='09:30')

def rebalance(context):
    # 沪深300 成分股作为股票池
    pool = get_index_stocks('000300.XSHG', context.current_dt.date())
    print('沪深300 成分股数量:', len(pool))
```

**常见指数代码速查**

| 指数 | 代码 |
|------|------|
| 沪深300 | `000300.XSHG` |
| 中证500 | `000905.XSHG` |
| 中证1000 | `000852.XSHG` |
| 上证50 | `000016.XSHG` |
| 创业板指 | `399006.XSHE` |

> 说明：`get_index_stocks` 返回的是**纯代码列表**，不含市值、行业等额外字段；若需这些信息，需再调用 `get_fundamentals` 或 `get_factor_values`。

---

### 3. get_industry_stocks

**用途**：获取指定行业在某交易日的成分股列表。用于「行业轮动」「行业中性化」等策略。

**核心参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `industry_code` | str | 是 | 行业代码，如 `851921`（申万一级行业）、`J66`（聚宽行业） |
| `date` | str / datetime / date | 否 | 查询日期，默认当天 |

**返回值**：一个 `list`，元素为股票代码字符串。

**基本用法**

```python
from jqdata import *

# 获取申万一级行业「银行」的股票（851911 为银行行业代码示例）
bank_stocks = get_industry_stocks('851911', '2024-01-01')
print(bank_stocks)
```

**简单例子**

```python
def rebalance(context):
    # 只买入银行行业股票
    pool = get_industry_stocks('851911', context.current_dt.date())
    # ... 后续对 pool 做因子选股
```

> 说明：行业代码体系多样（申万、聚宽、证监会），需先通过 `get_industries(name='sw_l1')` 查询行业代码，或通过 `get_industry(security, date)` 反查个股所属行业。

---

### 4. get_concept_stocks

**用途**：获取指定概念板块在某交易日的成分股列表。用于「概念主题投资」类策略（如新能源、人工智能、芯片等热门概念）。

**核心参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `concept_code` | str | 是 | 概念代码，如 `SC0001` |
| `date` | str / datetime / date | 否 | 查询日期，默认当天 |

**返回值**：一个 `list`，元素为股票代码字符串。

**基本用法**

```python
from jqdata import *

# 获取某概念板块股票（SC0001 为示例概念代码）
concept_stocks = get_concept_stocks('SC0001', '2024-01-01')
print(concept_stocks)
```

**简单例子**

```python
def rebalance(context):
    # 获取「人工智能」概念股作为候选池
    pool = get_concept_stocks('SC0101', context.current_dt.date())
    # ... 后续对 pool 做选股
```

> 说明：概念代码需先通过 `get_concepts()` 查询。概念板块的成分股变动比行业更频繁，回测时用 `date` 参数传入历史日期能避免未来函数。

---

## 二、行情数据获取

这类函数回答「价格走势如何」，是计算技术指标、收益率、动量的基础。

### 5. get_price

**用途**：获取指定时间段的历史行情数据，支持多标的、多字段、多频率。是通用性最强的行情获取函数，研究环境和回测环境均可用。

**核心参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `security` | str / list | 是 | 标的代码或代码列表 |
| `start_date` | str / datetime / date | 否 | 开始日期（含） |
| `end_date` | str / datetime / date | 否 | 结束日期（含） |
| `frequency` | str | 否 | 频率，如 `'daily'`（日线）、`'minute'`（分钟线）、`'1m'`/`'5m'` 等 |
| `fields` | list / str | 否 | 返回字段，如 `['open','close','high','low','volume']` |
| `fq` | str | 否 | 复权方式，`'pre'`（前复权）、`'post'`（后复权）、`None`（不复权） |
| `skip_paused` | bool | 否 | 是否跳过停牌数据，默认 `False` |
| `panel` | bool | 否 | 是否返回 panel 结构（已废弃，保持默认即可） |

**返回值**：一个 `DataFrame`。单标的返回以时间为索引的 DataFrame；多标的返回 MultiIndex（标的 + 时间）的 DataFrame。

**基本用法**

```python
from jqdata import *

# 获取平安银行 2024 全年日线收盘价
df = get_price('000001.XSHE', '2024-01-01', '2024-12-31', frequency='daily', fields=['close'], fq='pre')
print(df.head())
```

**简单例子**

```python
def initialize(context):
    g.security = '000001.XSHE'

def handle_data(context, data):
    # 取最近 60 个交易日的收盘价
    df = get_price(g.security, count=60, frequency='daily', fields=['close'])
    closes = df['close']
    ma = closes.mean()
    print('60日均线:', ma)
```

**返回 DataFrame 的常用字段（fields 可选值）**

| 字段 | 说明 |
|------|------|
| `open` | 开盘价 |
| `close` | 收盘价 |
| `high` | 最高价 |
| `low` | 最低价 |
| `volume` | 成交量（股） |
| `money` | 成交额（元） |
| `factor` | 复权因子 |
| `high_limit` | 涨停价 |
| `low_limit` | 跌停价 |
| `avg` | 均价 |
| `pre_close` | 昨收价 |
| `paused` | 是否停牌（布尔） |

> 说明：`get_price` 既支持 `start_date/end_date` 指定时间段，也支持 `count` 参数指定「最近 N 根 bar」。两者二选一。复权方式 `fq='pre'`（前复权）最常用于技术指标计算，可消除除权除息造成的价格跳空。

---

### 6. attribute_history

**用途**：回测专用。获取**单个标的**过去 `count` 个时间单位的行情数据。与 `get_price` 的区别在于它基于「当前回测时点往前数 N 根」，天然避免未来函数。

**核心参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `security` | str | 是 | 单个标的代码 |
| `count` | int | 是 | 往回取多少个时间单位（bar 数） |
| `unit` | str | 是 | 时间单位，如 `'1d'`（日）、`'1m'`（分钟）、`'1w'`（周） |
| `fields` | list / str | 是 | 字段列表，如 `['open','close','high','low','volume']` |
| `skip_paused` | bool | 否 | 是否跳过停牌，默认 `True` |
| `df` | bool | 否 | 是否返回 DataFrame，`True` 返回 DataFrame，`False` 返回 dict |
| `include_now` | bool | 否 | 是否包含当前 bar，默认 `False` |

**返回值**：默认（`df=True`）返回 `DataFrame`，以时间为索引，列为 fields 指定字段。

**基本用法**

```python
from jqdata import *

def handle_data(context, data):
    # 取平安银行最近 20 个交易日的收盘价
    df = attribute_history('000001.XSHE', 20, '1d', ['close'], df=True)
    closes = df['close']
    print(closes)
```

**简单例子（双均线）**

```python
def trade(context):
    security = '000300.XSHG'
    # 需要 long+1 根来保证能算出长短两根均线
    closes = attribute_history(security, 60 + 1, '1d', 'close', df=True)['close']
    ma_short = closes[-5:].mean()    # 短均线（5日）
    ma_long = closes[-60:].mean()    # 长均线（60日）
    if ma_short > ma_long:
        order_target(security, 100)   # 金叉买入
```

**说明**

- `attribute_history` 只能传**单个标的**，批量多标的请用 `history`。
- 它返回的数据是「已经收盘的完整 bar」，即不包含当根未走完的 K 线，因此回测中用它算指标是安全的。

---

### 7. history

**用途**：回测专用。获取**多个标的**过去 `count` 个时间单位的**单一字段**行情数据。是 `attribute_history` 的批量版。

**核心参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `security` | list | 是 | 标的代码列表 |
| `count` | int | 是 | 往回取多少个时间单位 |
| `unit` | str | 是 | 时间单位，如 `'1d'` |
| `field` | str | 是 | 单一字段，如 `'close'`、`'open'`、`'volume'` |
| `skip_paused` | bool | 否 | 是否跳过停牌，默认 `True` |
| `df` | bool | 否 | 是否返回 DataFrame，默认 `True` |
| `include_now` | bool | 否 | 是否包含当前 bar，默认 `False` |

**返回值**：默认返回 `DataFrame`，索引为时间，列为各标的代码（列名是代码），值为该字段的数据。

**基本用法**

```python
from jqdata import *

def handle_data(context, data):
    codes = ['000001.XSHE', '600000.XSHG', '600519.XSHG']
    # 取这三只股票最近 20 日收盘价
    df = history(codes, 20, '1d', 'close', df=True)
    print(df.head())
```

**简单例子（批量算动量）**

```python
def rebalance(context):
    pool = get_index_stocks('000300.XSHG')
    # 一次性取所有成分股最近 60 日收盘价
    close_df = history(pool, 60, '1d', 'close', df=True)
    # 计算每只股票的 60 日涨幅（动量）
    momentum = close_df.iloc[-1] / close_df.iloc[0] - 1
    momentum = momentum.sort_values(ascending=False)
    target = momentum.index.tolist()[:30]
```

> 说明：`history` 只支持**单一字段**（`field` 而非 `fields`）。若需多字段批量数据，可用 `get_price` 配合多标的列表。

---

### 8. get_bars

**用途**：获取 bar 线数据。与 `get_price` 的「移动窗口」逻辑不同，`get_bars` 更侧重于按 `count` 取最近的 bar，适合分钟级、日内策略。

**核心参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `security` | str | 是 | 单个标的代码 |
| `count` | int | 是 | bar 数量 |
| `unit` | str | 是 | 时间单位，如 `'1d'`、`'1m'`、`'5m'` |
| `fields` | list / str | 否 | 字段列表，如 `['close','volume']` |
| `include_now` | bool | 否 | 是否包含当前 bar，默认 `False` |
| `end_dt` | datetime | 否 | 结束时间 |
| `df` | bool | 否 | 是否返回 DataFrame，默认 `True` |

**返回值**：默认返回 `DataFrame`，以时间为索引。

**基本用法**

```python
from jqdata import *

def handle_data(context, data):
    # 取最近 20 根日线的收盘价与成交量
    df = get_bars('000001.XSHE', 20, '1d', fields=['close', 'volume'])
    print(df)
```

**简单例子**

```python
def handle_data(context, data):
    # 分钟级：取最近 30 分钟的数据
    df = get_bars('000001.XSHE', 30, '1m', fields=['close', 'high', 'low'])
    # 计算 30 分钟内的最高价
    recent_high = df['high'].max()
    print('近30分钟最高价:', recent_high)
```

> 说明：`get_bars` 与 `attribute_history` 功能接近，但 `get_bars` 支持 `end_dt` 指定结束时间，且可用于分钟线。日内策略（如择时、T+0）更常用 `get_bars`。

---

### 9. get_current_data

**用途**：获取**当前时刻**（回测/模拟中为当前单位时间）的实时数据对象。这是过滤「停牌、ST、涨跌停、当日无行情」的核心函数。

**核心参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| 无（可选 `security_list`） | - | 否 | 某些版本支持传入标的列表，但通常不传，按需获取即可 |

**返回值**：一个 `dict`，key 是股票代码，value 是该股票的实时数据对象（拥有下方「全部属性」）。

**基本用法**

```python
from jqdata import *

def filter_stocks(stock_list):
    current_data = get_current_data()
    result = []
    for s in stock_list:
        d = current_data[s]
        if d.is_st:          # 过滤 ST
            continue
        if d.paused:         # 过滤停牌
            continue
        result.append(s)
    return result
```

**简单例子（完整过滤）**

```python
def filter_stocks(context, stock_list):
    current_data = get_current_data()
    result = []
    for s in stock_list:
        d = current_data[s]
        if d.is_st or '退' in d.name:   # ST 或退市
            continue
        if d.paused:                     # 停牌
            continue
        if d.day_open <= 0:              # 当日无行情
            continue
        if d.high_limit <= d.last_price: # 涨停（买不进）
            continue
        if d.low_limit >= d.last_price:  # 跌停（卖不出）
            continue
        result.append(s)
    return result
```

**返回值对象的全部属性**

| 属性 | 类型 | 说明 |
|------|------|------|
| `last_price` | float | 最新价（09:30 前为昨日收盘价） |
| `high_limit` | float | 涨停价 |
| `low_limit` | float | 跌停价 |
| `paused` | bool | 是否停牌/未上市/退市（`True` 表示停牌） |
| `is_st` | bool | 是否为 ST（含 *ST） |
| `day_open` | float | 当天开盘价（约 09:27 后可获取） |
| `name` | str | 股票当前名称（可判断退市，如「××退」） |
| `industry_code` | str | 所属行业代码 |
| `unit` | int | 最小交易单位（手） |

> 重要提醒：
> 1. 返回的 dict 是**按需获取**的，初始为空，只有访问 `current_data[code]` 时才会真正取数，这是性能优化设计。
> 2. 结果**只在当天有效**，不要存起来隔天再用（否则会产生未来函数或脏数据）。

---

## 三、基本面与因子数据获取

这类函数回答「公司财务/估值如何」，是价值投资、质量投资、多因子选股的数据来源。

### 10. get_fundamentals

**用途**：执行 `query()` 查询，获取财务/估值数据。是基本面选股（PE、PB、ROE 等）的核心函数。

**核心参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query_object` | Query | 是 | 由 `query()` 构造的查询对象 |
| `date` | str / datetime / date | 否 | 查询日期（查该日期最近已披露的数据），与 `statDate` 二选一 |
| `statDate` | str | 否 | 按财报期查询，如 `'2023'`（年报）、`'2023q3'`（三季报），与 `date` 二选一 |

**返回值**：一个 `DataFrame`，**索引默认是 0,1,2,... 数字序号**（并非股票代码）。

**基本用法**

```python
from jqdata import *

# 查询沪深300 成分股的市盈率
q = query(
    valuation.code,
    valuation.pe_ratio,
    valuation.pb_ratio
).filter(
    valuation.code.in_(get_index_stocks('000300.XSHG'))
)
df = get_fundamentals(q, date='2024-01-01')
df = df.set_index('code')   # 关键：把索引设为股票代码
print(df.head())
```

**简单例子（低估值选股）**

```python
def rebalance(context):
    pool = get_all_securities(['stock'], date=context.current_dt.date()).index.tolist()
    q = query(
        valuation.code,
        valuation.pe_ratio,
        valuation.pb_ratio
    ).filter(
        valuation.code.in_(pool)
    )
    df = get_fundamentals(q, date=context.current_dt.date())
    df = df.set_index('code')          # 关键步骤
    df = df.dropna(subset=['pe_ratio'])  # 剔除 PE 缺失的股票
    df = df[df['pe_ratio'] > 0]          # 剔除亏损股（PE 为负）
    df = df.sort_values('pe_ratio')      # PE 升序
    target = df.index.tolist()[:30]
```

**常用财务数据表（query 的取值来源）**

| 表名 | 内容 | 常用字段 |
|------|------|----------|
| `valuation` | 估值表（日频） | `pe_ratio`、`pb_ratio`、`market_cap`、`circulating_market_cap`、`turnover_ratio` |
| `indicator` | 财务指标表（季频） | `roe`、`roa`、`gross_profit_margin`、`net_profit_margin`、`eps` |
| `balance` | 资产负债表 | `total_assets`、`total_liability`、`total_equity` |
| `income` | 利润表 | `total_operating_revenue`、`net_profit`、`operating_profit` |
| `cash_flow` | 现金流量表 | `net_operate_cash_flow`、`net_invest_cash_flow` |
| `code` | 股票代码字段 | `code`（配合 `.in_()` 做过滤） |

> 关键提醒：
> 1. **`get_fundamentals` 返回的 DataFrame 索引不是股票代码**，必须显式 `df.set_index('code')`，否则 `df.index.tolist()` 拿到的是数字序号，下单会静默失败。这是新手最容易踩的坑。
> 2. `date` 参数查的是「该日期收盘后能看到的最新披露数据」，**天然避免未来函数**；`statDate` 则按指定财报期查询。
> 3. `query()` 里常用 `.filter()` 做条件过滤、`.order_by()` 排序、`.limit()` 限制条数，字段可用 `.desc()`/`.asc()` 指定升降序。

---

### 11. get_factor_values

**用途**：获取聚宽**因子库**的因子值。聚宽内置了大量计算好的因子（市值、动量、估值、波动率等），可直接调用而无需自己从原始行情计算。

**核心参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `securities` | list | 是 | 标的代码列表 |
| `factors` | list | 是 | 因子名列表，如 `['market_cap', 'momentum']` |
| `start_date` / `end_date` | str | 否 | 查询起止日期（二选一，或配合 count） |
| `count` | int | 否 | 返回最近 N 期的因子值 |

**返回值**：一个 `dict`，key 是因子名，value 是该因子的 `DataFrame`（索引为日期，列为股票代码）。

**基本用法**

```python
from jqdata import *

# 获取两只股票的市值因子（最近 1 期）
factor_dict = get_factor_values(
    ['000001.XSHE', '600000.XSHG'],
    ['market_cap'],
    end_date='2024-01-01',
    count=1
)
market_cap_df = factor_dict['market_cap']
print(market_cap_df)
```

**简单例子（市值因子选股）**

```python
def rebalance(context):
    pool = get_index_stocks('000300.XSHG')
    factor_dict = get_factor_values(pool, ['market_cap'], end_date=context.current_dt.date(), count=1)
    market_cap = factor_dict['market_cap'].iloc[-1]  # 取最新一期
    market_cap = market_cap.sort_values()            # 市值升序
    target = market_cap.index.tolist()[:30]
```

**常用内置因子名**

| 因子名 | 含义 |
|--------|------|
| `market_cap` | 总市值 |
| `pe_ratio` / `pb_ratio` | 市盈率 / 市净率 |
| `momentum` | 动量 |
| `volatility` | 波动率 |
| `roe` | 净资产收益率 |
| `turnover_ratio` | 换手率 |

> 说明：`get_factor_values` 返回值是 `dict`（key 是因子名），使用时要先取出对应因子的 DataFrame，再取最新一期（`.iloc[-1]`）。相比自己从 `get_price` 算因子，它更省事且口径统一，但要注意因子名需与聚宽因子库一致。

---

## 四、实时/单只标的信息获取

这类函数回答「某只股票的基本档案如何」，是过滤、风控、数据校验的辅助工具。

### 12. get_security_info

**用途**：获取单个标的的详细基础信息（上市日期、退市日期、类型等）。常用于判断「次新股」「是否已退市」。

**核心参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `code` | str | 是 | 标的代码，如 `'000001.XSHE'` |

**返回值**：一个对象，包含标的的基础信息（见下方「全部属性」）。

**基本用法**

```python
from jqdata import *

info = get_security_info('000001.XSHE')
print(info.start_date)   # 上市日期
print(info.end_date)     # 退市日期
```

**简单例子（过滤次新股）**

```python
def filter_stocks(context, stock_list):
    result = []
    for s in stock_list:
        info = get_security_info(s)
        if info is None:
            continue
        # 剔除上市不足 60 天的次新股
        if (context.previous_date - info.start_date).days < 60:
            continue
        result.append(s)
    return result
```

**返回值对象的全部属性**

| 属性 | 说明 |
|------|------|
| `display_name` | 中文名称 |
| `name` | 拼音缩写 |
| `start_date` | 上市日期（datetime.date） |
| `end_date` | 退市日期（datetime.date），未退市为 `2200-01-01` |
| `type` | 证券类型 |
| `parent` | 父级证券（如分级基金） |

> 说明：`get_security_info` 是判断「次新股」（用 `start_date`）和「退市股」（用 `end_date`）的权威来源。判断退市也可用 `end_date < context.current_dt.date()`。

---

### 13. get_money_flow

**用途**：获取资金流向数据（主力、超大单、大单、中单、小单的净流入/流出）。用于「资金流向」类策略，判断主力资金的进出方向。

**核心参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `security_list` | list | 是 | 标的代码列表 |
| `start_date` | str / datetime | 否 | 开始日期 |
| `end_date` | str / datetime | 否 | 结束日期 |
| `fields` | list / str | 否 | 返回字段（见下方属性） |
| `count` | int | 否 | 返回最近 N 条 |

**返回值**：一个 `DataFrame`，索引为时间（多标的时为 MultiIndex）。

**基本用法**

```python
from jqdata import *

# 获取平安银行近 20 日资金流向
df = get_money_flow(['000001.XSHE'], count=20, fields=['date', 'net_amount_main'])
print(df.head())
```

**简单例子（主力净流入选股）**

```python
def rebalance(context):
    pool = get_index_stocks('000300.XSHG')
    df = get_money_flow(pool, count=5, fields=['sec_code', 'net_amount_main'])
    # 按主力净流入排序，取流入最多
    recent = df.groupby('sec_code')['net_amount_main'].sum()
    recent = recent.sort_values(ascending=False)
    target = recent.index.tolist()[:30]
```

**常用字段（fields 可选值）**

| 字段 | 说明 |
|------|------|
| `date` | 日期 |
| `sec_code` | 股票代码 |
| `net_amount_main` | 主力净流入额（超大单+大单） |
| `net_amount_xl` | 超大单净流入额 |
| `net_amount_l` | 大单净流入额 |
| `net_amount_m` | 中单净流入额 |
| `net_amount_s` | 小单净流入额 |
| `net_pct_main` | 主力净流入占比 |

> 说明：资金流向数据口径（主力 = 超大单 + 大单）各平台略有差异，且该数据为估算值，噪声较大，需结合其他因子综合使用，不宜单独作为决策依据。

---

## 附：函数分类速查表

| 分类 | 函数 | 一句话说明 | 返回类型 |
|------|------|-----------|----------|
| 标的池 | `get_all_securities` | 全市场标的 | DataFrame |
| 标的池 | `get_index_stocks` | 指数成分股 | list |
| 标的池 | `get_industry_stocks` | 行业成分股 | list |
| 标的池 | `get_concept_stocks` | 概念成分股 | list |
| 行情 | `get_price` | 历史行情（通用） | DataFrame |
| 行情 | `attribute_history` | 单标的最近 N 根 | DataFrame |
| 行情 | `history` | 多标的最近 N 根（单字段） | DataFrame |
| 行情 | `get_bars` | bar 线数据 | DataFrame |
| 行情 | `get_current_data` | 当前实时数据 | dict |
| 基本面 | `get_fundamentals` | 财务/估值查询 | DataFrame |
| 基本面 | `get_factor_values` | 聚宽因子库值 | dict |
| 信息 | `get_security_info` | 单标的档案 | 对象 |
| 信息 | `get_money_flow` | 资金流向 | DataFrame |

---

> 本文档是《Quant_Lab 聚宽量化策略学习库》的配套速查资料，建议配合 `strategies/` 目录下的 10 个策略代码和 `docs/` 目录下各策略的详解文档一起阅读。函数的最新权威定义请以[聚宽官方 API 文档](https://www.joinquant.com/help/api/help)为准。
