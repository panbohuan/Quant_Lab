# 策略 9：因子 IC/IR 加权选股（动态权重多因子）

> 策略类型：多因子进阶（因子有效性度量） ｜ 难度：★★★★★ ｜ 前置知识：策略7/8、相关性概念

## 一、核心思路：给因子"称重"

策略7把所有因子**等权**相加，隐含假设"每个因子同样有效"。但现实中：

- 某个因子在牛市有效、熊市失效；
- 因子有效性会随时间**衰减或回归**（因子拥挤、被市场消化）。

**IC/IR 加权**的思路：**用历史数据度量每个因子"有多有效"，有效性高的给更高权重，动态调整。**

## 二、IC 与 IR：因子有效性的度量

### 2.1 信息系数 IC（Information Coefficient）

IC = **因子值**与**未来一期收益**的相关系数（截面），衡量"因子对收益的预测能力"：

$$IC = corr(factor_t,\ return_{t \to t+1})$$

- IC 取值范围 [-1, 1]，绝对值越大预测力越强；
- |IC| > 0.03 被认为是有效因子，> 0.05 相当优秀；
- 每期算一个 IC，滚动多期后得到 IC 序列。

### 2.2 信息比率 IR（Information Ratio）

IR = IC 序列的**均值 / 标准差**：

$$IR = \frac{\overline{IC}}{\sigma(IC)}$$

- **均值**反映平均预测能力；
- **标准差**反映稳定性；
- IR 同时兼顾"有效"和"稳定"，是比单纯 IC 均值更科学的权重依据。

本策略用 `IR = mean(IC) / std(IC)` 作为每个因子的权重（无历史时退化为等权）。

## 三、算法结构

```
每月第1个交易日 → monthly(context)
  ├─ 股票池：全市场 + 过滤 ST/退市/停牌/次新/涨跌停
  ├─ 计算当期因子：momentum / pb / roe / market_cap（set_index('code')）
  ├─ 取当期收盘价 cur_price
  │
  ├─ 【算IC】用上一期快照：
  │      realized_ret = cur_price / prev_price - 1
  │      每个因子：IC = corr(prev_factor, realized_ret)
  │      滚动窗口保留最近12期
  │
  ├─ 存当期快照（因子+价格），只保留最近2期
  ├─ 权重 = IR = mean(IC)/std(IC)
  ├─ 标准化 + 方向 + 加权合成 score
  ├─ 按 score 取前 30 只
  └─ 换仓
```

## 四、函数详解

### 4.0 `df.set_index('code')` —— 必须记住的关键一步

`compute_factors` 里用 `get_fundamentals` 查 pb/roe/market_cap，返回的 DataFrame 索引是 0,1,2... 数字序号，**不是股票代码**。必须显式 `set_index('code')`，否则后续 `history(..., df.index.tolist(), ...)` 会传入错误代码、`df['momentum'] = momentum` 会索引不对齐（详见策略3的 3.3 节）。

```python
df = get_fundamentals(q, date=context.current_dt.date())
df = df.set_index('code')     # 【关键】之后 index 才是股票代码
```

### 4.1 `history(count, unit, field, security_list, df=True)` —— 批量取行情

与 `attribute_history`（单标的）不同，`history` 可以**一次取多只标的**，返回 DataFrame（索引=时间，列=股票代码），适合批量、向量化计算，性能远优于逐股循环：

```python
close_df = history(60, '1d', 'close', ['000001.XSHE','600519.XSHG'], df=True)
momentum = close_df.iloc[-1] / close_df.iloc[0] - 1   # 一次性算完所有股票的动量
```

- `security_list`：股票代码列表；
- 返回 df 中，`iloc[-1]` 是最后一根K线，`iloc[0]` 是第一根；
- 停牌/次新股会自动产生 NaN，配合 `dropna` 处理。

> 这也是策略2~8中 `for s in pool: attribute_history(...)` 的**高效替代写法**，建议在股票数量大时优先使用。

### 4.2 计算 IC：`.corr()`

```python
ic = prev_factors[f].loc[common].corr(realized_ret.loc[common])
```

pandas 的 `Series.corr(other)` 默认计算**皮尔逊相关系数**。注意先 `common` 取交集对齐，避免 NaN。

### 4.3 滚动窗口

```python
g.ic[f].append(ic)               # 追加新一期IC
g.ic[f] = g.ic[f][-g.ic_window:] # 只保留最近12期
```

用 `g.ic`（字典，键=因子名，值=IC列表）记录历史，`g` 全局变量在整个回测期间持续存在，是聚宽里保存跨期状态的惯用方式。

### 4.4 快照机制（关键！防止未来函数）

```python
g.snapshots.append({'factors': factors, 'price': cur_price})
g.snapshots = g.snapshots[-2:]
```

这是 IC 计算的**正确性关键**：

- 当期只能知道"上一期因子值"和"上一期至今的收益"，才能算出上一期的 IC；
- 如果把当期因子和当期收益直接相关，就引入了**未来函数**（用未来信息回测），结果会虚假地好看。

本策略严格用 `prev` 快照算 IC，杜绝未来函数。

### 4.5 权重与合成

```python
weights[f] = np.mean(ics) / (np.std(ics) + 1e-12)   # IR
...
z = (factors[f] - factors[f].mean()) / (factors[f].std() + 1e-12)  # 标准化
score += weights[f] * g.direction[f] * z
```

- `+1e-12` 防止除以 0；
- 方向 `g.direction` 统一"越大越好"。

## 五、回测说明

**回测参数（建议）：** 区间 2016-01-01 ～ 2026-01-01，初始资金 100 万，月度调仓，基准沪深300。

**关注指标：** 年化收益、最大回撤、夏普，以及日志里打印的**每期因子 IR 权重**——观察哪些因子权重高（说明近期有效），这是理解市场风格切换的窗口。

**如实说明：** 需在聚宽平台运行获取真实数据。风险提示：
- IC 窗口太短会**过拟合噪声**，太长会**滞后于风格切换**，需调参平衡；
- IR 权重可能为负（因子近期反向），此时应**剔除或反转**该因子，而非机械使用；
- 全市场逐月算因子+IC 计算量大，回测较慢属正常。

## 六、改进方向

1. 用 **Rank IC**（斯皮尔曼相关）替代皮尔逊，对极端值更稳健；
2. IC 为负的因子自动**剔除/反转**（动态因子筛选）；
3. 结合策略8，对因子**先中性化再算 IC**，度量更纯粹的预测力。
