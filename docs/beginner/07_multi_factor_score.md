# 策略 7：多因子打分模型（四因子：估值 + 质量 + 动量 + 规模）

> 策略类型：多因子选股（打分法） ｜ 难度：★★★★☆ ｜ 前置知识：策略3/4/5/6、z-score

## 一、核心思路：四大类经典因子的综合

因子研究把主流因子归纳为几大类（这也是 Barra 等商业模型的基础）：

| 大类 | 代表因子 | 方向 | 含义 |
|------|---------|------|------|
| 价值 Value | PB / PE | 越低越好 | 便宜 |
| 质量 Quality | ROE | 越高越好 | 赚钱能力强 |
| 动量 Momentum | 60日涨幅 | 越高越好 | 趋势强 |
| 规模 Size | 市值 | 越小越好 | 小市值溢价 |

本策略把这四类因子各取一个代表，合成综合打分，选"**又好又便宜、趋势向上且盘子不大**"的股票。

## 二、z-score 标准化：让不同量纲的因子可比

这是从策略6"排名法"升级到"打分法"的关键一步。

**问题**：ROE 是百分数（如 15%）、市值是亿元（如 200 亿）、动量是百分比（如 0.08），数值范围差异巨大，直接相加会导致大数值因子主导一切。

**解决**：z-score 标准化把每个因子都变成"均值为 0、标准差为 1"的标准分布：

$$z = \frac{x - \mu}{\sigma}$$

- 转换后，某股票 z=1.5 表示"比平均高 1.5 个标准差"，各因子从此可比；
- z 值越大，说明该股票在这个因子上越突出。

```python
def zscore(series):
    return (series - series.mean()) / (series.std() + 1e-12)  # +1e-12 防止除以0
```

## 三、因子方向：用正负号统一

合成时，让所有因子"越大代表越好"：

```python
df['score'] = (
    zscore(df['roe'])            # 质量：越高越好 → 正号
    - zscore(df['pb_ratio'])     # 估值：越低越好 → 负号（取反后"低PB"变成高分）
    + zscore(df['momentum'])     # 动量：越高越好 → 正号
    - zscore(df['market_cap'])   # 规模：越小越好 → 负号
)
```

## 四、算法结构

```
每月第1个交易日 → rebalance
  ├─ 股票池：全市场 + 过滤 ST/退市/停牌/次新/涨跌停
  ├─ 查询三因子：pb_ratio / market_cap / roe → set_index('code')
  ├─ 计算第四因子：momentum（60日涨幅）
  ├─ 合并成一张 DataFrame，dropna
  ├─ 逐因子 z-score 标准化
  ├─ 按方向加权合成 score
  ├─ 按 score 降序取前 30 只
  └─ 换仓等权
```

## 五、函数详解

### 5.0 `df.set_index('code')` —— 必须记住的关键一步

`get_fundamentals` 返回的 DataFrame 索引是 0,1,2... 数字序号，**不是股票代码**。必须显式 `set_index('code')`，否则后续 `df['momentum'] = pd.Series(momentum)` 会因索引不对齐而全部变成 NaN（详见策略3的 3.3 节）。

```python
df = get_fundamentals(q, date=context.current_dt.date())
df = df.set_index('code')     # 【关键】之后 index 才是股票代码
```

### 5.1 一次查询多张表

`query` 里可以**同时**查 `valuation` 和 `indicator` 两张表的字段，`get_fundamentals` 会自动 join：

```python
q = query(
    valuation.code, valuation.pb_ratio, valuation.market_cap,  # 估值表
    indicator.roe                                              # 财务指标表
).filter(valuation.code.in_(pool))
```

返回的 DataFrame 同时包含所有字段，索引为股票代码。这是多因子策略最常用的查询方式。

### 5.2 把字典因子并入 DataFrame

动量因子是用循环算出来的字典，需要并入 DataFrame：

```python
df['momentum'] = pd.Series(momentum)
```

`pd.Series(dict)` 会把字典的 key 作为索引。由于 `df` 的索引也是股票代码，二者自动对齐；某只股票在字典里没有值会填入 NaN，随后用 `dropna` 统一剔除。

### 5.3 综合分与选股

```python
target = df.sort_values('score', ascending=False).index[:g.stock_num].tolist()
```

按 `score` 列降序，取前 30 只的索引（股票代码）。相比策略6的"排名相加"，z-score 打分法**保留了因子的幅度信息**（不止看先后，还看领先多少）。

## 六、回测说明

**回测参数（建议）：** 区间 2016-01-01 ～ 2026-01-01，初始资金 100 万，月度调仓，基准沪深300。

**关注指标：** 年化收益、最大回撤、夏普；与各单因子策略对比，观察多因子是否在**收益风险比**上更优。

**如实说明：** 需在聚宽平台运行获取真实数据。风险提示：
- **等权合成**隐含"四因子同等重要"，但实际有效性差异很大（见策略9 IC 加权）；
- z-score 对**极端值敏感**（一个超大离群值会拉偏均值/标准差），进阶应做去极值（Winsorize）；
- 因子之间可能**高度相关**（如市值与 PB 相关），简单相加会重复计权（见策略8中性化）。

## 七、改进方向

1. **因子中性化**：剔除因子间的风格暴露，得到更"纯"的因子（见策略8）；
2. **因子加权**：用历史 IC/IR 给因子分配不同权重（见策略9）；
3. **去极值 + 标准化**：用中位数/分位数截尾（Winsorize）替代简单 z-score，更稳健。
