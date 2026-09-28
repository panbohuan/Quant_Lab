# 策略 2：单因子动量选股（Momentum）

> 策略类型：单因子选股（量价因子） ｜ 难度：★★☆☆☆ ｜ 前置知识：策略1、Python 列表/字典/sorted

## 一、核心思路：什么是"因子"与"动量效应"

**因子（Factor）** 是描述股票某一特征、可用于预测未来收益的量化指标。**因子选股**的思路是：每一期按某个因子对股票打分/排序，买入得分最高的若干只，卖出得分低的，定期换仓。

**动量效应（Momentum）**：过去一段时间（如 3~12 个月）表现好的股票，在未来一段时间倾向于继续跑赢；反之亦然。这是学术界和实务界公认最稳健的市场异象之一（Jegadeesh & Titman, 1993）。通俗说就是"强者恒强、追涨杀跌"的量化版本。

**为什么动量有效？** 几个主流解释：
- **反应不足**：市场对新信息的反应是渐进的，好消息的股价上涨需要时间消化，所以前期涨的会继续涨；
- **羊群效应与资金惯性**：机构资金建仓是分批进行的，趋势一旦形成会自我强化；
- **行为偏差**：投资者"追涨"心理放大趋势。

本策略把"过去 60 日收益率"作为动量因子，每月买入动量最强的 20 只。

## 二、算法结构（选股策略的通用框架）

几乎所有的因子选股策略都遵循同一个骨架，**请务必记住这个框架**，后续策略只是替换"因子"和"排序方式"：

```
每月第一个交易日 09:30 触发 rebalance(context)
   │
   ├─ 1. 确定股票池 pool（get_index_stocks / get_all_securities）
   │
   ├─ 2. 过滤：剔除 ST、退市、停牌、次新、涨跌停等不可交易/高风险股票
   │
   ├─ 3. 计算每只股票的因子值（动量 = 过去N日涨幅）
   │
   ├─ 4. 排序，选出目标股票 target（前 K 只）
   │
   ├─ 5. 卖出不在 target 里的旧持仓（遍历 positions）
   │
   └─ 6. 等权买入 target（order_target_value）
```

## 三、函数详解

### 3.1 `get_index_stocks(index_symbol)` —— 获取指数成分股

返回某指数在**当前日期**的成分股列表，是最常用的"股票池"来源。

```python
stocks = get_index_stocks('000300.XSHG')   # 沪深300成分股
stocks = get_index_stocks('000905.XSHG')   # 中证500成分股
stocks = get_index_stocks('000852.XSHG')   # 中证1000成分股
```

- **算法逻辑**：从指数数据库读取该指数当日的最新成分股名单（成分股会定期调整）。
- **其他用法**：`get_index_stocks('000300.XSHG', date='2020-01-01')` 可指定历史某日的成分股（注意传 `date` 而非用全局时间）。
- **常用指数代码速查**：沪深300=`000300.XSHG`，中证500=`000905.XSHG`，中证1000=`000852.XSHG`，上证50=`000016.XSHG`，创业板指=`399006.XSHE`。

> 想用全市场股票：`get_all_securities(['stock']).index.tolist()`，但全市场股票多达 5000+，因子计算更慢，初学者建议先用指数成分股。

### 3.2 `get_current_data()` —— 当日实时数据 + 过滤（核心）

返回一个**类似字典的对象**，键是股票代码，值是该股票的当日信息（`CurrentData` 对象）。这是过滤逻辑的基础。

**所含属性（常用）**：

| 属性 | 类型 | 含义 |
|------|------|------|
| `is_st` | bool | 是否为 ST / *ST（财务风险警示） |
| `paused` | bool | 是否停牌（停牌无法交易） |
| `name` | str | 股票名称（含"ST"、"退"等字样） |
| `day_open` | float | 当日开盘价（0 表示未开盘/无交易） |
| `last_price` | float | 最新价 |
| `high_limit` | float | 当日涨停价 |
| `low_limit` | float | 当日跌停价 |
| `unit` | int | 最小交易单位（股），A股通常为 100 |

### 3.3 `filter_stocks` 过滤函数 —— 本次修复的核心

本次更新把过滤逻辑封装成了独立函数，并**补齐了原来缺失的几类过滤**。这是保证"回测能正常交易、不买到买不到的股票"的关键。

```python
def filter_stocks(context, stock_list):
    current_data = get_current_data()
    yesterday = context.previous_date
    result = []
    for s in stock_list:
        d = current_data[s]
        if d.is_st or '退' in d.name:      # ① 剔除 ST、退市
            continue
        if d.paused:                        # ② 剔除停牌
            continue
        if d.day_open <= 0:                 # ③ 剔除当日无行情
            continue
        info = get_security_info(s)
        if info is None or (yesterday - info.start_date).days < g.min_list_days:  # ④ 次新股
            continue
        if d.high_limit <= d.last_price or d.low_limit >= d.last_price:  # ⑤ 涨跌停
            continue
        result.append(s)
    return result
```

**逐条解释"为什么要过滤"**：

