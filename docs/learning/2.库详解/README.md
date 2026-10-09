# 库详解目录（第三方库完整说明）

本文件夹系统讲解量化学习中涉及的**第三方库**的定位、模块结构、核心函数、参数与用途，并给出量化场景中的应用示例。

按用途分成**两个子目录**：

| 子目录 | 收录原则 | 包含 |
|---|---|---|
| [机器学习相关库](机器学习相关库/) | 建模、训练、推理、向量检索 | scikit-learn、XGBoost、TensorFlow/Keras、ChromaDB、tiktoken |
| [数据分析与量化研究相关库](数据分析与量化研究相关库/) | 数据处理、可视化、科学计算、回测 | pandas、pandas 量化应用、Matplotlib、SciPy、backtrader |

> **先学哪个？** 做量化研究的顺序通常是：
> **pandas（数据）→ Matplotlib（看图）→ backtrader（回测）→ scikit-learn / XGBoost（建模）**。
> 只做策略、不做机器学习时，前三项就够用。

---

## 一、机器学习相关库

| 文档 | 库 | 定位 | 一句话说明 |
|------|-----|------|-----------|
| [sklearn详解.md](机器学习相关库/sklearn详解.md) | scikit-learn | 机器学习的"瑞士军刀" | 分类/回归/聚类/降维/预处理一站式，API 统一 |
| [xgboost详解.md](机器学习相关库/xgboost详解.md) | XGBoost | 梯度提升的工业级实现 | 因子筛选与合成，量化里高频使用 |
| [tensorflow_keras详解.md](机器学习相关库/tensorflow_keras详解.md) | TensorFlow / Keras | 深度学习框架 | 神经网络、LSTM、CNN、Transformer |
| [chromadb详解.md](机器学习相关库/chromadb详解.md) | ChromaDB | 向量数据库 | RAG 检索的核心组件（研报/公告知识库） |
| [tiktoken详解.md](机器学习相关库/tiktoken详解.md) | tiktoken | OpenAI 分词器 | 文本 ↔ Token 转换，估算 LLM 成本 |

## 二、数据分析与量化研究相关库

| 文档 | 库 | 定位 | 一句话说明 |
|------|-----|------|-----------|
| [pandas详解.md](数据分析与量化研究相关库/pandas详解.md) | pandas | 表格数据处理 | 量化策略里绕不开的核心库（基础教程） |
| [pandas量化应用.md](数据分析与量化研究相关库/pandas量化应用.md) | pandas（进阶） | 量化实战 | 收益率、滚动窗口、因子计算、IC、分层回测 |
| [matplotlib详解.md](数据分析与量化研究相关库/matplotlib详解.md) | Matplotlib | 数据可视化 | 画价格走势、因子重要性、收益分布 |
| [scipy详解.md](数据分析与量化研究相关库/scipy详解.md) | SciPy | 科学计算 | 优化、积分、层次聚类等算法 |
| [backtrader详解.md](数据分析与量化研究相关库/backtrader详解.md) | backtrader | **本地回测引擎** | 18 章教程 + 手册：从心智模型、逐行模板到 Cerebro / Strategy / 指标 / 分析器 / 费用滑点 / 聚宽对照 |

---

## 三、安装命令速查

```bash
# —— 数据分析与量化研究 ——
pip install pandas matplotlib scipy          # 数据处理 + 可视化 + 科学计算
pip install backtrader                       # 本地回测引擎（strategies/backtrader 的依赖）

# —— 机器学习 ——
pip install scikit-learn                     # 机器学习全家桶
pip install xgboost                          # 梯度提升
pip install tensorflow                       # 深度学习
pip install chromadb                         # 向量数据库（RAG）
pip install tiktoken                         # OpenAI 分词器
```

## 四、综合查询表：各库核心函数速查

