# 策略 8：因子中性化选股（Barra 风格）

> 策略类型：多因子进阶（因子提纯） ｜ 难度：★★★★☆ ｜ 前置知识：策略7、线性回归基础

## 一、核心思路：为什么需要"中性化"

多因子选股最怕**因子之间相互污染**。举个例子：

- 动量因子（过去涨幅）在 A 股里，**小盘股的动量往往更强**——于是"按动量选股"实际上很大程度是在"按小市值选股"；
- 估值因子（PB）里，**银行股天然 PB 很低**——"按低 PB 选股"可能选出清一色银行股，等于赌单一行业。

**中性化（Neutralization）** 的目的：把某个因子里"被市值、行业等风格变量解释掉的部分"剔除，留下**该因子独有的、未被风格污染的信号**（称为 alpha 残差）。这是 Barra 等专业风险模型的核心思想。

## 二、数学原理：截面回归取残差

对每个调仓日，在"横截面"上做一次回归：

$$factor_i = \alpha + \beta_1 \cdot \log(cap_i) + \sum_k \gamma_k \cdot I(industry_i = k) + \varepsilon_i$$

- 自变量：对数市值 `log(cap)` + 行业哑变量；
- 因变量：原始因子 `factor`；
- **残差 `ε_i`** 就是"剔除了市值和行业影响后的纯因子"——它衡量的是"在同样市值、同行业里，这只股票的因子值相对高多少"。

选股时按残差排序，就得到了**市值中性、行业中性**的组合。

## 三、算法结构

```
每月第1个交易日 → rebalance
  ├─ 股票池：全市场 + 过滤 ST/退市/停牌/次新/涨跌停
  ├─ 查市值 → set_index('code') → 算对数市值 log_cap
  ├─ 查行业 get_industry → 申万一级行业
  ├─ 算原始因子（动量）
  ├─ 截面回归：因子 ~ log_cap + 行业哑变量
  ├─ 取残差作为纯因子 alpha
  ├─ 按 alpha 降序取前 30 只
  └─ 换仓等权
```

## 四、函数详解

### 4.0 `df.set_index('code')` —— 必须记住的关键一步

`get_fundamentals` 查市值返回的 DataFrame 索引是 0,1,2... 数字序号，**不是股票代码**。必须显式 `set_index('code')`，否则后续 `df['factor'] = pd.Series(momentum)` 会因索引不对齐而全部变成 NaN（详见策略3的 3.3 节）。

```python
df = get_fundamentals(q, date=context.current_dt.date())
df = df.set_index('code')     # 【关键】之后 index 才是股票代码
```

### 4.1 `get_industry(security, date)` —— 查询股票所属行业

```python
info = get_industry('600519.XSHG', date='2025-12-31')
# {'600519.XSHG': {'sw_l1': {'industry_code':'801120','industry_name':'食品饮料I'}, ...}}
```

- 支持传**股票列表**批量查询，返回以代码为 key 的字典；
- 每个股票包含多个分类体系：`sw_l1`（申万一级）、`sw_l2`、`zjw`（证监会）、`jq_l1`（聚宽一级）等；
- 我们取 `d['sw_l1']['industry_name']` 作为行业标签。

> 注意区分：`get_industry`（查**股票**属于什么行业）与 `get_industries`（查**行业列表**，返回行业代码与名称的 DataFrame）是两个不同函数，别混淆。

### 4.2 对数市值 `np.log`

市值分布极度右偏（从几亿到几万亿），直接回归会被大市值主导。**取对数**能压缩量级、让分布更接近正态：

```python
df['log_cap'] = np.log(df['market_cap'])
```

### 4.3 行业哑变量 `pd.get_dummies`

回归需要数值变量，但"行业"是分类变量，需转成**哑变量（0/1）**：

```python
industry_dummies = pd.get_dummies(df['industry'], drop_first=True)
```

- 每个行业生成一列 0/1（属于该行业为 1）；
- `drop_first=True` 丢弃第一个行业，避免"虚拟变量陷阱"（多重共线性）。

### 4.4 `statsmodels` 截面回归

```python
import statsmodels.api as sm
X = pd.concat([log_cap, industry_dummies], axis=1)
X = sm.add_constant(X)                # 加截距项
model = sm.OLS(factor, X).fit()       # 最小二乘回归
residual = model.resid                # 残差序列
```

- `sm.OLS(y, X).fit()`：y 是因变量（因子），X 是自变量矩阵；
- `model.resid` 返回每个样本的残差，索引与 `factor` 一致，可直接用于排序。

### 4.5 容错处理

回归可能因样本不足、行业过于集中等原因失败，所以用 `try/except` 兜底，失败时降级为原始因子，保证策略不会因单期异常而中断：

```python
try:
    df['alpha'] = neutralize(...)
except Exception as e:
    df['alpha'] = df['factor']   # 降级
```

## 五、回测说明

**回测参数（建议）：** 区间 2016-01-01 ～ 2026-01-01，初始资金 100 万，月度调仓，基准沪深300。

**关注指标：** 年化收益、最大回撤、夏普，以及**行业/市值暴露是否更均衡**（可对比持仓的行业分布与市值分布，中性化后应更分散）。

**如实说明：** 需在聚宽平台运行获取真实数据。风险提示：
- 中性化**不保证更高收益**，它的价值在于**降低风格集中风险、让因子更纯粹**；
- 中性化会"吃掉"一部分收益（把小市值、行业等本身也有效的暴露剔除），需要权衡；
- `get_industry` 依赖的行业分类可能有**历史调整**（申万行业会重分类），回测早期数据需留意。

## 六、改进方向

1. 中性化的自变量还可以加入 **beta（市场暴露）**、流动性等其他风格；
2. 中性化后再做**标准化**，然后多因子合成（中性化 + 打分法结合）；
3. 用**更稳健的回归**（如去极值后的稳健回归）替代普通 OLS。