1. **ST / *ST 股**：公司财务异常，有退市风险，涨跌幅被限制为 5%（主板），且基本面恶化。回测中若不剔除，会把"高风险垃圾股"当正常股票买，扭曲结果。
2. **退市股（名称含"退"）**：进入退市整理期，即将摘牌，买入可能血本无归。
3. **停牌股**：停牌期间无法下单成交。若回测"买到了停牌股"，收益是假的。
4. **次新股（上市不足 N 天）**：上市初期股价波动剧烈（连续涨停板）、历史数据不足（无法算 60 日动量）、且往往有炒作泡沫，属于"异常样本"，应剔除。
5. **涨跌停股**：涨停板买入会失败（排队买不到），跌停板卖出会失败。若不过滤，回测会"成交"在涨停价上，严重失真。

> **这是本次更新的重点**：之前的代码只过滤了 ST 和停牌，导致回测中可能买入涨停股、次新股、退市股，产生无法复现的虚假收益。现在这套过滤是所有选股策略的标准防线。

### 3.4 `get_security_info(code)` —— 个股基本信息

返回某只股票的基本信息对象，常用属性：

| 属性 | 含义 |
|------|------|
| `start_date` | 上市日期（datetime.date） |
| `end_date` | 退市日期（未退市则为远期日期如 2200-01-01） |
| `display_name` | 中文名称 |
| `type` | 类型（stock/fund 等） |

本例用它判断次新股：`(yesterday - info.start_date).days < g.min_list_days` 即"上市不足 60 天则剔除"。

### 3.5 `context.previous_date` —— 上一个交易日

`context.previous_date` 是**上一个交易日**（datetime.date）。用它和上市日期做差，得到"已上市天数"，比用当前日期更严谨（避免含周末/节假日导致的天数虚高，虽然这里只是粗略判断）。

### 3.6 `run_monthly(func, monthday, time)` —— 每月定时运行

在**每月第 monthday 个交易日**运行 `func`。`monthday=1` 表示每月第一个交易日；`monthday=-1` 表示每月最后一个交易日。

```python
run_monthly(rebalance, 1, time='09:30')   # 每月第1个交易日 09:30 调仓
run_monthly(rebalance, -1, time='14:50')  # 每月最后1个交易日 14:50 调仓
```

> 选股策略通常"月度调仓"：太频繁会带来高换手和高成本，太稀疏又跟不上因子变化，月度是折中且主流的选择。

### 3.7 `context.portfolio.positions` —— 当前持仓

`context.portfolio` 是账户对象，其中 `.positions` 是一个**字典**，键为股票代码，值为持仓对象（`Position`）。遍历它即可获得当前持有的所有股票：

```python
for s in list(context.portfolio.positions):
    print(s, context.portfolio.positions[s].total_amount)  # 代码 + 持股数量
```

- **为什么遍历时要 `list(...)`**：因为在遍历过程中会卖出（修改字典），直接用 `for s in context.portfolio.positions` 会在迭代中修改字典报错，包一层 `list()` 先复制键列表即可安全遍历。
- `Position` 对象常用属性：`total_amount`（持股数）、`closeable_amount`（可卖股数，T+1 下当日买入的不可卖）、`avg_cost`（成本价）。

### 3.8 排序与切片（Python 内置）

```python
# sorted 按字典的值排序，reverse=True 降序，取前 20 个键
target = sorted(momentum, key=momentum.get, reverse=True)[:g.stock_num]
```

`momentum` 是 `{'股票代码': 因子值}` 的字典。`key=momentum.get` 表示"按字典的值排序"（`momentum.get(code)` 返回该股的因子值）。这是因子选股里最核心的一行代码，务必理解。

### 3.9 等权买入

```python
per_value = context.portfolio.total_value / len(target)   # 每只分配相同金额
for s in target:
    order_target_value(s, per_value)
```

`context.portfolio.total_value` 是账户**总资产**（现金 + 持仓市值）。"等权"（Equal Weight）指每只股票分配相同资金，是最简单的组合构建方式（对标的：市值加权、因子值加权等）。

## 四、回测说明

**回测参数（建议）：** 区间 2016-01-01 ～ 2026-01-01，初始资金 100 万，月度调仓，基准沪深300。

**关注指标：** 年化收益、最大回撤、夏普比率，以及**换手率**（月度换仓带来的交易频率，影响真实成本）。

**如实说明：** 需在聚宽平台运行获取真实数据。风险提示：
- 动量因子在**市场风格急转**（如牛熊切换）时容易大幅回撤，俗称"动量崩盘"；
- 追高买入天然存在"买在阶段高点"的风险；
- 沪深300成分股流动性好，若换成小市值股需更注意冲击成本。

## 五、改进方向

1. 改用**全市场股票池**（`get_all_securities`），动量效应在小盘股中更显著；
2. 动量回看期改用 3、6、12 个月多种组合（多周期动量）；
3. 引入"剔除近 1 个月收益"（经典动量做法：跳过短期反转），见进阶文献。
