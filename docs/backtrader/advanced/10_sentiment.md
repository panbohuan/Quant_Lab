# 进阶 10：量价情绪代理策略（Sentiment Proxy）· backtrader 本地版

> **策略类型**：另类数据 / 情绪分析（代理变量） ｜ **难度**：★★★★★ ｜ **前置知识**：读完策略 7/8 再看这一篇
> **运行**：`python strategies/backtrader/advanced/bt_a10_sentiment.py` ｜ **聚宽版**：[10_sentiment.md](../../joinquant/advanced/10_sentiment.md)
> **语法底座**：[backtrader详解.md](../../learning/2.库详解/backtrader详解.md) 第 10 章

---

## 一、这一篇你将学到什么

真正的"舆情情绪"要用**新闻/股吧文本**。但免费源拿不到干净的新闻历史——于是这一篇教你**用"量价"当情绪的代理变量**。

| 你会搞懂 | 一句话 |
|---|---|
| 什么是**代理变量（proxy）** | 拿不到 A，就用与 A 高度相关的 B 代替 |
| 三个情绪代理 | 量能异常、波动放大、隔夜跳空 |
| 为什么用"代理" | 免费新闻文本拿不到，量价数据却人人都有 |
| 情绪因子的两面性 | 情绪高可能继续涨（追涨），也可能已过热（反转） |
| 标准化后再相加 | 三个量纲不同的指标要先 z-score |

**读完你应该能回答**：为什么"成交量突然放大"可以被当成"情绪升温"的代理？

---

## 二、心智模型：用量价数据"猜"情绪

```
每月调仓（收盘后）
   │
   ├─ 1. 对每只票算三个情绪代理（都是最近 5 天的）：
   │        vol_ratio 量能异常  = 近 5 日均量 ÷ 近 60 日均量
   │        amp       波动放大  = 平均 (最高 − 最低) ÷ 收盘
   │        gap       隔夜跳空  = 平均 |开盘 ÷ 昨收 − 1|
   │
   ├─ 2. 情绪分 = z(vol_ratio) + z(amp) + z(gap)      ← 三个都是"越大越热"
   │
   ├─ 3. 综合分 = z(情绪分) + z(20 日动量)             ← 情绪 + 动量
   │
   └─ 4. 取综合分最高的 10 只 → 等权买入 → 次日开盘成交
```

**为什么这三个能代表"情绪"？**

| 代理 | 现实含义 |
|---|---|
| 量能异常（放量） | 突然有很多人关注/交易 → 情绪升温 |
| 波动放大（振幅大） | 多空分歧加剧、情绪激动 |
| 隔夜跳空 | 消息面冲击、隔夜情绪延续 |

---

## 三、核心思路

**情绪因子（Sentiment）** 的核心假设：**价格会受群体情绪驱动，短期偏离基本面。**

**为什么要用"代理变量"？**

| 想要的 | 现实 | 替代方案 |
|---|---|---|
| 新闻/股吧情绪分 | 需要文本数据 + NLP，免费源没有干净历史 | **用量价数据构造代理** |

这是量化研究里极常见的做法：**拿不到你要的东西，就用"和它高度相关、又容易拿到"的东西代替**——但必须承认代理是近似的。

**情绪为什么必须和动量结合？**

因为情绪有**两面性**：

| 情形 | 可能的结果 |
|---|---|
| 情绪高 + 还在涨 | **追涨**有效（羊群效应） |
| 情绪高 + 已涨太多 | **过热反转**（情绪见顶） |

**单用情绪因子方向不明**，所以本策略把"情绪"和"动量"**同号相加**（都取"越大越好"）——用动量来判断"这个情绪是启动还是过热"。

> **⚠️ 本策略的诚实说明**：这是"**量价情绪代理版**"，不是真正的舆情分析。它没有用到任何新闻、研报、股吧文本。真正的舆情策略需要接入文本数据源（那通常是付费的）。

---

## 四、算法结构

```
main() → load_index_members → load_universe → __CAL__ → run_strategy
   │
   └─ SentimentProxy.on_rebalance(cur)（每月）
         ├─ 对每只票：_sentiment(d) → (vol_ratio, amp, gap)
         ├─ 同时算 20 日动量 mom
         ├─ 汇总成 DataFrame：行=股票，列=四个指标
         ├─ sentiment = z(vol_ratio) + z(amp) + z(gap)
         ├─ score = z(sentiment) + z(mom)
         └─ 取前 10 → equal_weight_order()
```

