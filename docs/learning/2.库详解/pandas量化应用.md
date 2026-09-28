# Pandas 量化应用指南：用 pandas 写量化策略

> 本篇用「真实量化场景」讲解 pandas 的进阶用法。建议先读《pandas 学习指南》掌握基础，再回到本篇看实战。

---

## 一、计算收益率（收益分析的起点）

所有策略的第一步，几乎都是把「价格」变成「收益率」。

```python
import pandas as pd

# 假设拿到某股票的历史收盘价（时间索引的 Series）
closes = df['close']

# 简单收益率：r_t = p_t / p_{t-1} - 1
returns = closes.pct_change()          # 等价于 closes / closes.shift(1) - 1

# 对数收益率（更常用于统计）
log_returns = pd.np.log(closes / closes.shift(1))
```

**`shift()` 是关键**：它把整列数据「往下挪一格」，`closes.shift(1)` 就是「昨天的价格」，两者相除就是今天的收益率。

```python
closes = pd.Series([100, 102, 101, 105])
print(closes.shift(1))
# 0      NaN   <- 第一天没有"昨天"
# 1    100.0
# 2    102.0
# 3    101.0
```

---

## 二、滚动窗口：计算均线和波动率

### 2.1 移动平均线（MA）

```python
closes = df['close']
ma5 = closes.rolling(window=5).mean()    # 5日均线
ma20 = closes.rolling(window=20).mean()  # 20日均线
```

### 2.2 滚动波动率

```python
returns = closes.pct_change()
vol = returns.rolling(window=20).std() * (252 ** 0.5)  # 20日滚动年化波动率
```

### 2.3 滚动最大回撤

```python
# 滚动最高价
rolling_max = closes.rolling(window=60, min_periods=1).max()
drawdown = closes / rolling_max - 1    # 相对最高点的回撤
```

---

## 三、因子计算的实战（动量、反转、波动率）

### 3.1 动量因子（过去 N 日涨幅）

```python
def momentum(closes, n=60):
    return closes.iloc[-1] / closes.iloc[0] - 1

# 或者向量化（对整个 DataFrame 批量算）
mom = close_df.iloc[-1] / close_df.iloc[0] - 1   # 每只股票的60日动量
```

### 3.2 反转因子（短期跌多了会反弹）

```python
# 5日反转：过去5日跌得越多，越可能反弹
reversal = close_df.iloc[-1] / close_df.iloc[-5] - 1
# 取 reversal 最小的（跌最多）作为买入候选
```

### 3.3 波动率因子（低波动更优）

```python
ret_df = close_df.pct_change()
vol = ret_df.rolling(window=60).std()   # 每只股票的波动率
```

---

## 四、横截面操作：一次处理所有股票

量化里「横截面」=「同一时刻，比较所有股票」。pandas 的 DataFrame 天然适合做横截面操作。

```python
# close_df 是"宽表"：行=日期，列=股票代码
#          000001.XSHE  600000.XSHG  ...
# 2024-01-01   10.5        7.2
# 2024-01-02   10.6        7.1

# 1. 算全市场某天的收益率（横截面）
daily_ret = close_df.pct_change().iloc[-1]   # 最后一天，所有股票的收益率

# 2. 排序取前20（横截面选股）
top20 = daily_ret.sort_values(ascending=False).head(20)

# 3. 计算所有股票的平均收益率（横截面均值）
market_avg = daily_ret.mean()
```

---

## 五、IC 计算：因子有效性检验

IC（信息系数）= 因子值与未来收益的相关系数，衡量「因子有没有用」。

```python
import pandas as pd

# factor: 本期的因子值（Series，索引=股票代码）
# future_ret: 未来N日收益（Series，索引=股票代码）
ic = factor.corr(future_ret)   # 直接算相关系数，就是 IC

# 或按时间序列算多期 IC
ic_series = []
for date in dates:
    f = factor_df.loc[date]
    r = future_ret_df.loc[date]
    ic_series.append(f.corr(r))

ic_mean = pd.Series(ic_series).mean()   # IC 均值
ic_ir = ic_mean / pd.Series(ic_series).std()  # IC_IR（稳定性）
```

