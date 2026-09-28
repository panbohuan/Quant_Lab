# Pandas 学习指南：量化新手入门

> 面向量化新手的 pandas 基础教程。pandas 是 Python 处理表格数据最核心的库，也是聚宽策略里绕不开的工具——`get_fundamentals` 返回的是 DataFrame，因子计算全靠它。

---

## 一、为什么量化必须学 pandas？

想象你要处理一份「所有股票的基本面数据」：

| 股票代码 | 市盈率 | 市净率 | 净资产收益率 |
|----------|--------|--------|-------------|
| 000001.XSHE | 6.5 | 0.8 | 11% |
| 600000.XSHG | 5.2 | 0.7 | 10% |
| ... | ... | ... | ... |

这份表格可能有 5000 行（5000 只股票）、几十列（几十个因子）。如果用手写 for 循环处理，又慢又容易出错。pandas 就是为「高效操作这种表格」而生的，它把表格抽象成两个核心对象：

- **Series**：一列数据（带索引的一维数组）；
- **DataFrame**：一整张表（多列 Series 组成，带行列索引）。

聚宽里几乎所有数据接口返回的都是 DataFrame，所以 pandas 是「必经之路」。

---

## 二、核心对象：Series 和 DataFrame

### 2.1 Series —— 一列数据

```python
import pandas as pd

# 创建 Series（索引 + 值）
s = pd.Series([6.5, 5.2, 8.1], index=['000001.XSHE', '600000.XSHG', '000002.XSHE'])
print(s)
# 000001.XSHE    6.5
# 600000.XSHG    5.2
# 000002.XSHE    8.1
```

访问方式：

```python
s['000001.XSHE']      # 按索引取值 → 6.5
s.iloc[0]             # 按位置取值 → 6.5
s.mean()              # 平均值 → 6.6
s.max()               # 最大值 → 8.1
s.sort_values()       # 排序
```

### 2.2 DataFrame —— 一整张表

```python
import pandas as pd

df = pd.DataFrame({
    'pe':   [6.5, 5.2, 8.1],
    'pb':   [0.8, 0.7, 1.2],
    'roe':  [0.11, 0.10, 0.15],
}, index=['000001.XSHE', '600000.XSHG', '000002.XSHE'])

print(df)
#                pe   pb   roe
# 000001.XSHE  6.5  0.8  0.11
# 600000.XSHG  5.2  0.7  0.10
# 000002.XSHE  8.1  1.2  0.15
```

访问方式：

```python
df['pe']                    # 取一列 → Series
df[['pe', 'pb']]            # 取多列 → DataFrame
df.loc['000001.XSHE']       # 按索引取一行 → Series
df.loc['000001.XSHE', 'pe'] # 按索引取单元格 → 6.5
df.iloc[0, 0]               # 按位置取单元格 → 6.5
```

---

## 三、量化最常用的 8 个操作

### 3.1 `set_index` —— 设置索引（最重要！）

**聚宽里最常踩的坑**：`get_fundamentals` 返回的 DataFrame 索引是 `0,1,2,...`，**不是股票代码**。必须 `set_index('code')`，之后 `df.index` 才是股票代码。

```python
df = get_fundamentals(q)      # 索引是 0,1,2...
df = df.set_index('code')     # 现在索引是股票代码
codes = df.index.tolist()     # 得到股票代码列表
```

### 3.2 `dropna` —— 删除缺失值

因子数据经常有缺失（比如某些股票没有 PE）。`dropna` 删除含缺失值的行。

```python
df = df.dropna()                          # 删除任意列有缺失的行
df = df.dropna(subset=['pe_ratio'])       # 只删 pe_ratio 缺失的行
```

### 3.3 `sort_values` —— 排序

选股的核心：按因子排序取前 N。

```python
df = df.sort_values('pe_ratio')                    # PE 升序（低估在前）
df = df.sort_values('roe', ascending=False)        # ROE 降序（高质在前）
top30 = df.head(30).index.tolist()                 # 取前30只的代码
```

