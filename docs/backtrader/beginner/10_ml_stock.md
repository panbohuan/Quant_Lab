# 策略 10：机器学习选股（ML Stock）· backtrader 本地版

> 策略类型：机器学习选股（监督学习 · 二分类） ｜ 难度：★★★★★ ｜ 前置知识：策略 7 的特征工程、sklearn RandomForest、标签构造、滚动训练
> **运行框架：backtrader（本地回测 + 免费数据）** ｜ 本策略的**聚宽云端版**见 [docs/joinquant/beginner/s10_ml_stock.md](../../joinquant/beginner/10_ml_stock.md)

## 一、核心思路

把"因子选股"抽象成监督学习问题：用历史量价特征预测"未来 N 日是否上涨"（二分类），训练随机森林，对当期股票预测上涨概率，买入概率最高的 K 只。

**特征设计（5 个量价特征）**：

| 编号 | 特征 | 计算 |
|------|------|------|
| 1 | 20 日动量 | `close_t / close_{t-20} - 1` |
| 2 | 60 日动量 | `close_t / close_{t-60} - 1` |
| 3 | 20 日波动率 | 近 20 日日收益率 std |
| 4 | 均线偏离度 | `close_t / MA60 - 1` |
| 5 | 量比 | 近 5 日均量 / 近 60 日均量 |

**标签设计**：未来 20 个交易日收益率 > 0 → 1（上涨），否则 0。

综合分即模型输出的"上涨概率" `proba[:,1]`，取最高的 TOPN 只等权持有。

> 给新手的直觉：把选股看成"考试预测"——历史上有很多"考生档案（特征）+ 后来成绩（标签）"的样本，随机森林从里面学出规律，再对今年这批考生预测谁会及格，挑预测及格概率最高的买。

## 二、算法结构（分步拆解）

```
每月首个交易日触发 on_rebalance(cur)
   │
   ├─ 1. _label_pending()：确认上一批样本的标签（时序纪律）
   │      └─ 若 len(d)-bars0 >= HORIZON(20)：p1=d.close[0]，标签=涨/跌
   │
   ├─ 2. 收集本期每只股票的特征 _features(d) + 当期价 d.close[0]
   │
   ├─ 3. 训练 + 预测
   │      ├─ 样本充足(≥400 且两类都有)：RandomForest 训练 → predict_proba 取上涨概率
   │      └─ 样本不足：用 20 日动量兜底（等价于因子选股）
   │
   ├─ 4. 登记本期样本进 self.pending（等 20 个交易日后再打标签）
   │
   └─ 5. equal_weight_order(上涨概率最高的前 TOPN 只, cur)
```

## 三、代码逐段详解 + backtrader 语法解析

### 3.1 状态与参数

```python
class MLStock(PanelStrategy):
    params = (('topn', TOPN), ('horizon', HORIZON), ('rebalance', 'monthly'),
              ('min_samples', MIN_SAMPLES),)

    def __init__(self):
        super().__init__()
        self.X, self.y = [], []     # 训练特征 / 标签累积列表
        self.pending = []          # 已收集特征、等待标签确认的样本
        self.model = None
```

`HORIZON=20`（预测窗口）、`MIN_SAMPLES=400`（训练样本下限）。状态 `X/y` 是扩张的训练集，`pending` 是"特征已采、标签未到"的样本队列——这是滚动训练避免未来函数的核心数据结构。

### 3.2 特征工程 `_features`

```python
def _features(self, d):
    c20 = self.hist_close(d, 21)
    c60 = self.hist_close(d, 61)
    if c20 is None or c60 is None:
        return None
    if c60[0] <= 0 or min(c60) <= 0:
        return None
    vols = d.volume.get(size=61)                 # list，近 61 根成交量
    if len(vols) < 61:
        return None
    rets = pd.Series(c20, dtype=float).pct_change().dropna()
    return [
        c20[-1] / c20[0] - 1.0,                  # 20 日动量（list[-1]=最新）
        c60[-1] / c60[0] - 1.0,                  # 60 日动量
        float(rets.std()),                        # 20 日波动率
        c60[-1] / (sum(c60) / len(c60)) - 1.0,   # 均线偏离度
        float(np.mean(vols[-5:]) / (np.mean(vols) + 1e-9)),  # 量比
    ]
```

