# 策略 2：单因子动量选股（Momentum）

> 策略类型：单因子选股（量价因子） ｜ 难度：★★☆☆☆ ｜ 前置知识：策略1、Python 列表/字典/sorted

## 一、核心思路：什么是"因子"与"动量效应"

**因子（Factor）** 是描述股票某一特征、可用于预测未来收益的量化指标。**因子选股**的思路是：每一期按某个因子对股票打分/排序，买入得分最高的若干只，卖出得分低的，定期换仓。

**动量效应（Momentum）**：过去一段时间（如 3~12 个月）表现好的股票，在未来一段时间倾向于继续跑赢；反之亦然。这是学术界和实务界公认最稳健的市场异象之一（Jegadeesh & Titman, 1993）。通俗说就是"强者恒强、追涨杀跌"的量化版本。

本策略把"过去 60 日收益率"作为动量因子，每月买入动量最强的 20 只。

## 二、算法结构（选股策略的通用框架）

几乎所有的因子选股策略都遵循同一个骨架，**请务必记住这个框架**，后续策略只是替换"因子"和"排序方式"：

```
每月第一个交易日 09:30 触发 rebalance(context)
   │
   ├─ 1. 确定股票池 pool（get_index_stocks / get_all_securities）
   │
   ├─ 2. 过滤：剔除 ST、停牌、次新等不可交易股票（get_current_data）
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

> 想用全市场股票：`get_all_securities(['stock']).index.tolist()`，但全市场股票多达 5000+，因子计算更慢，初学者建议先用指数成分股。

### 3.2 `get_current_data()` —— 当日实时数据 + 过滤

返回一个类似字典的对象，键是股票代码，值是该股票的当日信息。最常用的几个属性：

| 属性 | 含义 |
|------|------|
| `current_data[s].is_st` | 是否为 ST（风险警示股） |
| `current_data[s].paused` | 是否停牌（停牌无法交易） |
| `current_data[s].day_open` | 当日开盘价（0 表示未开盘/新股首日） |
| `current_data[s].name` | 股票名称 |

过滤写法（列表推导式）：
```python
current_data = get_current_data()
pool = [s for s in pool
        if not current_data[s].is_st
        and not current_data[s].paused]
```

**为什么要过滤？** ST 股有退市风险、涨跌幅受限；停牌股无法买入；若不过滤，回测中会"买到买不到的股票"，导致结果失真。

### 3.3 `run_monthly(func, monthday, time)` —— 每月定时运行

在**每月第 monthday 个交易日**运行 `func`。`monthday=1` 表示每月第一个交易日；`monthday=-1` 表示每月最后一个交易日。

```python
run_monthly(rebalance, 1, time='09:30')   # 每月第1个交易日 09:30 调仓
run_monthly(rebalance, -1, time='14:50')  # 每月最后1个交易日 14:50 调仓
```

> 选股策略通常"月度调仓"：太频繁会带来高换手和高成本，太稀疏又跟不上因子变化，月度是折中且主流的选择。

### 3.4 `context.portfolio.positions` —— 当前持仓

`context.portfolio` 是账户对象，其中 `.positions` 是一个**字典**，键为股票代码，值为持仓对象。遍历它即可获得当前持有的所有股票：

```python
for s in list(context.portfolio.positions):
    print(s, context.portfolio.positions[s].total_amount)  # 代码 + 持股数量
```

### 3.5 排序与切片（Python 内置）

```python
# sorted 按字典的值排序，reverse=True 降序，取前 20 个键
target = sorted(momentum, key=momentum.get, reverse=True)[:g.stock_num]
```

`momentum` 是 `{'股票代码': 因子值}` 的字典，`key=momentum.get` 表示按因子值排序。这是因子选股里最核心的一行代码。

### 3.6 等权买入

```python
per_value = context.portfolio.total_value / len(target)   # 每只分配相同金额
for s in target:
    order_target_value(s, per_value)
```

`context.portfolio.total_value` 是账户**总资产**（现金 + 持仓市值）。"等权"（Equal Weight）指每只股票分配相同资金，是最简单的组合构建方式。

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