### 3.4 `rank` —— 排名（因子合成必备）

把因子值转成排名，统一量纲，才能公平加权。

```python
df['pe_rank'] = df['pe_ratio'].rank(pct=True, ascending=False)  # PE越小排名越靠前
df['roe_rank'] = df['roe'].rank(pct=True)                       # ROE越大排名越靠前
# 合成
df['score'] = 0.5 * df['pe_rank'] + 0.5 * df['roe_rank']
```

### 3.5 `apply` —— 逐行/逐列计算

对一列做自定义变换。

```python
# 把 PE 做标准化（z-score）
df['pe_z'] = df['pe_ratio'].apply(lambda x: (x - df['pe_ratio'].mean()) / df['pe_ratio'].std())
```

### 3.6 `groupby` —— 分组聚合

按行业分组算平均值（行业中性化、行业分析必备）。

```python
df['industry'] = ...  # 每只股票的行业
df.groupby('industry')['pe_ratio'].mean()   # 每个行业的平均PE
```

### 3.7 布尔过滤 —— 条件筛选

```python
df = df[df['pe_ratio'] > 0]              # 只保留 PE 为正（剔除亏损股）
df = df[(df['roe'] > 0.15) & (df['pb'] < 2)]  # 多个条件用 & 连接
```

### 3.8 合并 —— `concat` 和 `merge`

```python
# 纵向拼接（两个 DataFrame 上下堆叠）
combined = pd.concat([df1, df2])

# 横向合并（按索引对齐，类似 SQL join）
merged = df1.merge(df2, on='code')
```

---

## 四、一个完整的量化示例

把上面所有操作串起来，写一个「低 PE + 高 ROE 选股」的完整流程：

```python
import pandas as pd

# 1. 假设已经从聚宽拿到数据（DataFrame，索引是 0,1,2...）
df = get_fundamentals(q)          # 含 code, pe_ratio, roe 三列
df = df.set_index('code')         # 索引设为股票代码

# 2. 清洗
df = df.dropna(subset=['pe_ratio', 'roe'])   # 删除缺失
df = df[df['pe_ratio'] > 0]                  # 删除亏损股（PE为负）

# 3. 排名（统一量纲）
df['pe_rank'] = df['pe_ratio'].rank(pct=True, ascending=False)  # PE越小越好
df['roe_rank'] = df['roe'].rank(pct=True)                       # ROE越大越好

# 4. 合成打分
df['score'] = 0.5 * df['pe_rank'] + 0.5 * df['roe_rank']

# 5. 选前20只
target = df.sort_values('score', ascending=False).head(20).index.tolist()

print(target)
```

这 20 行代码，就是「多因子选股」的最小骨架。入门篇的策略 7（四因子打分）本质上就是这个逻辑的扩展。

---

## 五、新手最容易犯的 5 个错

1. **忘了 `set_index('code')`**：导致 `df.index` 是数字而非股票代码，下单失败；
2. **用 `in` 而不是 `&` 做多条件筛选**：`df[df['a']>0 and df['b']>0]` 会报错，必须用 `&`（且加括号）；
3. **混淆 `loc` 和 `iloc`**：`loc` 用「索引名」，`iloc` 用「位置序号」；
4. **原地修改 vs 返回新对象**：`df.sort_values()` 返回新对象，必须 `df = df.sort_values(...)`，否则白排序；
5. **缺失值没处理就排序**：NaN 参与排序结果不可预测，先 `dropna`。

---

## 六、延伸学习

- **时间序列**：`df.resample()`、`df.shift()`（计算收益率）、`df.rolling()`（滚动窗口）；
- **透视表**：`df.pivot_table()`（把长表转成宽表）；
- **向量化思维**：pandas 的核心是「整列操作」而非「逐行循环」，能用向量化就别用 for 循环（快几十倍）。

下一篇《pandas 量化应用指南》会用更多实际案例，展示 pandas 在量化策略里的具体用法。
