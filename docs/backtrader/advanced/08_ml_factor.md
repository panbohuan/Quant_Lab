# 进阶 8：机器学习因子合成（GBDT）· backtrader 本地版

> **策略类型**：机器学习进阶 / 因子合成 ｜ **难度**：★★★★★ ｜ **前置知识**：读完策略 10 再看这一篇
> **运行**：`python strategies/backtrader/advanced/bt_a08_ml_factor.py` ｜ **聚宽版**：[08_ml_factor.md](../../joinquant/advanced/08_ml_factor.md)
> **语法底座**：[backtrader详解.md](../../learning/2.库详解/数据分析与量化研究相关库/backtrader详解.md) 第 10 章

---

## 一、这一篇你将学到什么

策略 10 是**分类**（涨/不涨），这一篇是**回归**（预测收益率的数值），并且把基本面因子也喂给了模型。

| 你会搞懂 | 一句话 |
|---|---|
| 从分类 → 回归 | 标签从"是否上涨"改成"真实收益率" |
| 6 个混合特征 | 4 个量价 + 2 个基本面（PB、市值） |
| 特征要**分类型处理** | 量价本身可比；PB/市值要做**截面 z-score** |
| 梯度提升树（GBDT） | 比随机森林更适合小样本的回归任务 |

**读完你应该能回答**：为什么 PB 和市值不能直接喂给模型，而要先做截面标准化？

---

## 二、心智模型：让模型自己决定"因子怎么组合"

```
每月调仓（收盘后）
   │
   ├─ ① 给到期样本打标签（回归：真实收益率）
   │
   ├─ ② 收集本期 6 个特征：
   │      量价（原始值）：mom20、mom60、vol20、vol_ratio
   │      基本面（截面 z-score）：pb_z、logmv_z
   │
   ├─ ③ 样本 ≥ 400 → 训练 GBDT → 预测每只票的"预期收益"
   │      样本 < 400 → 兜底：按 20 日动量排序
   │
   ├─ ④ 登记本期样本到 pending
   └─ ⑤ 取预测收益最高的 10 只 → 等权买入 → 次日开盘成交
```

**和策略 7（手工加权）的区别**：

| | 策略 7 | 本篇 |
|---|---|---|
| 因子权重 | **人手定**（都写 1.0） | **模型学** |
| 组合方式 | 线性相加 | 非线性（树模型能捕捉交互） |
| 例子 | `z(roe) - z(pb) + z(mom) - z(mv)` | "低波动 **且** 高动量"才加分 |

---

## 三、核心思路

**为什么用回归而不是分类？**

- 分类（策略 10）只回答"涨不涨"，丢掉了"涨多少"的信息；
- 回归直接预测收益率，**信息更完整**，排序也更自然。

**为什么要"分类型处理特征"？**

| 特征类型 | 处理方式 | 原因 |
|---|---|---|
| 量价（动量/波动/量比） | **直接用** | 不同股票之间**天然可比**（都是"涨了 X%"） |
| 基本面（PB、市值） | **先做截面 z-score** | PB 的分布随时间变化（2018 年普遍 2 倍、2024 年普遍 1.2 倍），不做标准化模型会学到"时代"而不是"因子" |

代码里对应的就是这两行：

```python
pb_z, mv_z = zscore(pb_s), zscore(mv_s)      # 截面标准化（对当期所有股票）
```

> **什么是"截面 z-score"**：在同一天的所有股票之间做标准化 —— `(值 − 当日均值) ÷ 当日标准差`。这样得到的是"**相对位置**"，而不是绝对数值。

**为什么用 GBDT（梯度提升树）？**

| | 随机森林（策略 10） | GBDT（本篇） |
|---|---|---|
| 训练方式 | 并行建树、投票 | **串行建树、逐步纠错** |
| 小样本回归 | 一般 | **通常更好** |
| 过拟合风险 | 较低 | 需要调参（学习率/深度） |

---

## 四、算法结构