---

## 五、代码逐段详解

### 5.1 参数与三个窗口

```python
SHORT_WIN = 5               # 情绪观测窗口（短）
LONG_WIN = 60               # 情绪基准窗口（长）
LOOKBACK = 20               # 动量回看期
TOPN = 10
```

**为什么需要"短窗 + 长窗"？** 因为情绪的本质是"**异常**"——不是看"成交量多少"，而是看"**比平时多了多少**"。所以要拿近 5 天和近 60 天比。

### 5.2 三个情绪代理

```python
def _sentiment(self, d):
    closes = self.hist_close(d, self.p.lookback + 1)
    highs, lows = d.high.get(size=SHORT_WIN), d.low.get(size=SHORT_WIN)
    opens, vols = d.open.get(size=SHORT_WIN), d.volume.get(size=LONG_WIN)
    if (closes is None or closes[0] <= 0 or len(highs) < SHORT_WIN
            or len(opens) < SHORT_WIN or len(vols) < LONG_WIN):
        return None

    prev_close = closes[-(SHORT_WIN + 1):-1] if len(closes) > SHORT_WIN else None
    if prev_close is None or len(prev_close) < SHORT_WIN:
        return None

    amp = float(np.mean([(highs[i] - lows[i]) / closes[-1] for i in range(SHORT_WIN)]))
    gap = float(np.mean([abs(opens[i] / prev_close[i] - 1.0) for i in range(SHORT_WIN)]))
    vol_ratio = float(np.mean(vols[-SHORT_WIN:]) / (np.mean(vols) + 1e-9))
    return vol_ratio, amp, gap
```

逐行拆解：

| 行 | 说明 |
|---|---|
| `closes = hist_close(d, 21)` | 21 个收盘价（用于算 20 日动量 + 取昨收） |
| `highs/lows/opens = d.xxx.get(size=5)` | 最近 5 个交易日的最高/最低/开盘（**array**） |
| `vols = d.volume.get(size=60)` | 最近 60 个交易日的成交量 |
| 那一长串 `if ...: return None` | **数据不足就返回 None**（新股、数据缺失） |
| `prev_close = closes[-6:-1]` | 取"最近 5 天各自的昨收"（切片不含最后一个元素） |
| `amp` | 平均振幅。**分母用 `closes[-1]`（今天的收盘）是简化**——严格应该用当天的收盘 |
| `gap` | 平均跳空幅度（绝对值，不管上下方向） |
| `vol_ratio` | 近 5 日均量 ÷ 近 60 日均量（`+1e-9` 防除零） |

> **关于 `amp` 的简化**：代码里用同一个 `closes[-1]` 做分母，而不是"当天收盘"，这会让振幅的绝对数值略有偏差，但**排序结果基本不受影响**（因为所有股票用的是同一天的收盘做基准）。这属于"工程上可接受、学术上不严谨"的取舍。

### 5.3 合成得分

```python
def on_rebalance(self, cur):
    rows = {}
    for d in self.tradables:
        if not self.live(d, cur):
            continue
        sent = self._sentiment(d)
        if sent is None:
            continue
        closes = self.hist_close(d, self.p.lookback + 1)
        mom = closes[-1] / closes[0] - 1.0
        rows[d._name] = {'vol_ratio': sent[0], 'amp': sent[1], 'gap': sent[2], 'mom': mom}
    if len(rows) < self.p.topn:
        return

    df = pd.DataFrame(rows).T                    # 行=股票，列=指标
    sentiment = (zscore(df['vol_ratio']) + zscore(df['amp']) + zscore(df['gap']))
    score = zscore(sentiment) + zscore(df['mom'])     # 情绪 + 动量
    names = score.sort_values(ascending=False).index[:self.p.topn].tolist()
    self.equal_weight_order(names, cur)
```