要点与索引语义：

- `hist_close(d, 61)` 返回 list，需 61 根（含今日）才能算"60 日动量"，所以取 `lookback+1` 根。**序列语义**：`c20[-1]` 是最新收盘、`c20[0]` 是 21 天前，`c20[-1]/c20[0]-1` 即 20 日涨幅。
- `d.volume.get(size=61)`：`get()` 返回 **array**（`array.array`，**不是 list**；但索引语义同 list）（详见 `backtrader详解` §2.2），`vols[-5:]` 取最近 5 根，`vols` 整体取近 60 日均量，二者之比即量比。
- `min(c60) <= 0` 守卫排除停牌/异常价。`pct_change().dropna()` 算日收益率序列再取 std。
- 所有特征只用**已收盘的 K 线**（hist_close 长度守卫在内部），不偷看未来。

### 3.3 打标签 `_label_pending` —— 时序纪律

```python
def _label_pending(self):
    still = []
    for code, feats, p0, bars0 in self.pending:
        d = self.getdatabyname(code)
        if len(d) - bars0 >= self.p.horizon:       # 已过预测窗口，标签可确认
            p1 = d.close[0]                          # 当前价（Line 语义，当根）
            if p0 > 0 and p1 > 0:
                self.X.append(feats)
                self.y.append(1 if p1 / p0 - 1.0 > 0 else 0)
        else:
            still.append((code, feats, p0, bars0))
    self.pending = still
```

- `self.getdatabyname(code)`：按名字取回该标的的 Line 数据源（与 §5.4 一致）。
- `len(d)` 是该数据源已推进的 K 线总数；`bars0` 是登记样本时 `len(d)` 的值。`len(d) - bars0 >= 20` 表示"自登记起已过去至少 20 个交易日"——**标签此刻才确认**，绝不提前用未来收益。
- `p1 = d.close[0]`：Line 语义，当根收盘价（今天），与 list 的 `[-1]` 不同，这里的 `[0]` 才是"最新"。`p1/p0-1 > 0` 即未来 20 日上涨 → 标签 1。

### 3.4 `on_rebalance`：训练、预测、兜底、登记

```python
def on_rebalance(self, cur):
    self._label_pending()                       # 1) 先确认上批标签
    feats, price = {}, {}
    for d in self.tradables:
        if not self.live(d, cur):
            continue
        f = self._features(d)
        if f is None:
            continue
        feats[d._name] = f
        price[d._name] = d.close[0]
    if len(feats) < self.p.topn:
        return
    codes = list(feats)
    if len(self.X) >= self.p.min_samples and len(set(self.y)) > 1:
        self.model = RandomForestClassifier(
            n_estimators=200, max_depth=5, min_samples_leaf=20,
            random_state=42, n_jobs=-1)
        self.model.fit(self.X, self.y)
        proba = self.model.predict_proba([feats[c] for c in codes])[:, 1]
        order = [codes[i] for i in np.argsort(-proba)]
        names = order[:self.p.topn]
        top_p = max(proba)
    else:
        order = sorted(codes, key=lambda c: feats[c][0], reverse=True)
        names = order[:self.p.topn]             # 样本不足：20 日动量兜底
    for c in codes:
        self.pending.append((c, feats[c], price[c], len(self.getdatabyname(c))))
    self.equal_weight_order(names, cur)
```

- **滚动扩窗训练**：`self.X/self.y` 只增不减，每期把刚确认的标签样本追加进去，模型用"截至上月能观察到标签"的全部历史重训——从根上杜绝未来函数。日志显示前 13 个月（2016-05~2017-05）样本不足 400，用 20 日动量兜底；2017-06 起样本≥426 才启用 ML（最高上涨概率约 0.55~0.85）。
- **过拟合防护**：`max_depth=5, min_samples_leaf=20` 限制单棵树的复杂度，避免模型"记住噪声"。样本少时直接降级为动量因子，也是防过拟合的兜底。
- `predict_proba(...)[:, 1]` 取"正类（上涨）"概率；`np.argsort(-proba)` 降序排，取前 TOPN。
- 末尾把**本期样本**压入 `pending`，登记时记录 `len(getdatabyname(c))` 作为 `bars0`——下一期 `_label_pending` 用它与当前 `len(d)` 的差判断标签是否可确认。

