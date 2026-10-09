# XGBoost 详解——梯度提升的工业级实现

## 1. 库的定位与安装

XGBoost（eXtreme Gradient Boosting）是梯度提升树的高效实现，在量化领域被广泛用于因子筛选和合成。它的核心思想是**"专家一个接一个上，后面的专家专门纠正前面的错误"**。

```bash
pip install xgboost
```

## 2. 模块结构

```
xgboost/
├── XGBClassifier      # 分类器
├── XGBRegressor       # 回归器
├── XGBRanker          # 排序器（用于Learning to Rank）
├── train()            # 底层训练接口
├── DMatrix            # 高效数据矩阵
└── plot_importance()  # 特征重要性可视化
```

## 3. XGBClassifier完整参数详解

```python
from xgboost import XGBClassifier

model = XGBClassifier(
    n_estimators=100,       # 树的数量
    max_depth=3,            # 每棵树最大深度
    learning_rate=0.1,      # 学习率（步长）
    objective='binary:logistic',  # 目标函数
    booster='gbtree',       # 基学习器类型
    subsample=0.8,          # 行采样比例
    colsample_bytree=0.8,   # 列采样比例
    reg_alpha=0,            # L1正则化
    reg_lambda=1,           # L2正则化
    gamma=0,                # 分裂所需最小损失减少
    min_child_weight=1,     # 子节点最小样本权重和
    random_state=42,
)
```

| 参数 | 类型 | 默认值 | 含义 | 调参建议 |
|------|------|--------|------|----------|
| `n_estimators` | int | 100 | 树的数量 | 越大越容易过拟合，配合early_stopping |
| `max_depth` | int | 3 | 树的最大深度 | 量化中建议3-6 |
| `learning_rate` | float | 0.1 | 学习率 | 越小需要越多树 |
| `objective` | str | 'binary:logistic' | 目标函数 | 二分类用binary:logistic |
| `subsample` | float | 1 | 行采样比例 | 0.6-0.8防过拟合 |
| `colsample_bytree` | float | 1 | 列采样比例 | 0.6-0.8防过拟合 |
| `reg_alpha` | float | 0 | L1正则化 | 增大可做特征选择 |
| `reg_lambda` | float | 1 | L2正则化 | 增大防过拟合 |
| `gamma` | float | 0 | 分裂阈值 | 增大使树更保守 |

## 4. 完整使用示例

```python
from xgboost import XGBClassifier, plot_importance
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import roc_auc_score
import numpy as np
import matplotlib.pyplot as plt

np.random.seed(42)
X = np.random.randn(2000, 5)
y = (X[:, 0] * 0.5 + X[:, 1] * 0.3 > 0).astype(int)

tscv = TimeSeriesSplit(n_splits=5)
for train_idx, test_idx in tscv.split(X):
    X_train, X_test = X[train_idx], X[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]

    model = XGBClassifier(n_estimators=100, max_depth=3,
                          learning_rate=0.1, subsample=0.8,
                          colsample_bytree=0.8, random_state=42)
    model.fit(X_train, y_train,
              eval_set=[(X_test, y_test)],
              verbose=False)

    y_prob = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_prob)
    print(f'AUC: {auc:.3f}')

# 特征重要性
plot_importance(model)
plt.show()
```

## 5. 在量化中的应用

XGBoost 在因子筛选和合成中具有显著潜力。中金公司的研究表明，XGBoost 模型能够在不预设固定线性关系的基础上，识别多维变量之间的复杂关系，因此更适合当前市场非线性定价环境下的择券需求。在沪深300、中证500和中证1000指数增强中均有全面测试。

| 场景 | 用法 | 优势 |
|------|------|------|
| 因子合成 | 多因子输入，预测收益 | 自动捕捉非线性关系 |
| 因子筛选 | 查看feature_importances_ | 识别有效因子 |
| 指数增强 | 预测个股超额收益 | 比线性模型更强 |