| 代码 | 作用 |
|---|---|
| `pd.DataFrame(rows).T` | 把 `{股票: {指标: 值}}` 转成"行=股票、列=指标"，方便做截面运算 |
| `zscore(...)` × 3 再相加 | **必须先标准化**：量比（约 1.0）、振幅（约 0.03）、跳空（约 0.01）量纲完全不同 |
| `zscore(sentiment) + zscore(df['mom'])` | 情绪分和动量**再各自标准化**后等权相加 |
| `ascending=False` | 越大越好（情绪高 + 动量强） |

> **注意**：`sentiment` 本身是三个 z-score 之和，它已经是无量纲的；但它的**波动幅度**可能和 `mom` 差很多，所以代码**又做了一次 z-score** 再相加。这是"两层标准化"，属于谨慎做法。

---

## 六、一次真实运行的轨迹

```
[btlab] 股票池：候选 40 只 → 数据可用 38 只
[3/3] 开始 backtrader 回测 ...
（每月调仓，无打印）
```

想看"情绪分最高的长什么样"，加一行：

```python
top = score.sort_values(ascending=False).head(3)
print(f'  [{cur}] 情绪+动量最强：{list(top.index)}')
print(f'        情绪分={sentiment[top.index[0]]:.2f} 动量={df["mom"][top.index[0]]:+.1%}')
```

**你会观察到一个现象**：入选的常常是**刚放量上涨**的股票——这既是这个因子的威力，也是它的风险（追高）。

---

## 七、与聚宽版的差异

| 维度 | 聚宽（原版） | 本地版 |
|---|---|---|
| 数据 | **股吧/新闻情绪打分** | **量价代理**（无文本数据） |
| 因子 | 真实情绪分 | vol_ratio + amp + gap |
| 方向 | 情绪可能正向也可能反向 | 与动量同向（越大越好） |
| 降级原因 | —— | 免费源没有干净的新闻历史 |

---

## 八、回测结果怎么读

| 指标 | 数值 | 怎么理解 |
|---|---|---|
| 累计收益率 | **+176.65%** | 不错 |
| 年化收益率 | **+9.40%** | —— |
| 最大回撤 | **−49.17%** | ⚠️ 接近腰斩 |
| 夏普比率 | **0.46** | 一般 |
| 成交笔数 | 2060 | 月频，换手很高 |

**要点：**

1. **收益尚可、回撤偏大**：−49.17% 说明"追情绪"在情绪退潮时会集中受伤；
2. **它其实是"情绪 + 动量"的组合**：很难分清收益里有多少来自情绪代理、多少来自动量；
3. **代理是近似的**：量价能反映"关注度"，但不能区分"利好还是利空"——**真情绪因子应该能分辨方向**；
4. **换手 2060 笔**：情绪指标波动快，导致持仓频繁变化。

> **教学价值**：这一篇教你 **"拿不到数据时怎么办"**：用代理变量是可行路径，但必须**明确说明代理是什么、它漏掉了什么**（这里漏掉的是"情绪的方向"）。

---

## 九、易混点与常见错误

| 症状 | 原因 | 正确做法 |
|---|---|---|
| 三个指标直接相加 | 量纲不同（1.0 vs 0.01） | 先各自 z-score |
| `prev_close` 取错 | 切片边界搞错 | `closes[-(5+1):-1]` 取"最近 5 天的昨收" |
| 数据不足报错 | 新股/停牌股数据短 | `if ...: return None` |
| 以为这是"真舆情" | 用的是量价代理 | 明确标注是代理版 |
| 回撤大 | 追高情绪股 | 加估值/质量过滤，或设置止损 |

---

## 十、自测题（不写代码也能做）

1. 为什么"成交量放大"能当"情绪升温"的代理？这个代理漏掉了什么信息？
2. 为什么要"两层标准化"（三个代理先 z-score，情绪分和动量再 z-score）？
3. 这个策略的回撤（−49.17%）主要来自什么情形？

---

## 十一、改进方向（思考题）

1. **加情绪方向**：用"涨跌方向 × 情绪强度"区分利好放量和利空放量。
2. **接入真文本**：用新闻/股吧数据做 NLP 情绪打分（需要付费数据源或自己爬取）。
3. **情绪反转**：把情绪分取负号，测试"情绪过热 → 反转"是否更有效。
4. **降换手**：情绪指标变化快，可以加"排名掉出前 15 才卖"的缓冲带。