```
MLFactor(PanelStrategy)
  __init__:
      value_panel → self.pb, self.mv
      self.X, self.y = [], []      训练集（回归标签）
      self.pending = []
  _features(d, cur):   → 6 维特征字典
  _label_pending():    → moved ≥ 20 时用真实收益率打标签（连续值）
  on_rebalance(cur):
      ① _label_pending()
      ② 收集原始特征 raw
      ③ pb/mv → log → 截面 z-score
      ④ 拼成向量，喂 GBDT（样本 ≥ 400）或动量兜底
      ⑤ 登记样本到 pending
      ⑥ equal_weight_order(names)
```

---

## 五、代码逐段详解

### 5.1 特征构造

```python
FEATURE_NAMES = ['mom20', 'mom60', 'vol20', 'vol_ratio', 'pb_z', 'logmv_z']

def _features(self, d, cur):
    c20 = self.hist_close(d, 21)
    c60 = self.hist_close(d, 61)
    if c20 is None or c60 is None or min(c60) <= 0:
        return None
    vols = d.volume.get(size=61)
    if len(vols) < 61:
        return None
    rets = pd.Series(c20, dtype=float).pct_change().dropna()
    pb, mv = asof(self.pb, cur), asof(self.mv, cur)
    name = d._name
    row = (pb, mv) if (pb is not None and mv is not None
                       and name in pb.index and name in mv.index) else None
    return {
        'mom20': c20[-1] / c20[0] - 1.0,
        'mom60': c60[-1] / c60[0] - 1.0,
        'vol20': float(rets.std()),
        'vol_ratio': float(np.mean(vols[-5:]) / (np.mean(vols) + 1e-9)),
        'pb': float(row[0][name]) if row else np.nan,
        'mv': float(row[1][name]) if row else np.nan,
    }
```

**注意 `asof(self.pb, cur)`**：PB/市值是基本面数据，必须"只取已公布的最近一期"（和策略 7 一样）。

### 5.2 截面标准化 + 训练 + 预测

```python
codes = list(raw)

# 基本面特征做截面 z-score（量价特征本身已可比）
pb_s = pd.Series({c: raw[c]['pb'] for c in codes}, dtype=float)
mv_s = pd.Series({c: raw[c]['mv'] for c in codes}, dtype=float)
mv_s = np.log(mv_s.where(mv_s > 0))            # ← 市值先取对数
pb_z, mv_z = zscore(pb_s), zscore(mv_s)

vectors = []
for c in codes:
    f = raw[c]
    vectors.append([f['mom20'], f['mom60'], f['vol20'], f['vol_ratio'],
                    float(pb_z.get(c, np.nan)), float(mv_z.get(c, np.nan))])

if len(self.X) >= self.p.min_samples:
    self.model = GradientBoostingRegressor(
        n_estimators=150, max_depth=3, learning_rate=0.05,
        min_samples_leaf=20, subsample=0.8, random_state=42)
    self.model.fit(self.X, self.y)
    pred = self.model.predict(vectors)
    order = [codes[i] for i in np.argsort(-pred)]      # 预测收益从高到低
else:
    order = sorted(codes, key=lambda c: raw[c]['mom20'], reverse=True)
```

| 参数 | 作用 |
|---|---|
| `n_estimators=150` | 150 棵弱学习器 |
| `max_depth=3` | 树很浅 → **防过拟合**（GBDT 的树通常比 RF 更浅） |
| `learning_rate=0.05` | 每棵树只贡献一点点 → 更稳 |
| `subsample=0.8` | 每棵树用 80% 样本 → 增加随机性、防过拟合 |
| `min_samples_leaf=20` | 叶子至少 20 个样本 |
| `np.argsort(-pred)` | **负号 = 从大到小**（预测收益最高的排最前） |

### 5.3 标签：回归值而不是 0/1

```python
def _label_pending(self):
    for code, feats, p0, bars0, miss in self.pending:
        d = self.getdatabyname(code)
        moved = len(d) - bars0
        if moved >= self.p.horizon:
            p1 = d.close[0]
            if p0 > 0 and p1 > 0 and np.isfinite(feats).all():
                self.X.append(list(feats))
                self.y.append(p1 / p0 - 1.0)      # ← 连续值（回归标签）
```

