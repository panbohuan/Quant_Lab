# 进阶策略 8：机器学习因子合成（ML Factor Combination）· backtrader 本地版

> 类型：机器学习进阶 / 因子合成 ｜ 难度：★★★★★ ｜ 前置知识：scikit-learn、滚动训练、PanelStrategy、asof
> **运行框架：backtrader（本地回测 + 免费数据）** ｜ 本策略的**聚宽云端版**见 [docs/joinquant/advanced/08_ml_factor.md](../../joinquant/advanced/08_ml_factor.md)

## 一、核心思路

前面 s07/a07 用手工线性加权把因子合成综合分。本策略让**模型自己学**「因子怎么组合才能预测收益」：用梯度提升回归树（GradientBoostingRegressor）把 6 个因子非线性地合成为一个「预期未来 20 日收益率」，再按预测值排序选股。

回归 vs 分类：聚宽版文档提到「随机森林分类（涨/跌）」，本策略用**回归**预测「涨多少」——信息量更大但也更难（回归对噪声更敏感）。

6 个特征分两类：

| 类别 | 特征 | 含义 |
|------|------|------|
| 量价 | `mom20` | 20 日动量（涨幅） |
| 量价 | `mom60` | 60 日动量 |
| 量价 | `vol20` | 20 日收益率标准差（波动） |
| 量价 | `vol_ratio` | 近 5 日均量 / 近 60 日均量（放量程度） |
| 基本面 | `pb_z` | PB 的截面 z-score |
| 基本面 | `logmv_z` | 对数市值的截面 z-score |

标签：**未来 20 个交易日的收益率**（连续值）。模型学到「什么样的因子组合预示高收益」，就用它给当期股票打分。

给新手的直觉：传统多因子是「我拍脑袋定权重」（ROE 给 0.3、动量给 0.2）；ML 因子是「让树模型从历史数据里自己找出权重和交互」，比如「低 PB 且放量时收益特别好」这种非线性规律。

## 二、算法结构（分步拆解）

```
每月第 1 个交易日触发 on_rebalance(cur)
   │
   ├─ 0. _label_pending()：确认「20 个交易日前登记」的样本标签（未来收益已落地）
   ├─ 1. 逐标的算 6 个特征（量价用 hist_close/volume.get；基本面用 asof(pb/mv)）
   ├─ 2. 截面 z-score 处理 pb / 市值 → 拼成特征向量 vectors
   ├─ 3. 若样本数 ≥ MIN_SAMPLES(400)：
   │      └─ GradientBoostingRegressor 训练 → predict(vectors) → 按预测收益降序取 TOPN
   │      否则：用 20 日动量兜底排序
   ├─ 4. 把本期 (code, 特征, 当时价, 当时bar数) 存入 self.pending
   └─ 5. equal_weight_order(names, cur)
```

## 三、代码逐段详解 + backtrader 语法解析

### 3.1 特征构造 `_features`（全是「已知」数据）

```python
c20 = self.hist_close(d, 21)          # 最近 21 个收盘价（list，最旧→最新）
c60 = self.hist_close(d, 61)
vols = d.volume.get(size=61)          # 成交量 Line.get → list（注意：list[-1] 是最新）
rets = pd.Series(c20).pct_change().dropna()
pb, mv = asof(self.pb, cur), asof(self.mv, cur)
return {
    'mom20': c20[-1] / c20[0] - 1.0,
    'mom60': c60[-1] / c60[0] - 1.0,
    'vol20': float(rets.std()),
    'vol_ratio': float(np.mean(vols[-5:]) / (np.mean(vols) + 1e-9)),
    'pb': float(row[0][name]) if ... else np.nan,
    'mv': float(row[1][name]) if ... else np.nan,
}
```

关键：`c20`/`vols` 来自 `hist_close`/`volume.get`，返回的是 **array（`array.array`）**，所以 `c20[-1]` = 当根（最新）、`c20[0]` = 21 根前（最旧）——这是 序列语义，与 backtrader Line 的 `[0]=当根、[-1]=昨天` 不同（base doc §2.2）。`vol_ratio` 用 `vols[-5:]`（最近 5 天）除以全段均值，衡量「近期是否放量」。

`pb`/`mv` 用 `asof(self.pb, cur)` 取「不晚于 cur」的最新估值——防未来函数（见 a07 第三节）。若某股当天没有估值（NaN）则留空，后面截面 z-score 时再处理。

### 3.2 滚动扩窗训练：标签滞后确认防未来（重点）

