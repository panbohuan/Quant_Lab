# 库详解目录（第三方库完整说明）

本文件夹系统讲解机器学习与量化学习中涉及的**所有第三方库**（除 numpy、pandas 外）的定位、模块结构、核心函数及其参数与用途，并给出量化场景中的应用示例。

> numpy 与 pandas 的基础学习见 `pandas详解.md` 与 `pandas量化应用.md`。

## 文档清单

| 文档 | 库 | 定位 | 一句话说明 |
|------|-----|------|-----------|
| [backtrader详解.md](backtrader详解.md) | backtrader | **本地回测引擎** | 本地回测的**教程 + 手册**：18 章，从心智模型、逐行模板到 Cerebro / Strategy / 指标 / 分析器 / 费用滑点 / 聚宽对照，代码块全部通过语法检查、关键示例实跑验证 |
| [sklearn详解.md](sklearn详解.md) | scikit-learn | 机器学习的"瑞士军刀" | 分类/回归/聚类/降维/预处理一站式，API 统一 |
| [xgboost详解.md](xgboost详解.md) | XGBoost | 梯度提升的工业级实现 | 因子筛选与合成，量化高频使用 |
| [tensorflow_keras详解.md](tensorflow_keras详解.md) | TensorFlow / Keras | 深度学习框架 | 神经网络、LSTM、CNN、Transformer |
| [chromadb详解.md](chromadb详解.md) | ChromaDB | 向量数据库 | RAG 检索的核心组件 |
| [tiktoken详解.md](tiktoken详解.md) | tiktoken | OpenAI 分词器 | 文本 ↔ Token 转换，估算 LLM 成本 |
| [scipy详解.md](scipy详解.md) | SciPy | 科学计算 | 优化、积分、层次聚类等算法 |
| [matplotlib详解.md](matplotlib详解.md) | Matplotlib | 数据可视化 | 画价格走势、因子重要性、收益分布 |
| [pandas详解.md](pandas详解.md) | pandas | 表格数据处理 | 量化策略里绕不开的核心库（基础教程） |
| [pandas量化应用.md](pandas量化应用.md) | pandas（进阶） | 量化实战 | 收益率、滚动窗口、因子计算、IC、分层回测 |

## 安装命令速查

```bash
# 本地回测引擎（本仓库 strategies/backtrader 的依赖）
pip install backtrader

# 核心机器学习库
pip install scikit-learn

# 梯度提升
pip install xgboost

# 深度学习
pip install tensorflow

# 向量数据库（RAG）
pip install chromadb

# 分词器
pip install tiktoken

# 科学计算
pip install scipy

# 可视化
pip install matplotlib
```

## 综合查询表：各库核心函数速查

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
| sklearn | `StandardScaler` | 标准化 | preprocessing |
| sklearn | `train_test_split` | 数据切分 | model_selection |
| sklearn | `TimeSeriesSplit` | 时序切分 | model_selection |
| sklearn | `cross_val_score` | 交叉验证 | model_selection |
| sklearn | `GridSearchCV` | 参数搜索 | model_selection |
| sklearn | `LinearRegression` | 线性回归 | linear_model |
| sklearn | `Ridge` | 岭回归 | linear_model |
| sklearn | `Lasso` | Lasso回归 | linear_model |
| sklearn | `LogisticRegression` | 逻辑回归 | linear_model |
| sklearn | `DecisionTreeClassifier` | 决策树 | tree |
| sklearn | `RandomForestClassifier` | 随机森林 | ensemble |
| sklearn | `KMeans` | K均值聚类 | cluster |
| sklearn | `DBSCAN` | 密度聚类 | cluster |
| sklearn | `PCA` | 主成分分析 | decomposition |
| sklearn | `accuracy_score` | 准确率 | metrics |
| sklearn | `roc_auc_score` | AUC | metrics |
| sklearn | `silhouette_score` | 轮廓系数 | metrics |
| XGBoost | `XGBClassifier` | XGBoost分类 | xgboost |
| XGBoost | `XGBRegressor` | XGBoost回归 | xgboost |
| XGBoost | `plot_importance` | 特征重要性 | xgboost |
| Keras | `Sequential` | 顺序模型 | keras.models |
| Keras | `Dense` | 全连接层 | keras.layers |
| Keras | `LSTM` | LSTM层 | keras.layers |
| Keras | `Conv1D` | 一维卷积 | keras.layers |
| Keras | `GlobalAveragePooling1D` | 全局平均池化 | keras.layers |
| ChromaDB | `Client` | 创建客户端 | chromadb |
| ChromaDB | `create_collection` | 创建集合 | chromadb |
| ChromaDB | `collection.add` | 添加文档 | chromadb |
| ChromaDB | `collection.query` | 相似性搜索 | chromadb |
| tiktoken | `encoding_for_model` | 获取分词器 | tiktoken |
| tiktoken | `enc.encode` | 文本→Token | tiktoken |
| tiktoken | `enc.decode` | Token→文本 | tiktoken |
| SciPy | `linkage` | 链接矩阵 | scipy.cluster.hierarchy |
| SciPy | `dendrogram` | 树状图 | scipy.cluster.hierarchy |
| Matplotlib | `plot` | 线图 | pyplot |
| Matplotlib | `scatter` | 散点图 | pyplot |
| Matplotlib | `bar` | 柱状图 | pyplot |
| Matplotlib | `hist` | 直方图 | pyplot |
| Matplotlib | `subplots` | 子图 | pyplot |
| Matplotlib | `savefig` | 保存图片 | pyplot |
