# 进阶策略 5：低价可转债轮动（Convertible Bond）· backtrader 本地版

> 类型：跨品种 / 可转债 ｜ 难度：★★★★☆
> 前置知识：`listed_bonds` / `load_bond_daily` / `bond_symbol`、`PanelStrategy`、MIN_COVERAGE 覆盖率
> **运行框架：backtrader（本地回测 + 免费数据）** ｜ 聚宽云端版（真实双低）见 [docs/joinquant/advanced/05_convertible_bond.md](../../joinquant/advanced/05_convertible_bond.md)

## 一、核心思路

可转债 = 债券 + 看涨期权：股价不涨，至少还本付息（下有保底）；股价大涨，可转股跟着赚（上不封顶）。

经典「双低」挑"价格低 + 转股溢价率低"的品种：

```
双低值 = 转债价格 + 转股溢价率(%)
双低值越小越"便宜"
```

**本地版为什么只做"低价"？** 转股溢价率的历史序列在免费源里拿不到——`listed_bonds`
的 `premium` 字段是**当前时点快照**。把"今天的溢价率"拿去给 2019 年的每一天排序，就是
用未来信息（未来函数），回测会虚高。所以本地版只用可得的历史价格：选价格最低的 TOPN
只，等权持有。想要真正的双低，请用聚宽版，或接入能回放历史溢价率的数据源。

参数一览（文件顶部常量）：

| 参数 | 默认值 | 含义 |
|------|--------|------|
| `START` / `END` | `2019-01-01` / `2025-06-30` | 固定区间（数据可靠性限制） |
| `CASH` | `1_000_000` | 初始资金 100 万 |
| `MAX_CANDIDATES` | `60` | 按发行规模取前 60 只作候选池 |
| `MIN_COVERAGE` | `0.50` | 数据覆盖度下限（区间交易日 × 50%） |
| `TOPN` | `5` | 持有价格最低的 5 只 |

## 二、算法结构（分步拆解）

```
main() → build_bond_universe()：listed_bonds 取前 N 大发行规模
   │
   ├─ 对每只：load_bond_daily，覆盖度 >= MIN_COVERAGE 才入选
   └─ run_strategy() 启动回测
         └─ 每月 on_rebalance(cur)
               ├─ 1. 遍历 tradables：live(d,cur) 且 price>0 才参与
               ├─ 2. 按现价升序取前 topn 只
               └─ 3. equal_weight_order(target, cur) 等权调仓
```

## 三、代码逐段详解 + backtrader 语法解析（本篇重点：可转债数据）

### 3.0 数据源 API：`listed_bonds` / `load_bond_daily` / `bond_symbol`

| 函数 | 返回 | 说明 |
|------|------|------|
| `listed_bonds(before, top, min_size)` | `DataFrame([bond_code, bond_name, list_date, price, conv_price, premium, issue_size, rating])` | `before` 前上市的可转债，按发行规模降序；`price` / `premium` 都是**当前快照**，只用于建候选池 |
| `load_bond_daily(code, start, end)` | `DataFrame[open,high,low,close,volume]` | 单只转债日线（新浪，上市日起） |
| `bond_symbol(code)` | `str` | 转债代码归一化：沪市 `11x/113/118` → `sh`，深市 `123/127/128` → `sz` |

### 3.1 可转债代码规范化 `bond_symbol`

```python
data[bond_symbol(code)] = df
```

喂数据与策略取数必须同名：`adddata(name=归一化名)`，策略里 `getdatabyname` 才能对上。
转债号段与股票不同，所以需要单独的函数（`normalize_code` 不适用）。

### 3.2 候选池与覆盖率门槛 `MIN_COVERAGE`

```python
table = listed_bonds(before=START, top=MAX_CANDIDATES)   # 上市早于 2019 的 Top60
df = load_bond_daily(code, start=START, end=END)
if len(df) < total_days * MIN_COVERAGE:
    continue                                             # 数据太稀 → 剔除
```

覆盖率 = 实际可用交易日 / 区间交易日。低于门槛的转债直接剔除，避免"数据断层"被误判
成"价格没变"。注意 `listed_bonds` 用的是**当前还存续**的转债，天然带幸存者偏差。

### 3.3 为什么不用静态溢价率（本篇最重要的一课）

数据可得性会直接改变策略的定义。免费源只有"当前"溢价率：

- 把它当历史值用 → 未来函数，回测虚高；
- 想在回测里每天更新 → 需要历史溢价率，免费源没有；
- 结论：本策略**只用历史价格**。

"先问数据能不能支持，再谈策略"是量化里很常见的一步。这个取舍本身，就是本篇想教的。

### 3.4 `on_rebalance` 与索引方向

```python
for d in self.tradables:
    if not self.live(d, cur):      # 停牌 / 未上市 → 跳过
        continue
    price = d.close[0]             # [0]=当根收盘，[-1]=昨天，[1]=未来（禁用）
```

`self.live(d, cur)` 保证只用当天真实有行情的转债；全程不出现 Line 正索引。

### 3.5 未建模的两个真实细节（诚实提示）

- **T+0 未建模**：可转债实行 T+0，日内可反复交易；本策略按日线月度调仓，无法刻画日内回转。
- **强赎条款未触发**：股价大涨触发强制赎回时，转债上涨空间被封顶，并非真"上不封顶"。

真实双低的收益与回撤会与本回测有偏差，引用数字时要心里有数。

## 四、与聚宽版的差异

| 维度 | 聚宽云端版 | backtrader 本地版 |
|------|-----------|-------------------|
| 因子 | **真实动态双低**（价格 + 历史溢价率） | **低价**（历史溢价率不可得，只用历史价格） |
| 转债列表 | `get_all_securities(types=['cb'])`（时点全市场） | `listed_bonds(before, top)`（当前存续池，幸存者偏差） |
| 覆盖度检查 | 平台保证数据完整 | 手动 `MIN_COVERAGE >= 50%` 剔除残缺标的 |
| 回测区间 / 持有数 | 平台设置 / 10 只 | 固定 2019-01-01 ~ 2025-06-30 / 5 只 |
| 触发方式 | `run_monthly(rebalance, 1)` | `PanelStrategy` 的 `(年,月)` 变化检测 |
| 下单口径 | `order_target_value(security, 市值)` | `equal_weight_order`（目标股数，整手） |

## 五、回测结果

> ⚠️ **待重跑**：4.1.1 已把本策略从"静态双低的双低版"改成"低价版"（去掉未来函数）。
> `results/logs/bt_a05_convertible_bond.log` 与 `results/bt_a05_result.png` 里的旧数字
> （累计 42.28% / 回撤 -9.83%）由**旧版本**跑出，不代表当前代码，重跑后再更新本节。

## 六、改进方向（思考题）

1. **还原动态溢价率**：接入能回放历史转股溢价率的数据源（正股历史价 + 历史转股价自算
   `溢价率 = 转债价 / 转股价值 - 1`），把"低价"升级回"真双低"。
2. **去幸存者偏差**：用区间时点的转债列表，纳入期间上市 / 退市的品种。
3. **叠加风控与博弈**：加"剩余规模小 / 可能下修"筛选提升弹性，并用止损防强赎前溢价率归零的回撤。
