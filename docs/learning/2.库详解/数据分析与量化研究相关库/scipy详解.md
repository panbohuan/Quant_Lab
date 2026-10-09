# SciPy 详解——科学计算

## 1. 库的定位与安装

SciPy 是 Python 科学计算的核心库，提供优化、积分、插值、信号处理、聚类等算法。本文档聚焦其在机器学习指南中使用到的层次聚类模块。

```bash
pip install scipy
```

## 2. 文档中使用的模块

```
scipy.cluster.hierarchy/
├── linkage()      # 计算层次聚类的链接矩阵
├── dendrogram()   # 绘制树状图
├── fcluster()     # 从链接矩阵中提取扁平聚类
└── leaves_list()  # 获取叶节点顺序
```

## 3. linkage——计算链接矩阵

```python
from scipy.cluster.hierarchy import linkage

Z = linkage(X, method='ward', metric='euclidean')
```

| 参数 | 含义 | 可选值 |
|------|------|--------|
| `method` | 链接方法 | 'single', 'complete', 'average', 'ward' |
| `metric` | 距离度量 | 'euclidean', 'cityblock', 'cosine' |

**链接方法对比**：

| 方法 | 策略 | 特点 |
|------|------|------|
| `single` | 最近距离 | 容易产生链状簇 |
| `complete` | 最远距离 | 紧凑的簇 |
| `average` | 平均距离 | 折中方案 |
| `ward` | 最小方差 | 最常用，簇内方差最小 |

返回的 Z 是一个 (n-1)×4 的矩阵，每一行表示一次合并操作：`[簇1索引, 簇2索引, 距离, 新簇大小]`。

## 4. dendrogram——绘制树状图

```python
from scipy.cluster.hierarchy import dendrogram
import matplotlib.pyplot as plt

Z = linkage(X_scaled[:50], method='ward')
plt.figure(figsize=(10, 5))
dendrogram(Z)
plt.title('层次聚类树状图')
plt.show()
```

| 参数 | 含义 | 说明 |
|------|------|------|
| `Z` | linkage返回的矩阵 | 必需 |
| `truncate_mode` | 截断模式 | 'lastp'只显示最后p个簇 |
| `p` | 截断数量 | 与truncate_mode配合 |
| `leaf_rotation` | 叶标签旋转角度 | 90度避免重叠 |
| `leaf_font_size` | 叶标签字体大小 | 8-12 |

## 5. 量化应用：股票层次聚类

```python
from scipy.cluster.hierarchy import linkage, dendrogram
from sklearn.preprocessing import StandardScaler
import numpy as np
import matplotlib.pyplot as plt

# 模拟50只股票的5个因子
np.random.seed(42)
stock_factors = np.random.randn(50, 5)

scaler = StandardScaler()
X_scaled = scaler.fit_transform(stock_factors)

# 层次聚类
Z = linkage(X_scaled, method='ward')

# 可视化
plt.figure(figsize=(12, 5))
dendrogram(Z, leaf_rotation=90, leaf_font_size=8)
plt.title('股票层次聚类树状图')
plt.xlabel('股票编号')
plt.ylabel('距离')
plt.show()
```
