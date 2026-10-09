# scikit-learn（sklearn）详解——机器学习的"瑞士军刀"

## 1. 库的定位与设计哲学

scikit-learn 是 Python 中最广泛使用的机器学习库。它的设计哲学是**统一的 API**——所有模型都遵循相同的接口模式，因此学会一个模型后，切换到另一个模型只需要改变类名。

**安装方式**：

```bash
pip install scikit-learn
```

**核心API三接口**（所有对象都遵循以下约定）：

| 接口 | 核心方法 | 作用 | 示例 |
|------|----------|------|------|
| Estimator | `model.fit(X, y)` | 从数据中学习 | `rf.fit(X_train, y_train)` |
| Predictor | `model.predict(X)` | 做出预测 | `rf.predict(X_test)` |
| Transformer | `transformer.transform(X)` | 转换数据 | `scaler.transform(X)` |
| Model | `model.score(X, y)` | 评估性能 | `rf.score(X_test, y_test)` |

所有估计器都继承自 `sklearn.base.BaseEstimator`，实例化时只接受超参数，不接受训练数据。训练数据只能通过 `fit()` 方法传入。

## 2. 完整模块结构

sklearn 采用子包（subpackage）组织，每个子包负责一类功能。以下为文档中涉及和量化常用的全部子包：

| 子包路径 | 中文名称 | 核心功能 |
|----------|----------|----------|
| `sklearn.datasets` | 数据集 | 加载和生成示例数据集 |
| `sklearn.preprocessing` | 数据预处理 | 标准化、归一化、编码 |
| `sklearn.model_selection` | 模型选择 | 交叉验证、参数搜索、数据切分 |
| `sklearn.linear_model` | 线性模型 | 线性回归、逻辑回归、Ridge、Lasso |
| `sklearn.tree` | 决策树 | 决策树分类与回归 |
| `sklearn.ensemble` | 集成模型 | 随机森林、梯度提升 |
| `sklearn.svm` | 支持向量机 | SVM分类与回归 |
| `sklearn.neighbors` | 近邻算法 | kNN分类与回归 |
| `sklearn.cluster` | 聚类 | KMeans、DBSCAN、层次聚类 |
| `sklearn.decomposition` | 矩阵分解 | PCA、NMF降维 |
| `sklearn.metrics` | 评估指标 | 分类/回归/聚类评估 |
| `sklearn.pipeline` | 流水线 | 串联多个处理步骤 |
| `sklearn.feature_extraction` | 特征提取 | 文本、图像特征提取 |
| `sklearn.feature_selection` | 特征选择 | 方差过滤、递归特征消除 |
| `sklearn.impute` | 缺失值处理 | 填充缺失数据 |
| `sklearn.manifold` | 流形学习 | t-SNE等非线性降维 |
| `sklearn.mixture` | 混合模型 | 高斯混合模型 |

## 3. 核心模块与函数详解

### 3.1 数据预处理：sklearn.preprocessing

**StandardScaler——标准化**

作用：将数据转换为均值为 0、标准差为 1 的分布。

```python
from sklearn.preprocessing import StandardScaler

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)  # 等价于 fit + transform
```

| 参数 | 默认值 | 含义 | 量化场景 |
|------|--------|------|----------|
| `copy` | True | 是否复制原始数据 | 大数据集设False省内存 |
| `with_mean` | True | 是否将均值变为0 | 稀疏数据设False |
| `with_std` | True | 是否将方差变为1 | 通常保持True |

**为什么量化中必须标准化？** 不同因子的量纲差异巨大（PE 是几十，ROE 是 0.1 几），标准化后所有因子在同一尺度上，模型才能公平对待每个因子。

**其他预处理函数**：

| 类/函数 | 作用 | 使用场景 |
|---------|------|----------|
| `MinMaxScaler` | 缩放到[0,1]区间 | 神经网络输入 |
| `RobustScaler` | 用中位数和四分位距缩放 | 有异常值的因子 |
| `LabelEncoder` | 将类别编码为整数 | 行业分类 |
| `OneHotEncoder` | 独热编码 | 多类别特征 |

### 3.2 模型选择：sklearn.model_selection

**train_test_split——训练/测试集切分**

```python
from sklearn.model_selection import train_test_split

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, shuffle=True)
```

| 参数 | 默认值 | 含义 | 注意 |
|------|--------|------|------|
| `test_size` | 0.25 | 测试集比例 | 金融数据建议0.2-0.3 |
| `random_state` | None | 随机种子 | 设固定值保证可复现 |
| `shuffle` | True | 是否打乱 | **时序数据必须设False** |
| `stratify` | None | 分层抽样 | 类别不平衡时使用 |

