# Matplotlib 详解——数据可视化

## 1. 库的定位与安装

Matplotlib 是 Python 最基础的绘图库，`pyplot` 子模块提供了类似 MATLAB 的绘图接口。

```bash
pip install matplotlib
```

## 2. 模块结构

```
matplotlib/
├── pyplot          # 绘图接口（最常用）
├── figure          # 画布对象
├── axes            # 坐标轴对象
├── ticker          # 刻度控制
├── cm              # 颜色映射
└── style           # 样式设置
```

## 3. 核心绘图函数详解

| 函数 | 用途 | 核心参数 |
|------|------|----------|
| `plot()` | 绘制线图/散点图 | `x, y, fmt, **kwargs` |
| `scatter()` | 绘制散点图 | `x, y, s, c, alpha` |
| `bar()` | 绘制柱状图 | `x, height, width` |
| `hist()` | 绘制直方图 | `x, bins, density` |
| `pie()` | 绘制饼图 | `x, labels, autopct` |
| `imshow()` | 显示图像 | `X, cmap` |
| `subplots()` | 创建子图 | `nrows, ncols, figsize` |

**plot()函数参数详解**：

```python
plt.plot(x, y, 'bo-', label='动量因子', linewidth=2, markersize=6)
```

| 参数 | 含义 | 可选值 |
|------|------|--------|
| `x, y` | 数据序列 | 列表或数组 |
| `fmt` | 格式字符串 | 颜色+标记+线型 |
| `label` | 图例标签 | 字符串 |
| `linewidth` | 线宽 | 浮点数 |
| `markersize` | 标记大小 | 浮点数 |

**格式字符串组合**：
- 颜色：`'b'`蓝、`'r'`红、`'g'`绿、`'k'`黑
- 线型：`'-'`实线、`'--'`虚线、`':'`点线
- 标记：`'.'`点、`'o'`圈、`'^'`三角

## 4. 图表装饰函数

| 函数 | 用途 | 示例 |
|------|------|------|
| `title()` | 设置标题 | `plt.title('股价走势')` |
| `xlabel()` / `ylabel()` | 设置轴标签 | `plt.xlabel('日期')` |
| `legend()` | 显示图例 | `plt.legend(loc='upper left')` |
| `xlim()` / `ylim()` | 设置轴范围 | `plt.xlim(0, 100)` |
| `grid()` | 显示网格 | `plt.grid(True, alpha=0.3)` |
| `savefig()` | 保存图片 | `plt.savefig('plot.png', dpi=150)` |
| `show()` | 显示图片 | `plt.show()` |

## 5. 量化应用：因子可视化

```python
import matplotlib.pyplot as plt
import numpy as np

np.random.seed(42)

# 1. 价格走势
price = 100 * np.cumprod(1 + np.random.randn(200) * 0.01)
plt.figure(figsize=(10, 4))
plt.plot(price, 'b-', linewidth=1.5)
plt.title('模拟股价走势')
plt.xlabel('天数')
plt.ylabel('价格')
plt.grid(True, alpha=0.3)
plt.show()

# 2. 特征重要性柱状图
features = ['动量', 'PE', 'ROE', '波动率', '换手率']
importance = [0.35, 0.10, 0.30, 0.15, 0.10]
plt.figure(figsize=(8, 4))
plt.bar(features, importance, color='steelblue')
plt.title('因子重要性')
plt.ylabel('重要性')
plt.show()

# 3. 收益率分布直方图
returns = np.random.randn(1000) * 0.02
plt.figure(figsize=(8, 4))
plt.hist(returns, bins=50, density=True, alpha=0.7)
plt.title('日收益率分布')
plt.xlabel('收益率')
plt.ylabel('频率')
plt.show()
```

## 6. 子图布局

```python
fig, axes = plt.subplots(2, 2, figsize=(12, 8))

# 在每个子图上绘图
axes[0, 0].plot(price)
axes[0, 0].set_title('价格走势')

axes[0, 1].hist(returns, bins=30)
axes[0, 1].set_title('收益率分布')

axes[1, 0].bar(features, importance)
axes[1, 0].set_title('因子重要性')

axes[1, 1].scatter(np.random.randn(50), np.random.randn(50))
axes[1, 1].set_title('散点图')

plt.tight_layout()
plt.show()
```