### 3.5 防未来函数的三个手段

1. **滚动训练**：只用"标签已确认"的历史样本，`pending` 机制保证标签滞后 20 日；
2. **标签滞后确认**：`_label_pending` 用 `len(d)-bars0 >= HORIZON` 严格挡住未到期样本；
3. **只用已收盘数据**：`_features` 全靠 `hist_close` 长度守卫 + `d.close[0]` 当根价。

### 3.6 `PanelStrategy` 的月份调度与 `__CAL__` 时钟

"每月触发一次"由骨架完成（key 取 `(年, 月)`，`runner.py`），与前面策略一致。本策略的滚动训练对节奏极敏感：`pending` 里样本的"登记月"与 `_label_pending` 的"确认月"必须间隔 `HORIZON=20` 个交易日，靠 `len(d)-bars0` 精确计数，不依赖具体日期；而 `on_rebalance` 每月一次保证"采特征、登记、下月算 IC"的闭环稳定。同样，订单次日开盘成交，与"标签滞后 20 日"共同挡住未来函数。

## 四、与聚宽版的差异

| 维度 | 聚宽云端版（s10） | backtrader 本地版（bt_s10） |
|------|-------------------|------------------------------|
| 训练方式 | 一次性取全市场长窗口，遍历历史时点构造训练集 | **逐期滚动扩窗**：每月用"标签已确认"样本重训 |
| 标签时点 | `close.iloc[i+HORIZON]/close.iloc[i]-1`，向量化构造 | `pending` 队列 + `len(d)-bars0>=HORIZON` 逐样本确认 |
| 特征来源 | `history(total,'1d','close',pool)` 批量矩阵 | 逐标的 `hist_close` + `d.volume.get` |
| 触发/下单 | `run_daily` + `order_target_value` | `on_rebalance` + `equal_weight_order`（整手） |
| 股票池 | `get_index_stocks('000300')` 历史成分 | `load_index_members('000300')[:40]` 当前成分（幸存者偏差） |
| 调仓频率 | 每 20 个交易日 | 月度（`rebalance='monthly'`） |

**本地核心改动**：聚宽一次性拉全历史向量化造样本，本地改为"逐期滚动"，代价是前 13 个月样本不足只能动量兜底（日志明确标注），但从机制上更严谨。

## 五、回测结果（真实数据）

数据来源：`results/logs/bt_s10_ml_stock.log`（本地实跑，未编造）。

| 指标 | 数值 |
|------|------|
| 回测区间 | 2016-01-04 ~ 2026-09-30（2611 个交易日） |
| 初始 / 期末资金 | 100 万 → 4,800,745 元 |
| 累计收益率 | +380.07% |
| 年化收益率 | 16.35% |
| 基准（沪深300）累计 | +25.61% |
| 超额收益 | +354.46% |
| 最大回撤 | -33.65% |
| 夏普比率 | 0.83 |
| 年化波动率 | 20.86% |
| 日胜率 | 52.19% |
| 总成交笔数 | 2047 |
| 累计换手率 | 41735.48% |

**解读**：ML 选股年化 16.35%、夏普 0.83，跑赢沪深300 且波动最低（20.86%）；但注意**基准累计 +25.61%** 是因为本策略区间从 2016 年起（比 6~9 早两年），沪深300 在 2016–2026 累计其实涨了 25.6%，超额 +354% 仍可观。累计换手率高达 41735%——ML 每月全换仓、且候选池小，摩擦成本敏感度极高；前段动量兜底期收益贡献也需客观看待。

## 六、改进方向（思考题）

1. **加止损**：`equal_weight_order` 不做个股止损，可用 `self.buy_bracket` 给单票挂止损腿，压低 -33.65% 回撤。
2. **特征/标签优化**：当前仅 5 个量价特征，可加入估值/质量类（策略 7 的因子）做多源特征，并测试不同 `HORIZON`。
3. **缓解幸存者偏差**：本地用当前沪深300 成分，可改历史成分或更大股票池，并评估样本外（如近 3 年）表现，警惕过拟合。