**和策略 10 的唯一区别**：这里 `y` 是**收益率本身**（如 +7.3%），而不是 `1/0`。

> **`np.isfinite(feats).all()` 这一行的作用**：过滤掉含 NaN/inf 的样本。如果 PB 缺失（`np.nan`），这个样本就不能用来训练——否则 GBDT 会直接报错。

---

## 六、一次真实运行的轨迹

```
  预加载估值面板（PB / 市值）...
  模型特征重要性：mom20=0.24, mom60=0.17, vol20=0.21, vol_ratio=0.15, pb_z=0.12, logmv_z=0.11
  [2017-06-01] ML 因子合成（样本 426 条）预期收益最高 3.21%
```

**关键信息**：

- **特征重要性相对均匀**（0.11~0.24），说明模型没有把宝押在单一因子上；
- **没有哪个基本面因子占绝对主导**，这与"量价因子短期更重要"的直觉一致；
- **"预期收益最高 3.21%"** 是模型输出，不是承诺——它只是"在历史相似情形下的平均表现"。

---

## 七、与聚宽版的差异

| 维度 | 聚宽 | 本地版 |
|---|---|---|
| 模型 | 随机森林/XGBoost/神经网络 | GradientBoostingRegressor |
| 样本量 | 全市场（几千只 × 多年） | 40 只 × 月度（样本很少） |
| 训练 | 一次性全量 | **滚动扩窗**（时序更严格） |
| 兜底 | 无 | 样本 < 400 用动量 |

---

## 八、回测结果怎么读

| 指标 | 数值 | 怎么理解 |
|---|---|---|
| 累计收益率 | **+699.61%** | 全场第二（仅次于纯小市值 +783.63%） |
| 年化收益率 | **+22.22%** | —— |
| 最大回撤 | **−31.01%** | 与多因子相当 |
| 夏普比率 | **0.98** | 全场第二（仅次于小市值 1.19） |
| 成交笔数 | 1922 | 月频 |

**要点：**

1. **表现确实很好**（夏普 0.98），说明"让模型学权重"比"人拍脑袋定权重"（策略 7 夏普 0.82）更有效；
2. **但仍有前面的老问题**：股票池是当前成分股（幸存者偏差）、样本量小（40 只 × 月度）、区间特定；
3. **前 13 个月同样是动量兜底**，所以收益里混着动量的贡献；
4. **模型只能学到"历史规律"**：风格一变（比如小市值失效），它不会自动知道。

> **教学价值**：这一篇的定位是 **"把策略 7 的手工加权换成模型学习"**。对比两者的夏普（0.82 vs 0.98），你能直观看到"非线性 + 自动权重"的价值；同时也要看到它带来的**新风险：模型黑箱、样本不足、过拟合**。

---

## 九、易混点与常见错误

| 症状 | 原因 | 正确做法 |
|---|---|---|
| GBDT 报错含 NaN | 特征里有 `np.nan`（PB 缺失） | `np.isfinite(feats).all()` 过滤 |
| 预测值全都很接近 | 特征没标准化/量纲差异大 | 基本面做截面 z-score |
| 模型过拟合 | 树太深 / 学习率太高 | `max_depth=3`、`learning_rate=0.05` |
| 结果每次不同 | 没固定随机种子 | `random_state=42` |
| 特征重要性只反映模型 | 不代表因果 | 它只是"模型怎么用这些特征" |

---

## 十、自测题（不写代码也能做）

1. 为什么 PB/市值要做截面 z-score，而动量/波动率不用？
2. 回归标签（收益率）比分类标签（涨/跌）多保留了哪些信息？
3. 这一篇的夏普（0.98）比策略 7（0.82）高，能直接说明"机器学习更好"吗？还有哪些可能的解释？

---

## 十一、改进方向（思考题）

1. **换模型**：试 `RandomForestRegressor` 或 `XGBoost`，对比稳定性。
2. **加时序验证**：用 Purged K-Fold 评估模型，避免"用未来验证过去"。
3. **特征筛选**：用特征重要性做一轮筛选，减少噪声特征。
4. **加约束**：控制行业/市值暴露，避免模型学到"小市值"这一条捷径。