| 库 | 函数/类 | 用途 | 所属模块 |
|----|---------|------|----------|
| backtrader | `bt.Cerebro` | 回测总控 | backtrader |
| backtrader | `bt.Strategy` | 策略基类（`params`/`next`/`notify_order`） | backtrader |
| backtrader | `bt.feeds.PandasData` | DataFrame → 行情数据源 | backtrader.feeds |
| backtrader | `bt.ind.SMA/EMA/CrossOver/RSI/MACD/ATR` | 技术指标 | backtrader.indicators |
| backtrader | `self.buy/sell/close` | 下单 | backtrader.Strategy |
| backtrader | `self.order_target_value/percent` | 目标市值/比例调仓 | backtrader.Strategy |
| backtrader | `bt.analyzers.TradeAnalyzer` | 交易统计 | backtrader.analyzers |
| backtrader | `bt.analyzers.Transactions` | 逐笔成交明细 | backtrader.analyzers |
| backtrader | `bt.CommInfoBase` | 自定义手续费模型 | backtrader |
| backtrader | `broker.set_slippage_perc` | 百分比滑点 | backtrader.brokers |
| pandas | `DataFrame` / `read_csv` | 表格数据结构 / 读数据 | pandas |
| pandas | `rolling` / `shift` / `pct_change` | 滚动窗口与收益率 | pandas |
| pandas | `groupby` / `rank` / `corr` | 分组、排序、相关性（算 IC） | pandas |
| matplotlib | `plot` / `scatter` / `bar` / `hist` | 线图 / 散点 / 柱状 / 直方图 | pyplot |
| matplotlib | `subplots` / `savefig` / `show` | 子图 / 保存 / 显示 | pyplot |
| sklearn | `StandardScaler` | 标准化（Z-Score） | preprocessing |
| sklearn | `MinMaxScaler` | 归一化（Min-Max） | preprocessing |
| sklearn | `train_test_split` | 数据切分 | model_selection |
| sklearn | `TimeSeriesSplit` | 时序切分 | model_selection |
| sklearn | `cross_val_score` | 交叉验证 | model_selection |
| sklearn | `GridSearchCV` | 参数搜索 | model_selection |
| sklearn | `LinearRegression` / `Ridge` / `Lasso` | 线性 / 岭 / Lasso 回归 | linear_model |
| sklearn | `LogisticRegression` | 逻辑回归 | linear_model |
| sklearn | `DecisionTreeClassifier` | 决策树 | tree |
| sklearn | `RandomForestClassifier` | 随机森林 | ensemble |
| sklearn | `KMeans` | K 均值聚类 | cluster |
| sklearn | `DBSCAN` | 密度聚类 | cluster |
| sklearn | `PCA` | 主成分分析 | decomposition |
| sklearn | `accuracy_score` | 准确率 | metrics |
| sklearn | `classification_report` | 分类报告（P/R/F1） | metrics |
| sklearn | `confusion_matrix` | 混淆矩阵 | metrics |
| sklearn | `roc_auc_score` | AUC | metrics |
| sklearn | `silhouette_score` | 轮廓系数 | metrics |
| sklearn | `calinski_harabasz_score` | CH 系数 | metrics |
| XGBoost | `XGBClassifier` / `XGBRegressor` | XGBoost 分类 / 回归 | xgboost |
| XGBoost | `plot_importance` | 特征重要性 | xgboost |
| Keras | `Sequential` / `Dense` / `LSTM` / `Conv1D` | 顺序模型 / 全连接 / LSTM / 一维卷积 | keras |
| ChromaDB | `Client` / `create_collection` / `add` / `query` | 客户端 / 建库 / 写入 / 检索 | chromadb |
| tiktoken | `encoding_for_model` / `encode` / `decode` | 分词器 / 文本→Token / Token→文本 | tiktoken |
| SciPy | `linkage` / `dendrogram` | 链接矩阵 / 树状图 | scipy.cluster.hierarchy |

## 五、配套文档

- 机器学习完整教程（含 SVM / PCA / 人脸识别 / 考点速记）→ [`docs/learning/4.机器学习/机器学习完全指南.md`](../4.机器学习/机器学习完全指南.md)
- 聚宽平台函数详解 → [`docs/learning/3.聚宽函数详解/get_functions.md`](../3.聚宽函数详解/get_functions.md)
- 本地回测环境与运行 → [`docs/本地回测使用指南.md`](../../本地回测使用指南.md)