**判断标准**：|IC| > 0.03 算有效，IC_IR > 0.5 算稳定。

---

## 六、分组回测：因子分层检验

「分层回测」检验因子是否有单调性——按因子值把股票分成 5 组，看每组收益是否单调递增/递减。

```python
# 1. 按因子值分5组（用 qcut 分位分组）
df['group'] = pd.qcut(df['factor'], 5, labels=False)   # 0~4 五组

# 2. 每组未来收益
group_ret = df.groupby('group')['future_ret'].mean()
print(group_ret)
# 如果 group 0（因子最小）到 group 4（因子最大）的收益单调，说明因子有效
```

---

## 七、透视表：长表转宽表

聚宽数据经常是「长表」（一行一个（日期, 股票）），分析时要转成「宽表」（行=日期，列=股票）。

```python
# 长表：每行是 (date, code, value)
long_df = pd.DataFrame({
    'date': ['2024-01-01', '2024-01-01', '2024-01-02', '2024-01-02'],
    'code': ['000001.XSHE', '600000.XSHG', '000001.XSHE', '600000.XSHG'],
    'value': [10.5, 7.2, 10.6, 7.1],
})

# 转宽表：pivot
wide_df = long_df.pivot(index='date', columns='code', values='value')
print(wide_df)
# code        000001.XSHE  600000.XSHG
# date
# 2024-01-01        10.5         7.2
# 2024-01-02        10.6         7.1
```

---

## 八、综合案例：一个完整的多因子选股流程

把前面的知识串起来，写一个「动量 + 低波动 + 低估值」三因子选股：

```python
import pandas as pd

def multi_factor_select(context, pool):
    """三因子选股：动量 + 低波动 + 低估值"""

    # 1. 批量取历史收盘价（宽表：列=股票）
    close_df = history(pool, 60, '1d', 'close', df=True)

    # 2. 动量因子（60日涨幅，越大越好）
    momentum = close_df.iloc[-1] / close_df.iloc[0] - 1

    # 3. 波动率因子（60日波动率，越小越好）
    ret_df = close_df.pct_change()
    volatility = ret_df.rolling(window=60).std().iloc[-1]

    # 4. 估值因子（PE，越小越好）
    q = query(valuation.code, valuation.pe_ratio).filter(valuation.code.in_(pool))
    pe_df = get_fundamentals(q).set_index('code')['pe_ratio']

    # 5. 对齐：只保留三个因子都有值的股票
    valid = momentum.index.intersection(volatility.index).intersection(pe_df.index)

    # 6. 排名（统一量纲）
    score = pd.DataFrame(index=valid)
    score['mom_rank'] = momentum[valid].rank(pct=True)                    # 越大越好
    score['vol_rank'] = volatility[valid].rank(pct=True, ascending=False) # 越小越好
    score['pe_rank'] = pe_df[valid].rank(pct=True, ascending=False)       # 越小越好

    # 7. 等权合成
    score['total'] = score.mean(axis=1)

    # 8. 取前20
    target = score.sort_values('total', ascending=False).head(20).index.tolist()
    return target
```

这个函数就是「进阶篇因子择时策略」的简化版骨架。理解了它，你就理解了多因子选股的本质。

---

## 九、性能提示

1. **能向量化就别循环**：`close_df.pct_change()` 一次算完所有股票，比 `for s in pool` 快几十倍；
2. **批量取数**：`history(pool, ...)` 一次取所有股票，别 `for s in pool: attribute_history(s, ...)`；
3. **提前过滤**：先缩小股票池（过滤 ST、停牌），再算因子，避免无谓计算；
4. **缓存中间结果**：如果多个因子用到同一个数据（如收盘价），只取一次，复用。