```python
def _label_pending(self):
    still = []
    for code, feats, p0, bars0 in self.pending:
        d = self.getdatabyname(code)
        if len(d) - bars0 >= self.p.horizon:        # 距登记已过去 ≥ 20 根
            p1 = d.close[0]                          # 当前（确认日）收盘价
            if p0 > 0 and p1 > 0 and np.isfinite(feats).all():
                self.X.append(list(feats))           # 特征（登记日已知）
                self.y.append(p1 / p0 - 1.0)         # 标签 = 真实 20 日收益
        else:
            still.append((code, feats, p0, bars0))
    self.pending = still
```

这是防未来函数的核心机制。`pending` 里存的是「登记时的特征 `feats`、登记时收盘价 `p0`、登记时的 bar 数 `bars0`」。只有等到 `len(d) - bars0 >= HORIZON(20)`（即 20 个交易日后），才用「当前收盘价 `p1`」算出标签 `p1/p0 - 1`：

- `p0` 是登记那一刻的收盘价（**过去已知值**），不是未来；
- `p1 = d.close[0]` 在确认日读取，是**确认日当根**，也不是未来；
- 标签在「20 根之后」才进入训练集，模型永远只用「标签已落地的历史样本」训练。

日志显示：2016-2018 年样本数从 0 缓慢累积到 400，2019-01 起样本达标（424 条）才开始用 ML 预测，之后样本逐月增长到 3714 条——这就是「滚动扩窗」：样本随月份单调增长。

### 3.3 训练与预测

```python
if len(self.X) >= self.p.min_samples:
    self.model = GradientBoostingRegressor(
        n_estimators=150, max_depth=3, learning_rate=0.05,
        min_samples_leaf=20, subsample=0.8, random_state=42)
    self.model.fit(self.X, self.y)
    pred = self.model.predict(vectors)
    order = [codes[i] for i in np.argsort(-pred)]
```

**防过拟合三板斧**（对应源代码注释）：浅树（`max_depth=3`，树越深越易记噪声）、叶子样本下限（`min_samples_leaf=20`）、特征少而稳定（6 个）。`subsample=0.8` 做行采样进一步正则化。固定一组保守超参，不做时序交叉验证搜参（避免过拟合）。

`model.feature_importances_` 给出特征重要性，日志首报：`mom20=0.21, mom60=0.16, vol20=0.14, vol_ratio=0.17, pb_z=0.23, logmv_z=0.10`——说明 PB 估值（0.23）和未来放量（vol_ratio 0.17）贡献最大。这是树模型相比线性模型的优势：**可解释性来自特征重要性**（线性模型看系数，树模型看重要性）。

样本不足 400 时退化为 `sorted(codes, key=mom20, reverse=True)`——用 20 日动量兜底，保证策略早期也能运行。

### 3.4 `equal_weight_order` 调仓

```python
names = order[:self.p.topn]
self.equal_weight_order(names, cur)
```

取预测收益最高的 TOPN 只等权买入（先清旧仓、再整手补齐，base doc §5.6 / runner.py）。

### 3.5 关键参数表

| 参数 | 默认 | 含义 |
|------|------|------|
| `UNIVERSE_SIZE` | 40 | 沪深300 前 40 只（幸存者偏差） |
| `TOPN` | 10 | 持有股票数 |
| `HORIZON` | 20 | 预测窗口（未来 20 交易日收益） |
| `MIN_SAMPLES` | 400 | 启动 ML 训练的最小样本数 |
| `FEATURE_NAMES` | 6 个 | 特征名（mom20/mom60/vol20/vol_ratio/pb_z/logmv_z） |

### 3.6 backtrader 索引方向速查（防未来函数，必记）

| 写法 | 含义 | 能否在回测中用 |
|------|------|----------------|
| `d.close[0]` | 当根收盘价（Line 索引） | ✅ |
| `d.close[-1]` | 上一根（昨天） | ✅ |
| `d.close[-2]` | 上上根（前天） | ✅ |
| `d.close[1]` | 下一根（明天） | ❌ 未来数据，禁用 |
| `d.volume.get(size=n)` 返回的 array | `[0]`=最旧、`[-1]`=最新（数组） | ✅（序列语义，与 Line 相反） |

本策略特征用 `c20[-1]/c20[0]-1`、`vols[-5:]`（`c20`/`vols` 来自 `hist_close`/`get` 返回的 array，`[-1]`=最新）；标签确认时用 `d.close[0]`（确认日当根）。两个易错点：**(1)** `line[1]` 是未来，禁用；**(2)** 首根 K 线 `[-1]` 会绕到数据集末尾（base doc §2.2），靠 `hist_close` 的 `len(d)<n` 判空挡住。

### 3.7 滚动扩窗：为什么标签必须「滞后确认」