**cross_val_score——交叉验证评分**

```python
from sklearn.model_selection import cross_val_score

scores = cross_val_score(model, X, y, cv=5, scoring='accuracy')
```

| 参数 | 含义 | 可选值 |
|------|------|--------|
| `cv` | 折数或切分器 | 5（K折）、TimeSeriesSplit对象 |
| `scoring` | 评估指标 | 'accuracy'、'roc_auc'、'neg_mean_squared_error' |
| `n_jobs` | 并行数 | -1表示使用所有CPU核心 |

**TimeSeriesSplit——时序交叉验证**

```python
from sklearn.model_selection import TimeSeriesSplit

tscv = TimeSeriesSplit(n_splits=5)
for train_idx, test_idx in tscv.split(X):
    # 训练集始终在测试集之前
    pass
```

| 参数 | 含义 | 量化建议 |
|------|------|----------|
| `n_splits` | 折数 | 5-10 |
| `max_train_size` | 最大训练集大小 | None（使用所有历史） |
| `test_size` | 测试集大小 | 自动计算 |

**GridSearchCV——网格搜索**

```python
from sklearn.model_selection import GridSearchCV

param_grid = {'n_estimators': [50, 100, 200], 'max_depth': [3, 5, 7]}
grid = GridSearchCV(model, param_grid, cv=TimeSeriesSplit(5), scoring='roc_auc')
grid.fit(X, y)
print(grid.best_params_)
```

### 3.3 线性模型：sklearn.linear_model

| 类 | 全称 | 用途 | 正则化 | 核心参数 |
|----|------|------|--------|----------|
| `LinearRegression` | 线性回归 | 预测连续值 | 无 | `fit_intercept` |
| `Ridge` | 岭回归 | 共线性强的回归 | L2 | `alpha` |
| `Lasso` | Lasso回归 | 高维稀疏数据 | L1 | `alpha` |
| `ElasticNet` | 弹性网 | 综合L1+L2 | L1+L2 | `alpha`, `l1_ratio` |
| `LogisticRegression` | 逻辑回归 | 二分类/多分类 | L1/L2 | `C`, `penalty` |
| `RidgeCV` | 岭回归CV | 自动选alpha | L2 | `alphas` |
| `LassoCV` | Lasso回归CV | 自动选alpha | L1 | `cv` |

**岭回归代码示例**：

```python
from sklearn.linear_model import Ridge, RidgeCV
import numpy as np

ridge = Ridge(alpha=1.0)
ridge.fit(X_train, y_train)
print("系数:", ridge.coef_)
print("截距:", ridge.intercept_)

# 自动选择最优alpha
alphas = np.logspace(-3, 3, 50)
ridge_cv = RidgeCV(alphas=alphas, cv=5)
ridge_cv.fit(X_train, y_train)
print("最优alpha:", ridge_cv.alpha_)
```

**Lasso回归代码示例**：

```python
from sklearn.linear_model import Lasso, LassoCV

lasso = Lasso(alpha=0.1)
lasso.fit(X_train, y_train)
print("系数:", lasso.coef_)  # 不重要的特征系数为0

lasso_cv = LassoCV(cv=5, random_state=42)
lasso_cv.fit(X_train, y_train)
print("非零系数个数:", np.sum(lasso_cv.coef_ != 0))
```

### 3.4 树模型与集成模型

| 类 | 模块 | 用途 | 核心参数 |
|----|------|------|----------|
| `DecisionTreeClassifier` | `sklearn.tree` | 分类决策树 | `max_depth`, `min_samples_split` |
| `DecisionTreeRegressor` | `sklearn.tree` | 回归决策树 | `max_depth` |
| `RandomForestClassifier` | `sklearn.ensemble` | 随机森林分类 | `n_estimators`, `max_depth` |
| `RandomForestRegressor` | `sklearn.ensemble` | 随机森林回归 | `n_estimators` |
| `GradientBoostingClassifier` | `sklearn.ensemble` | 梯度提升分类 | `n_estimators`, `learning_rate` |

**plot_tree——决策树可视化**：

```python
from sklearn.tree import plot_tree
import matplotlib.pyplot as plt

plt.figure(figsize=(8, 6))
plot_tree(tree, feature_names=['身高', '体重'],
          class_names=['小孩', '成年人'], filled=True, rounded=True)
plt.show()
```

