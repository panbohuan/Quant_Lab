# 策略 3：单因子低估值选股（PE / PB 估值因子）

> 策略类型：单因子选股（基本面·估值） ｜ 难度：★★☆☆☆ ｜ 前置知识：策略2框架、query/get_fundamentals

## 一、核心思路：价值投资与估值因子

价值投资的核心是**用低于内在价值的价格买入资产，等待价值回归**。衡量"便宜与否"最常用的两个指标就是估值因子：

### 1.1 市盈率 PE（Price-to-Earnings Ratio）

$$PE = \frac{\text{股价}}{\text{每股收益(EPS)}} = \frac{\text{总市值}}{\text{净利润}}$$

**含义**：投资者为每 1 元净利润愿意支付的价格。PE 越低，代表"回本"越快、估值越便宜。

- 直观理解：PE=10 意味着按当前盈利水平，10 年赚回本金；
- 为什么能辅助决策：市场情绪会把好公司炒到高 PE（透支未来），把暂时困境的公司打到低 PE（过度悲观）。**低 PE 组合本质上在赌"均值回归"——被低估的终将被重新定价**。学术上著名的"价值溢价（Value Premium）"即指低估值股长期跑赢高估值股。

### 1.2 市净率 PB（Price-to-Book Ratio）

$$PB = \frac{\text{股价}}{\text{每股净资产}} = \frac{\text{总市值}}{\text{净资产}}$$

**含义**：股价相对账面净资产的倍数。PB<1 俗称"破净"，代表股价低于公司账面价值。

- 为什么能辅助决策：净资产是"清算价值"的粗略代理，PB 越低安全边际越高；对**金融、周期、重资产行业**（银行、钢铁、地产）尤其有效，因为这些行业资产更实、利润波动大，用 PB 比 PE 更稳定。

> **PE 与 PB 的适用区别**：盈利稳定、成长型行业更适合 PE；周期/重资产行业更适合 PB。亏损公司 PE 无意义（为负），此时看 PB。

## 二、算法结构

沿用策略2的选股框架，唯一变化是**因子来源从"价格"换成了"财务报表"**：

```
每月第1个交易日 → rebalance
  ├─ 股票池：全市场 get_all_securities(['stock'])
  ├─ 过滤 ST / 停牌
  ├─ 查估值因子：query(valuation.pe_ratio, valuation.pb_ratio)
  ├─ 清洗：dropna + 剔除负值
  ├─ 按 PE 升序取前 30 只
  └─ 换仓：卖旧买新，等权
```

## 三、函数详解

### 3.1 `from jqdata import *` —— 导入数据模块

使用 `query`、`valuation`、`indicator` 等财务数据相关功能前，需要先导入。`jqdata` 是聚宽封装好的数据访问模块。

```python
from jqdata import *
```

### 3.2 `query(...)` + `get_fundamentals(...)` —— 财务数据查询（核心）

这是聚宽基本面数据的主入口，采用"**声明式查询**"语法：先用 `query` 声明"要查哪些表的哪些字段、如何过滤、如何排序"，再交给 `get_fundamentals` 执行。

```python
q = query(
    valuation.code,          # 字段1：代码
    valuation.pe_ratio       # 字段2：市盈率
).filter(
    valuation.code.in_(pool)          # 过滤：代码在 pool 里
).order_by(
    valuation.pe_ratio.asc()          # 排序：PE 升序
).limit(90)                            # 只取前90条

df = get_fundamentals(q, date='2025-12-31')
```

**返回结果**：一个 pandas DataFrame，**索引是股票代码**，列是你查询的字段。因此 `df.index` 就是选出的股票代码，非常方便。

### 3.3 常用财务数据表（table）

聚宽把财务数据分成多张"表"，每张表有不同字段。本系列会用到：

| 表名 | 含义 | 常用字段 |
|------|------|----------|
| `valuation` | 估值表（每日更新） | `pe_ratio`、`pb_ratio`、`ps_ratio`、`market_cap`（总市值）、`circulating_market_cap`（流通市值）、`turnover_ratio` |
| `indicator` | 财务指标表（季度） | `roe`、`roa`、`gross_profit_margin`、`inc_revenue_year_on_year`、`inc_net_profit_year_on_year` |
| `balance` | 资产负债表 | `total_assets`、`total_liability`、`asset_liability_ratio` |
| `income` | 利润表 | `total_operating_revenue`、`net_profit` |
| `cash_flow` | 现金流量表 | `net_operate_cash_flow` |

查询字段的语法：`表名.字段名`，如 `valuation.pe_ratio`、`indicator.roe`。

### 3.4 `get_fundamentals` 的 `date` 与 `statDate` 参数

- `date`：取**该日期**已披露的最新财务数据（配合每日更新的 valuation 表用）；
- `statDate`：取**某个报告期**（如 `'2024q4'`）的财务数据，适合季度指标（indicator/balance/income）。

```python
df = get_fundamentals(q, date='2025-12-31')        # 截至该日的最新数据
df = get_fundamentals(q, statDate='2024q4')        # 2024年第四季度报告数据
```

### 3.5 数据清洗

```python
df = df.dropna(subset=['pe_ratio'])   # 删除 PE 缺失的行
df = df[df['pe_ratio'] > 0]           # 只保留 PE 为正的行
```

**为什么必须剔除负 PE？** PE 为负代表净利润为负（亏损），此时 PE 越小反而意味着亏得越多，因子方向完全颠倒。这是估值因子最容易踩的坑，务必过滤。

## 四、回测说明

**回测参数（建议）：** 区间 2016-01-01 ～ 2026-01-01，初始资金 100 万，月度调仓，基准沪深300。

**关注指标：** 年化收益、最大回撤、夏普，以及**低估值策略的风格特征**——它在"价值风格"占优的年份（如 2016-2017、部分熊市）表现好，在成长风格牛市（如 2019-2021 核心资产、成长股行情）明显跑输，回撤周期可能较长。

**如实说明：** 需在聚宽平台运行获取真实数据。风险提示：
- **价值陷阱**：低 PE/PB 可能是公司基本面真的恶化，而非被错杀；
- 价值策略是典型的"长周期因子"，可能连续多年跑输成长风格，需要足够耐心；
- 财务数据存在**披露滞后**（财报季报通常滞后 1-4 个月），回测中要确认用的是当时已披露的数据。

## 五、改进方向

1. 把 PE 与 PB 结合成**综合估值分**（如等权或加权）；
2. 加**盈利质量过滤**：只买"低估值且 ROE 为正"的股票，规避价值陷阱（见策略5）；
3. 估值因子在不同行业不可直接比较，可做**行业内估值排名**（见策略8中性化）。