若直接在调仓日算 `未来20日收益 = close[+20]/close[0]-1`，就用了 `line[+20]`（未来），是严重未来函数。本策略的解法（3.2 节 `_label_pending`）：调仓日只把「特征 + 当时价 `p0` + 当时 bar 数 `bars0`」存进 `self.pending`；等到 `len(d)-bars0 >= 20` 的下一次调仓，才用**那时**的 `d.close[0]` 当 `p1` 算标签。`p0` 是过去已知值、`p1` 是确认日当根，标签永远在「20 根之后」才进入训练集——模型只见过「标签已落地」的历史样本。这就是 Walk-Forward（滚动训练）防未来的标准写法。

### 3.8 树模型 vs 线性模型：因子合成的两类思路

- **线性合成**（s07/a07）：人工定权重，`score = Σ w_i·z_i`，权重是拍脑袋或规则给的，可解释但表达能力有限（假设因子间独立可加）。
- **树模型合成**（本策略）：`GradientBoostingRegressor` 自动学因子间的**非线性交互**（如「低 PB 且放量时收益特别高」），表达能力更强。可解释性来自 `feature_importances_`（线性模型看系数，树模型看重要性）。代价是更易过拟合，需 `max_depth=3`/`min_samples_leaf=20`/`subsample` 三板斧正则。

### 3.9 回测时序与 ML 因子常见坑

`on_rebalance(cur)` 在当根收盘后调用，`self.buy/sell` 默认**下一根开盘**成交（base doc §9.1），天然防未来。ML 因子坑：(1) **过拟合**——月频重训 + 40 只大池，样本内特征重要性稳定不代表样本外有效，需 Purged K-Fold 验证；(2) **换手成本**——回测累计换手率 45115%（见第五节），费率或冲击成本稍严苛收益就缩水；(3) **标签泄漏**——务必用 3.7 的滞后确认，切勿用 `line[+HORIZON]` 直接算标签。

## 四、与聚宽版的差异

| 维度 | 聚宽版 a08 | backtrader 本地版 |
|------|-----------|-------------------|
| 模型 | `RandomForestRegressor` | `GradientBoostingRegressor`（回归） |
| 标签 | **`np.random.rand` 随机占位**（教学桩，非真实收益） | **真实未来 20 日收益**，滚动确认防未来 |
| 预测目标 | 文档称「收益排名/概率」 | 连续收益率（回归幅度） |
| 特征 | 4 个（动/波/PE/ROE） | 6 个（加 vol_ratio、pb_z/logmv_z 截面标准化） |
| 训练方式 | 单期拟合（桩实现） | **逐月滚动扩窗**，标签滞后确认 |
| 触发/下单 | `run_monthly` + `order_target_value` | `PanelStrategy` + `equal_weight_order` 整手 |

**诚实说明（本例特有）**：聚宽版 a08 的标签是 `np.random.rand(len(X))` 占位（源码注释「真实应替换为历史收益」），它并未真正实现 Walk-Forward 训练。backtrader 版反而把聚宽文档里「描述但未实现」的真实滚动训练做了出来——所以本地的 ML 因子才是该思路的**忠实实现**，聚宽版更像教学脚手架。两者「回归 vs 分类」的对照仍成立：聚宽版文档讨论随机森林分类，本地用梯度提升回归。

> 幸存者偏差提示：同 a07，`load_index_members` 返回当前成分，回测用了「现在的龙头」填进历史。

## 五、回测结果（真实数据）

来源：`results/logs/bt_a08_ml_factor.log`（区间 2016-01-04 ~ 2026-09-30，2611 个交易日，初始资金 100 万）。

| 指标 | 数值 |
|------|------|
| 累计收益率 | 699.61% |
| 年化收益率 | 22.22% |
| 最大回撤 | -31.01% |
| 夏普比率 | 0.98 |
| 年化波动率 | 23.19% |
| 基准（沪深300）累计收益 | 25.61% |
| 超额收益 | 674.00% |
| 总成交笔数 | 1922 |
| 累计换手率 | 45115.23% |

解读：ML 因子是 5 篇里收益最高（累计 699%、夏普 0.98）、回撤最低（-31%）的策略，远超沪深300（基准仅 +25.6%）。但**累计换手率高达 45115%**——月频 + 40 只大池 + 模型每月重排，交易成本是最大隐忧；若费率假设更严苛或加入冲击成本，收益会明显缩水。高夏普也需警惕：样本内特征重要性稳定，但不代表样本外同样有效。

## 六、改进方向（思考题）

1. **严格样本外验证**：用 Purged K-Fold / 时序交叉验证调参，而非固定超参，检验是否过拟合。
2. **降低换手**：对预测收益排名做「调仓阈值」（仅当新组合与旧组合差异大才换），压低 45115% 换手。
3. **加止损/风控**：模型在 2018、2022 年仍可能连续踩雷，-31% 回撤可进一步用个股止损或市场择时压缩。