### 3.5 聚类：sklearn.cluster

| 类 | 算法 | 核心参数 | 特点 |
|----|------|----------|------|
| `KMeans` | K均值 | `n_clusters`, `init`, `n_init` | 需指定K值，只能球形簇 |
| `DBSCAN` | 密度聚类 | `eps`, `min_samples` | 自动确定簇数，可处理噪声 |
| `AgglomerativeClustering` | 层次聚类 | `n_clusters`, `linkage` | 自底向上合并 |

**KMeans代码示例**：

```python
from sklearn.cluster import KMeans

kmeans = KMeans(n_clusters=3, init='k-means++', n_init=10, random_state=42)
labels = kmeans.fit_predict(X_scaled)
print("簇中心:", kmeans.cluster_centers_)
print("惯性:", kmeans.inertia_)  # 越小越好
```

**DBSCAN代码示例**：

```python
from sklearn.cluster import DBSCAN

dbscan = DBSCAN(eps=0.5, min_samples=5)
labels = dbscan.fit_predict(X_scaled)
n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
n_noise = list(labels).count(-1)
print(f"簇数: {n_clusters}, 噪声点: {n_noise}")
```

### 3.6 降维：sklearn.decomposition

**PCA——主成分分析**：

```python
from sklearn.decomposition import PCA

pca = PCA(n_components=5)
X_pca = pca.fit_transform(X_scaled)
print("解释方差比:", pca.explained_variance_ratio_)
print("累计解释方差:", np.sum(pca.explained_variance_ratio_))

# 保留95%方差
pca_95 = PCA(n_components=0.95)
X_pca_95 = pca_95.fit_transform(X_scaled)
print(f"保留95%方差需要 {pca_95.n_components_} 个主成分")
```

| 参数 | 含义 | 设置方式 |
|------|------|----------|
| `n_components` | 主成分数量 | 整数（指定数量）或小数（保留方差比例） |
| `whiten` | 是否白化 | True时各主成分方差为1 |

### 3.7 评估指标：sklearn.metrics

**分类指标**：

```python
from sklearn.metrics import (accuracy_score, precision_score,
                             recall_score, f1_score, roc_auc_score)

print("准确率:", accuracy_score(y_true, y_pred))
print("精确率:", precision_score(y_true, y_pred))
print("召回率:", recall_score(y_true, y_pred))
print("F1:", f1_score(y_true, y_pred))
print("AUC:", roc_auc_score(y_true, y_prob))
```

| 指标 | 函数 | 含义 | 量化解读 |
|------|------|------|----------|
| 准确率 | `accuracy_score` | 预测对的占比 | 涨跌预测中参考价值有限 |
| 精确率 | `precision_score` | 预测涨中真涨的比例 | 衡量信号质量 |
| 召回率 | `recall_score` | 真涨中被预测到的比例 | 衡量覆盖度 |
| F1 | `f1_score` | 精确率和召回率的调和 | 综合评分 |
| AUC | `roc_auc_score` | 区分正负样本的能力 | >0.55有预测力 |

**回归指标**：

```python
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

print("MSE:", mean_squared_error(y_test, y_pred))
print("MAE:", mean_absolute_error(y_test, y_pred))
print("R²:", r2_score(y_test, y_pred))
```

**聚类指标**：

```python
from sklearn.metrics import silhouette_score, davies_bouldin_score

sil = silhouette_score(X_scaled, labels)  # -1到1，>0.5表示簇分离好
dbi = davies_bouldin_score(X_scaled, labels)  # 越低越好
```

## 4. sklearn在量化策略中的完整工作流

```python
"""
量化策略中的sklearn完整流程示例
"""
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score

np.random.seed(42)
n = 3000
X = np.random.randn(n, 5)
y = (X[:, 0] * 0.5 + X[:, 1] * 0.3 > 0).astype(int)

# 1. 标准化
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# 2. 时序切分
tscv = TimeSeriesSplit(n_splits=5)
auc_scores = []

for train_idx, test_idx in tscv.split(X_scaled):
    X_train, X_test = X_scaled[train_idx], X_scaled[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]

    # 3. 训练
    model = RandomForestClassifier(n_estimators=100, max_depth=6,
                                   random_state=42)
    model.fit(X_train, y_train)

    # 4. 评估
    y_prob = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_prob)
    auc_scores.append(auc)

print(f'各折AUC: {[round(a, 3) for a in auc_scores]}')
print(f'平均AUC: {np.mean(auc_scores):.3f}')
```
