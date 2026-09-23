# 机器学习入门指南：从零基础到量化实战

> 目标读者：**非计算机、非人工智能专业**的同学。本篇用大量生活化的比喻和例子，帮你从零理解机器学习，并把它用到量化策略里。看完你会发现：机器学习没那么神秘，它只是「让计算机自己从数据里找规律」。
>
> 本文每个概念都配了**可直接运行的 Python 代码**。建议你打开 Jupyter 或任意 Python 环境，边看边跑，亲手把每个例子跑一遍，理解会深十倍。

---

## 目录

- [第 0 章：先破除一个迷思](#第0章先破除一个迷思)
- [第一章：机器学习是什么](#第一章机器学习是什么用教小孩认水果讲透)
- [第二章：监督学习——训练、测试、过拟合](#第二章监督学习的核心用考试类比理解训练)
- [第三章：金融数据的特殊性](#第三章金融数据的特殊性量化-ml-的分水岭)
- [第四章：常用模型](#第四章常用模型用一句话比喻讲清每个)
- [第五章：深度学习](#第五章深度学习进阶先了解概念)
- [第六章：强化学习](#第六章强化学习最前沿选学)
- [第七章：如何评估模型](#第七章如何评估模型别被回测好看骗了)
- [第八章：实战流程](#第八章实战流程从数据到实盘的完整链路)
- [第九章：一个完整的量化 ML 实战案例](#第九章一个完整的量化-ml-实战案例)
- [第十章：常见陷阱速查表](#第十章常见陷阱速查表)
- [第十一章：学习资源](#第十一章学习资源)
- [第十二章：知识体系总结](#第十二章知识体系总结)

---

<a name="第0章先破除一个迷思"></a>
## 第 0 章：先破除一个迷思

很多同学一听到「机器学习」就想到「高深数学」「神经网络」「要写很复杂的代码」，然后被吓退。

**真实情况**：机器学习最核心的思想，其实你每天都在用。

想想你是**怎么学会「分辨猫和狗」的**：

1. 小时候，你见过很多猫（毛茸茸、喵喵叫、抓老鼠）和很多狗（汪汪叫、摇尾巴、看门）；
2. 大人在旁边告诉你「这是猫」「那是狗」；
3. 见多了之后，你的大脑自动总结出规律：「四条腿 + 喵喵叫 + 抓老鼠 = 猫」；
4. 现在见到一只从没见过的猫，你一眼就能认出来。

**机器学习就是把这个过程交给计算机**：给计算机看「很多例子（数据）+ 正确答案（标签）」，让它自己总结规律，然后用规律去判断「没见过的新例子」。

所以别怕。你已经「无师自通」地完成了无数次机器学习，只是现在要把它「教给计算机」而已。

**再给你一个信心的例子**：下面这行代码，就能让计算机「学会」根据两个数字判断大小。跑一下试试：

```python
# 这是一个最小、最小、最小的机器学习例子
from sklearn.tree import DecisionTreeClassifier

# 特征：身高(cm) 和 体重(kg)；标签：1=成年人，0=小孩
X = [[175, 70], [160, 50], [180, 80], [110, 20], [100, 18], [120, 22]]
y = [1, 1, 1, 0, 0, 0]

model = DecisionTreeClassifier()   # 创建一个「决策树」模型
model.fit(X, y)                     # 训练：让模型「看」这 6 个例子

# 预测一个新样本：身高 170、体重 65，是成年人还是小孩？
print(model.predict([[170, 65]]))   # 输出 [1]，即「成年人」

# 预测另一个：身高 115、体重 21
print(model.predict([[115, 21]]))   # 输出 [0]，即「小孩」
```

就这四行代码，你已经完成了一次「完整的机器学习」：给数据（特征 X + 标签 y）→ 训练（fit）→ 预测（predict）。**是不是没你想的那么难？**

---

<a name="第一章机器学习是什么用教小孩认水果讲透"></a>
## 第一章：机器学习是什么

### 1.1 三个核心概念：特征、标签、模型

想象你教一个外星人「什么是苹果」：

- **特征（Feature）**：你描述的「线索」——「红色」「圆的」「有柄」「甜的」。特征就是「描述一个东西的维度」。
- **标签（Label）**：正确答案——「这是苹果」。标签就是「你要预测的目标」。
- **模型（Model）**：外星人学到的规律——「红色 + 圆 + 有柄 + 甜 = 苹果」。模型就是「从特征到标签的映射关系」。

对应到量化：

- **特征** = 因子（动量、PE、ROE、波动率……）；
- **标签** = 未来涨跌（涨了/跌了，或收益排名）；
- **模型** = 从「因子」到「未来收益」的映射规律。

**用代码直观感受这三个概念**：

```python
import pandas as pd

# 特征 X：三个「线索」（因子）
#   动量(过去60日涨幅)、PE(市盈率)、ROE(净资产收益率)
# 标签 y：未来是否上涨（1=涨，0=跌）
df = pd.DataFrame({
    '动量':  [0.25, 0.05, -0.10, 0.30],   # 这是「特征」
    'PE':    [8.0,  25.0, 15.0, 6.0],     # 这是「特征」
    'ROE':   [0.18, 0.08, 0.12, 0.20],    # 这是「特征」
    '未来涨': [1,    0,    0,    1],       # 这是「标签」
})
X = df[['动量', 'PE', 'ROE']]   # 特征矩阵：模型「看」的东西
y = df['未来涨']                # 标签向量：模型要「学」的答案

print('特征矩阵 X 的形状:', X.shape)   # (4, 3) = 4个样本，3个特征
print('标签 y 的形状:', y.shape)       # (4,)   = 4个答案
```

**记住这个约定**：在机器学习里，特征通常记作大写 `X`（矩阵，行=样本、列=特征），标签记作小写 `y`（向量，每个样本一个答案）。这个命名习惯几乎所有教程和代码都通用，看到了别懵。

### 1.2 三种学习范式

| 范式 | 类比 | 含义 | 量化应用 |
|------|------|------|----------|
| **监督学习** | 有老师告诉你答案 | 有特征 + 有标签 | 预测涨跌、因子合成 |
| **无监督学习** | 没有老师，自己找规律 | 只有特征，没标签 | 聚类选股、降维 |
| **强化学习** | 通过「试错 + 奖惩」学习 | 与环境互动，优化策略 | 动态仓位、最优执行 |

**量化里最常用的是「监督学习」**——因为我们有历史数据（特征）和历史结果（标签），可以让模型「学」出规律。

下面用代码把三种范式都快速看一眼：

```python
# ===== 1. 监督学习：有标签 =====
from sklearn.linear_model import LogisticRegression
X = [[175, 70], [160, 50], [110, 20], [100, 18]]   # 特征
y = [1, 1, 0, 0]                                    # 标签（有答案！）
clf = LogisticRegression().fit(X, y)
print('监督学习预测:', clf.predict([[120, 22]]))    # [0]

# ===== 2. 无监督学习：没标签，自己找结构 =====
from sklearn.cluster import KMeans
# 只有特征，没有标签，让模型自己「分组」
X = [[175, 70], [160, 50], [180, 80], [110, 20], [100, 18], [120, 22]]
kmeans = KMeans(n_clusters=2, random_state=0).fit(X)
print('无监督学习分组:', kmeans.labels_)  # 自动分成 2 组，如 [0,0,0,1,1,1]

# ===== 3. 强化学习：与环境互动，试错奖惩（概念性，这里不展开代码）=====
# 后文第六章专门讲，先知道它「没有现成答案，靠奖励信号学」即可。
```

**三者的本质区别就一句话**：监督学习有答案、无监督学习自己找结构、强化学习靠奖惩信号。

---

<a name="第二章监督学习的核心用考试类比理解训练"></a>
## 第二章：监督学习的核心——考试

### 2.1 训练集、测试集、过拟合

这是机器学习最最重要的概念，用「考试」来理解：

- **训练集**：你做的「练习题」（带答案）；
- **测试集**：真正的「期末考试」（没见过的题）；
- **过拟合**：你把「练习题答案背下来了」，但没理解规律，遇到新题就不会了。

**一个扎心的例子**：

小明复习数学考试，把练习册上 100 道题的**答案全背下来**了。考试时，出了 50 道**一模一样**的题，小明考了 100 分（训练集满分）。但下次考试，老师换了 50 道**新题**，小明只考了 30 分（测试集惨败）。

小明就是「过拟合」了——他「记住了题目」而非「学会了方法」。

**量化里的过拟合**：你的策略在「历史回测」里收益爆表（训练集满分），但一上实盘就亏钱（测试集惨败）。原因：策略「记住了历史数据的噪声」，而非「学到了真实的市场规律」。

**如何防止过拟合**：

1. **留出测试集**：训练时只用一部分数据，留一部分「没见过的」做最终验证；
2. **正则化**：给模型「戴紧箍咒」，禁止它太复杂（太复杂就容易背答案）；
3. **交叉验证**：多次「切分训练/测试」，确保模型稳定；
4. **早停**：训练到一定程度就停，别让模型「背到极致」。

### 2.2 一个完整的训练流程

下面是机器学习最标准的「四步流程」，你以后写的任何 ML 代码都是这个骨架：

```python
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

# 第一步：准备数据（假设 X 是特征/因子，y 是标签/未来涨跌）
np.random.seed(42)   # 固定随机种子，保证结果可复现
n = 1000
X = np.random.randn(n, 5)          # 1000 个样本，5 个特征（随机生成示例数据）
y = (X[:, 0] + X[:, 1] > 0).astype(int)  # 标签：由前两个特征决定（制造一个规律）

# 第二步：切分训练集/测试集（关键！留出"没见过的数据"做验证）
# test_size=0.2 表示留 20% 的数据做测试，剩下 80% 训练
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42)

# 第三步：训练模型
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# 第四步：评估（分别看"训练集"和"测试集"的表现）
train_acc = model.score(X_train, y_train)   # 训练集准确率
test_acc  = model.score(X_test,  y_test)    # 测试集准确率

print('训练集准确率:', round(train_acc, 3))
print('测试集准确率:', round(test_acc, 3))

# 判断是否过拟合：
#   训练集很高(如 0.99)、测试集很低(如 0.55) → 过拟合了
#   两者接近且都还不错 → 模型学到了真实规律
if train_acc - test_acc > 0.15:
    print('警告：训练集远高于测试集，可能过拟合了！')
```

**逐行理解这个流程**（这是全文最重要的代码，务必看懂）：

| 代码 | 作用 | 类比 |
|------|------|------|
| `train_test_split` | 把数据切成「练习题」和「期末考卷」 | 老师出题分两批 |
| `model.fit(X_train, y_train)` | 用练习题「学习」规律 | 学生刷题 |
| `model.score(X_test, y_test)` | 用期末考卷「检验」学得怎么样 | 真考试 |
| `train_acc` vs `test_acc` 对比 | 判断是否「背答案」而非「学会」 | 看平时成绩 vs 考试成绩 |

### 2.3 动手实验：亲自制造一次「过拟合」

看懂不如亲手做一次。下面这段代码，让你**亲眼看到过拟合长什么样**：

```python
import numpy as np
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split

np.random.seed(0)
n = 200
X = np.random.randn(n, 2)
# 标签里故意加了 20% 的随机噪声（模拟金融数据的"高噪声"）
y = (X[:, 0] > 0).astype(int)
noise = np.random.rand(n) < 0.2
y[noise] = 1 - y[noise]   # 随机翻转 20% 的标签，制造噪声

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3)

# 用"很深"的决策树（容易过拟合）
deep_tree = DecisionTreeClassifier(max_depth=None)   # 不限制深度 → 会拼命记住每个点
deep_tree.fit(X_train, y_train)
print('【深树】训练集:', round(deep_tree.score(X_train, y_train), 3),
      '| 测试集:', round(deep_tree.score(X_test, y_test), 3))

# 用"很浅"的决策树（限制深度 → 泛化更好）
shallow_tree = DecisionTreeClassifier(max_depth=2)   # 最多分 2 层
shallow_tree.fit(X_train, y_train)
print('【浅树】训练集:', round(shallow_tree.score(X_train, y_train), 3),
      '| 测试集:', round(shallow_tree.score(X_test, y_test), 3))
```

**你会看到**：深树的训练集准确率可能接近 100%（它「背下了所有题目」），但测试集准确率反而可能比浅树还低（因为它「记住了噪声」）。这就是过拟合的**直观证据**。

---

<a name="第三章金融数据的特殊性量化-ml-的分水岭"></a>
## 第三章：金融数据的特殊性（量化 ML 的分水岭）

这是「普通 ML」和「量化 ML」最大的区别。金融数据有三个致命特性：

### 3.1 高噪声、低信噪比

**比喻**：普通 ML（比如图像识别）像是「在安静的房间听清一句话」；量化 ML 像是「在菜市场里听清一句话」——到处都是噪声，真正的信号很微弱。

股价的波动，大部分是「噪声」（随机游走），只有一小部分是「可预测的信号」。所以量化 ML 的准确率天然很低——**能稳定做到 52%~55% 就已经很了不起**（别拿图像识别 99% 的准确率来期待）。

**代码直观感受「噪声有多重」**：

```python
import numpy as np
import matplotlib.pyplot as plt

# 用"随机游走"模拟股价：每天涨跌 = 随机噪声
np.random.seed(1)
n_days = 500
price = 100 * np.cumprod(1 + np.random.randn(n_days) * 0.01)  # 日波动1%

plt.figure(figsize=(10, 4))
plt.plot(price)
plt.title('模拟股价（纯随机游走）：看似有规律，实则全是噪声')
plt.xlabel('天数')
plt.ylabel('价格')
plt.show()

# 检验"可预测性"：明天的涨跌与今天是否相关？
returns = np.diff(price) / price[:-1]
corr = np.corrcoef(returns[:-1], returns[1:])[0, 1]
print('相邻两日收益率的相关系数:', round(corr, 4))
print('接近 0 → 说明明天涨跌几乎无法从今天预测（这就是"低信噪比"）')
```

### 3.2 非平稳性（规律会变）

**比喻**：图像识别里，猫永远是猫，规律不变。但金融市场里，「低 PE 的股票会涨」这个规律，可能在 2017 年有效、2020 年失效、2023 年又有效——**规律本身在变**。

这叫「非平稳」（regime change）。它意味着：**用过去数据训练的模型，未来可能失效**。对策是「滚动重训」（定期用最新数据重新训练）。

### 3.3 样本不是独立的（时序相关）

**比喻**：普通 ML 的样本像「抽签」，每张签独立。但金融数据像「多米诺骨牌」——今天的股价影响明天，样本之间有强相关性。

这导致一个严重后果：**不能用「随机 K 折」交叉验证**（会把「未来」混进「过去」，泄露信息）。

**代码演示：随机 K 折 vs 时序切分**

```python
from sklearn.model_selection import KFold, TimeSeriesSplit
import numpy as np

# 假设有 100 天的时序数据（index 越大越"未来"）
X = np.arange(100).reshape(-1, 1)   # 每天一个样本

print('=== 随机 K 折（金融里【错误】用法）===')
kf = KFold(n_splits=5, shuffle=True)
for i, (train_idx, test_idx) in enumerate(kf.split(X)):
    print(f'第{i+1}折 测试集索引: {test_idx.min()}~{test_idx.max()}')

print('\n=== 时序切分（金融里【正确】用法）===')
# TimeSeriesSplit：训练集永远是"过去"，测试集永远是"未来"
tscv = TimeSeriesSplit(n_splits=5)
for i, (train_idx, test_idx) in enumerate(tscv.split(X)):
    print(f'第{i+1}折 训练集: {train_idx.min()}~{train_idx.max()} '
          f'| 测试集: {test_idx.min()}~{test_idx.max()}')

# 关键区别：
# 随机K折：测试集可能出现在"过去"（用未来数据训练，去预测过去 → 作弊）
# 时序切分：测试集永远在训练集"之后"（符合真实交易"用过去预测未来"）
```

**理解这个代码的意义**：随机 K 折会让模型「用 2025 年的数据训练，去预测 2020 年」，这在现实里是不可能的（你 2020 年根本看不到 2025 年的数据）。时序切分则严格保证「只用过去预测未来」。

### 3.4 必须防范的四大陷阱

| 陷阱 | 比喻 | 说明 | 对策 |
|------|------|------|------|
| **未来函数** | 考试前偷看了答案 | 用了当时不可知的信息 | 数据滞后使用、动态复权 |
| **幸存者偏差** | 只统计活下来的老兵 | 只用现在还存在的股票 | 回测包含退市股 |
| **过拟合** | 背答案而非学方法 | 记住了噪声 | 正则化、样本外测试 |
| **数据窥探** | 反复调参直到好看 | 试到满意为止 | 严格样本外验证 |

**「未来函数」的代码演示**（这是新手最容易犯的致命错误）：

```python
import pandas as pd
import numpy as np

# 模拟：某股票连续 10 天的收盘价
df = pd.DataFrame({
    'date': pd.date_range('2024-01-01', periods=10),
    'close': [10, 11, 12, 11, 13, 14, 15, 14, 16, 17],
})

# ❌ 错误做法：用"未来"的数据当特征（未来函数）
# 比如"用今天的收盘价"去预测"今天的涨跌"——但涨跌是用今天和昨天算的，
# 而收盘价你今天收盘后才知道，等于"用结果预测结果"
df['未来5日均线'] = df['close'].rolling(5).mean().shift(-5)  # 用了未来5天的数据！
print('❌ 错误（含未来函数）的"未来5日均线"列：')
print(df[['date', 'close', '未来5日均线']].to_string(index=False))

# ✅ 正确做法：只用"过去"的数据
df['过去5日均线'] = df['close'].rolling(5).mean()  # 只用过去和当前的数据
print('\n✅ 正确的"过去5日均线"列（无未来函数）：')
print(df[['date', 'close', '过去5日均线']].to_string(index=False))

# 关键：shift(-5) 是"向前看"（用了未来），rolling().mean() 是"向后看"（只用过去）
# 任何用了 shift(-n) 或"未来数据"的特征，都会让回测虚高、实盘失效
```

> **必读推荐**：Marcos López de Prado 的《Advances in Financial Machine Learning》（金融机器学习进展）是这一领域的「圣经」，系统讲解了这些陷阱。

---

<a name="第四章常用模型用一句话比喻讲清每个"></a>
## 第四章：常用模型

这一章是重点——每个模型都配了**能跑的代码**，让你真正「亲手用过」。

### 4.1 树模型家族

**决策树（Decision Tree）**

比喻：像「二十个问题」游戏——通过一连串「是/否」判断，逐步缩小范围。

```
是否 ROE > 15%？
  ├─ 是 → 是否 PE < 10？
  │        ├─ 是 → 买入
  │        └─ 否 → 观望
  └─ 否 → 不买
```

优点：**可解释**（你能看到每一步判断）；缺点：容易过拟合（一条规则用到极致）。

```python
from sklearn.tree import DecisionTreeClassifier, plot_tree
import matplotlib.pyplot as plt

# 用第二章的数据训练一棵决策树
X = [[175, 70], [160, 50], [180, 80], [110, 20], [100, 18], [120, 22]]
y = [1, 1, 1, 0, 0, 0]
tree = DecisionTreeClassifier(max_depth=2)
tree.fit(X, y)

# 可视化这棵树（你会看到它"怎么一步步判断"）
plt.figure(figsize=(8, 6))
plot_tree(tree, feature_names=['身高', '体重'], class_names=['小孩', '成年人'],
          filled=True, rounded=True)
plt.title('决策树：可解释的"是/否"判断链')
plt.show()
# 你能清楚地看到树的每个分支，这就是"可解释性"
```

**随机森林（Random Forest）**

比喻：请 100 个「专家」（决策树）各自独立判断，最后**投票**。单个专家可能看走眼，但 100 个专家投票，结果就稳了。

优点：抗过拟合、对噪声鲁棒、能处理表格数据；是量化入门最推荐的模型。

```python
from sklearn.ensemble import RandomForestClassifier
import numpy as np

# 随机森林 = 很多棵决策树投票
# n_estimators=100 表示"请 100 个专家"
rf = RandomForestClassifier(n_estimators=100, random_state=42)

# 造一些带噪声的数据
np.random.seed(0)
X = np.random.randn(500, 3)
y = (X[:, 0] * 0.5 + X[:, 1] * 0.3 > 0).astype(int)
y[np.random.rand(500) < 0.15] = 1 - y[np.random.rand(500) < 0.15]  # 加噪声

rf.fit(X, y)

# 关键特性：特征重要性（哪个因子最有用）
importance = rf.feature_importances_
for i, imp in enumerate(importance):
    print(f'特征{i} 重要性: {imp:.3f}')
# 你会看到：特征0、1 重要性高（它们决定了标签），特征2 接近0（它是噪声）
print('这告诉我们：随机森林能"自动识别"哪些因子真正有用')
```

**XGBoost / LightGBM**

比喻：随机森林是「100 个专家同时独立判断」，XGBoost 是「专家一个接一个上，后面的专家专门纠正前面的错误」（梯度提升）。

优点：性能更强、训练快，是低频量化的「业界标准基线」。

```python
# XGBoost 需要先安装：pip install xgboost
from xgboost import XGBClassifier
import numpy as np

np.random.seed(0)
X = np.random.randn(500, 3)
y = (X[:, 0] * 0.5 + X[:, 1] * 0.3 > 0).astype(int)

xgb = XGBClassifier(n_estimators=100, max_depth=3, learning_rate=0.1)
xgb.fit(X, y)
print('XGBoost 训练完成，准确率:', round(xgb.score(X, y), 3))
# XGBoost 是"梯度提升"：后面的树专门修正前面树的错误，通常比随机森林更强
```

### 4.2 逻辑回归（Logistic Regression）

很多同学以为「回归」只能做「预测数字」，其实「逻辑回归」是做「分类」的利器（名字里带"回归"但做分类，这是历史命名遗留，别被名字骗了）。

比喻：逻辑回归就是「给每个特征打分，加权求和，再用一条 S 形曲线把分数压缩到 0~1 之间，表示"概率"」。

```python
from sklearn.linear_model import LogisticRegression
import numpy as np

np.random.seed(0)
X = np.random.randn(300, 2)
y = (X[:, 0] + X[:, 1] > 0).astype(int)

lr = LogisticRegression()
lr.fit(X, y)

# 逻辑回归不仅能输出"0/1"，还能输出"概率"
proba = lr.predict_proba([[1.5, 1.5]])
print('预测为1的概率:', round(proba[0, 1], 3))
print('权重系数:', lr.coef_)   # 能看到每个特征的"权重"，可解释性强
```

**为什么要提逻辑回归**：在量化里，很多时候「简单、可解释」的模型（逻辑回归、线性模型）比复杂模型更受青睐——因为它让你知道「模型为什么这么判断」。

### 4.3 支持向量机（SVM）

比喻：在「男同学」和「女同学」之间画一条线分开，SVM 找的是「离两边都最远」的那条线（最大间隔）。适合小样本、高维数据。

```python
from sklearn.svm import SVC
import numpy as np

np.random.seed(0)
X = np.random.randn(200, 2)
y = (X[:, 0] + X[:, 1] > 0).astype(int)

svm = SVC(kernel='rbf', probability=True)  # kernel='rbf' 用"核函数"处理非线性
svm.fit(X, y)
print('SVM 准确率:', round(svm.score(X, y), 3))
# kernel 参数是关键：'linear' 线性、'rbf' 非线性（最常用）
```

### 4.4 K 近邻（kNN）

比喻：「物以类聚」——判断一个新样本属于哪类，就看它「最近的 K 个邻居」大多数属于哪类。简单直观，但数据量大时很慢。

```python
from sklearn.neighbors import KNeighborsClassifier
import numpy as np

np.random.seed(0)
X = np.random.randn(200, 2)
y = (X[:, 0] + X[:, 1] > 0).astype(int)

knn = KNeighborsClassifier(n_neighbors=5)  # 看最近的 5 个邻居
knn.fit(X, y)
print('kNN 准确率:', round(knn.score(X, y), 3))
# n_neighbors 越小越容易过拟合，越大越平滑。需调参。
```

### 4.5 模型选择速查（新手照这个选）

| 场景 | 首选模型 | 理由 |
|------|----------|------|
| 第一次上手 | **随机森林** | 可解释、抗过拟合、几乎不用调参 |
| 追求精度 | XGBoost / LightGBM | 性能强，业界标准 |
| 需要「概率」输出 | 逻辑回归 / 随机森林 | predict_proba 直接给概率 |
| 样本很小 | SVM / 逻辑回归 | 小样本表现稳 |
| 要「为什么」的解释 | 决策树 / 逻辑回归 | 规则透明 |

---

<a name="第五章深度学习进阶先了解概念"></a>
## 第五章：深度学习（进阶）

### 5.1 神经网络是什么

比喻：大脑由神经元组成，每个神经元接收信号、处理、传递。人工神经网络就是模仿这个结构——一层层「神经元」叠加，层层提取特征。

**为什么叫「深度」学习**：层数多（深）的神经网络，能学到更抽象的特征。

**用 Keras 亲手搭一个最小神经网络**（体验一下）：

```python
# 需要先安装：pip install tensorflow
# 一个"两隐藏层"的神经网络，识别手写数字的简化版
from tensorflow import keras
from tensorflow.keras import layers
import numpy as np

# 造一些示例数据：1000 个样本，每个 10 个特征
np.random.seed(0)
X = np.random.randn(1000, 10)
y = (X[:, 0] + X[:, 1] > 0).astype(int)   # 二分类标签

model = keras.Sequential([
    layers.Dense(16, activation='relu', input_shape=(10,)),  # 输入层→隐藏层1
    layers.Dense(8, activation='relu'),                       # 隐藏层2
    layers.Dense(1, activation='sigmoid'),                    # 输出层(0~1概率)
])
model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
model.fit(X, y, epochs=20, batch_size=32, verbose=0)

print('神经网络准确率:', round(model.evaluate(X, y, verbose=0)[1], 3))
# 这就是"深度学习"：多层神经元叠加，自动提取特征
```

**逐层理解**：
- `Dense(16, activation='relu')`：一层 16 个「神经元」，`relu` 是激活函数（给网络引入非线性）；
- `sigmoid`：把输出压缩到 0~1，表示「概率」；
- `epochs=20`：整个数据「反复看 20 遍」；
- `batch_size=32`：每次「看 32 个样本」再更新一次。

### 5.2 处理时序的三种网络

**LSTM（长短期记忆网络）**

比喻：LSTM 有「记忆门」，像记笔记——重要的信息记下来，不重要的忘掉。它解决了「普通网络记不住很久以前信息」的问题，能捕捉「长期依赖」。

在金融里：能记住「3 个月前发生的某个事件对今天的影响」。

```python
# 概念性示例：LSTM 处理时序数据（简化版）
# LSTM 的输入是"三维的"：(样本数, 时间步长, 特征数)
from tensorflow import keras
from tensorflow.keras import layers
import numpy as np

# 模拟：200 个样本，每个是"过去10天、每天2个特征(如收盘价、成交量)"的序列
X = np.random.randn(200, 10, 2)   # (200, 10天, 2特征)
y = (X[:, -1, 0] > 0).astype(int) # 标签：由最后一天决定

model = keras.Sequential([
    layers.LSTM(32, input_shape=(10, 2)),  # LSTM层，32个记忆单元
    layers.Dense(1, activation='sigmoid'),
])
model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
model.fit(X, y, epochs=10, verbose=0)
print('LSTM 准确率:', round(model.evaluate(X, y, verbose=0)[1], 3))
# 关键：LSTM 能"记住"整个10天序列的信息，而非只看最后一天
```

**CNN（卷积神经网络）**

比喻：CNN 像「用放大镜扫过一段文字」——卷积层自动提取「局部模式」（比如「连续 3 天上涨」这个模式）。虽然 CNN 因图像识别出名，但也能处理一维时间序列。

```python
# 概念性示例：一维卷积处理时间序列（提取"局部模式"）
from tensorflow import keras
from tensorflow.keras import layers
import numpy as np

X = np.random.randn(200, 10, 1)   # (200, 10天, 1特征)
y = (X[:, -1, 0] > 0).astype(int)

model = keras.Sequential([
    layers.Conv1D(filters=16, kernel_size=3, activation='relu', input_shape=(10, 1)),
    layers.GlobalAveragePooling1D(),   # 把每个卷积核的结果汇总
    layers.Dense(1, activation='sigmoid'),
])
model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
model.fit(X, y, epochs=10, verbose=0)
print('一维CNN 准确率:', round(model.evaluate(X, y, verbose=0)[1], 3))
# kernel_size=3 表示"卷积窗口看3天"，自动捕捉"连续3天"的局部模式
```

**Transformer + 注意力机制**

比喻：注意力机制像「你在看一句话时，会自动重点关注某些关键词」。Transformer 让模型「动态决定该关注序列里的哪一部分」，在时序预测中逐渐取代 RNN。

（Transformer 代码较长，这里不展开。新手先知道「它能动态关注最重要的部分」这个概念即可，用到时再查文档。）

### 5.3 图神经网络（GNN）

比喻：把「资产之间的关系」画成一张网（图），GNN 能学习「哪些关联资产对预测最重要」。比如「苹果供应商的股价变化，可能领先于苹果本身」。

（GNN 是前沿方向，需要图结构数据和专门框架如 PyG/DGL，新手了解概念即可。）

---

<a name="第六章强化学习最前沿选学"></a>
## 第六章：强化学习（最前沿，选学）

### 6.1 核心思想

监督学习是「老师给答案」，强化学习是「**让 agent 自己试错，对了奖励、错了惩罚**」。

比喻：训练一只狗。你让它「坐下」，它坐下了就给零食（奖励），它乱跑就批评（惩罚）。反复多次，狗学会了「坐下有零食」。

在量化里：agent 是「交易策略」，环境是「市场」，奖励是「收益」，惩罚是「亏损」。agent 通过不断试错，学会「什么市场状态下该买多少仓位」。

### 6.2 强化学习的四个关键概念（用「打游戏」类比）

| 概念 | 类比 | 量化含义 |
|------|------|----------|
| **状态（State）** | 当前游戏画面 | 当前市场情况（价格、指标、持仓） |
| **动作（Action）** | 按键操作 | 买卖决策（买/卖/持有/仓位） |
| **奖励（Reward）** | 得分/扣分 | 收益/亏损 |
| **策略（Policy）** | 你的操作习惯 | 从「市场状态」到「交易动作」的规则 |

### 6.3 核心算法（了解名字即可）

- **DQN**：处理「离散动作」（买/卖/持有）；
- **DDPG**：处理「连续动作」（仓位从 0% 到 100%）；
- **PPO**：在低信噪比（噪声大）的环境里表现稳定，是量化常用的；
- **SAC**：更先进的连续控制算法。

**优势**：绕过「先预测再决策」的两阶段不一致，直接优化「交易目标」。
**劣势**：样本效率低、难调、易过拟合，实盘难度大。

> 新手建议：**先不要碰强化学习**。它是最难、最易过拟合的方向。等你把监督学习玩熟了，再回头研究它。

---

<a name="第七章如何评估模型别被回测好看骗了"></a>
## 第七章：如何评估模型（别被「回测好看」骗了）

### 7.1 基础指标（分类）

| 指标 | 含义 | 类比 |
|------|------|------|
| 准确率 | 预测对的占比 | 考试分数 |
| 精确率 | 预测「涨」里真的涨的 | 报警器响时真有小偷的概率 |
| 召回率 | 真的涨里被你预测到的 | 抓到了多少小偷 |
| F1 | 精确率和召回率的调和 | 综合评分 |
| AUC-ROC | 区分正负样本的能力 | 0.5=瞎猜，1=完美 |

**代码：一次性算出所有分类指标**

```python
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
import numpy as np

# 假设：y_true 是真实答案，y_pred 是模型预测
np.random.seed(0)
y_true = np.random.randint(0, 2, 100)
y_pred = np.random.randint(0, 2, 100)   # 随机预测（相当于瞎猜）

print('准确率 accuracy:', round(accuracy_score(y_true, y_pred), 3))
print('精确率 precision:', round(precision_score(y_true, y_pred), 3))
print('召回率 recall:', round(recall_score(y_true, y_pred), 3))
print('F1:', round(f1_score(y_true, y_pred), 3))

# AUC 需要"概率"而非"0/1"，这里模拟
y_prob = np.random.rand(100)
print('AUC-ROC:', round(roc_auc_score(y_true, y_prob), 3))
# 注意：随机预测的 AUC 应该接近 0.5（= 瞎猜），这是基准线
```

**为什么量化里「准确率」不够用**：因为「预测涨跌」本身很难（涨跌接近随机），更看重的是「区分能力」（AUC）和「因子有效性」（IC）。下面讲金融特有指标。

### 7.2 金融特有指标（这才是量化真正看的）

| 指标 | 含义 | 阈值 |
|------|------|------|
| **IC** | 因子值与未来收益的相关系数 | >0.03 有效 |
| **IC_IR** | IC 均值 / IC 标准差 | >0.5 稳定 |
| **分层回测单调性** | 按因子分 5 组，收益是否单调 | 越单调越好 |

**IC（信息系数）的代码演示**——这是量化 ML 最重要的指标：

```python
import numpy as np

# 模拟：某因子在 100 只股票上的取值，以及它们未来的收益
np.random.seed(0)
factor_value = np.random.randn(100)          # 因子值（如动量）
future_return = factor_value * 0.1 + np.random.randn(100) * 0.5  # 未来收益(与因子正相关+噪声)

# IC = 因子值与未来收益的相关系数
ic = np.corrcoef(factor_value, future_return)[0, 1]
print('本期 IC:', round(ic, 3))

# IC_IR = 多期 IC 的 均值 / 标准差（衡量因子"稳定不稳定"）
# 模拟 50 期的 IC 序列
ics = []
for _ in range(50):
    fv = np.random.randn(100)
    fr = fv * 0.08 + np.random.randn(100) * 0.6
    ics.append(np.corrcoef(fv, fr)[0, 1])
ics = np.array(ics)
ic_ir = ics.mean() / ics.std()
print('IC 均值:', round(ics.mean(), 3))
print('IC_IR:', round(ic_ir, 3))
print('解读：IC_IR > 0.5 说明因子"稳定有效"；< 0.3 说明不稳定，可能失效')
```

### 7.3 过拟合检测（进阶）

- **PBO（概率回测过拟合）**：你的回测结果「被过拟合污染」的概率；
- **Deflated Sharpe Ratio**：修正「反复试了很多次」后的夏普比率。

**一句话**：一个策略回测夏普 3.0，但如果是「试了 1000 次才试出来」的，真实夏普可能只有 1.0。

**「数据窥探」的直观理解（代码演示）**：

```python
import numpy as np

# 模拟：你反复调参，每次随机生成一个策略，看它的"夏普比率"
np.random.seed(0)
best_sharpe = 0
best_try = 0
for i in range(1, 1001):   # 尝试 1000 次
    # 每次随机生成一个"策略"（纯随机，没有任何真实 alpha）
    random_returns = np.random.randn(252) * 0.02  # 模拟一年的日收益
    sharpe = random_returns.mean() / random_returns.std() * np.sqrt(252)
    if sharpe > best_sharpe:
        best_sharpe = sharpe
        best_try = i

print(f'在 1000 次【纯随机】尝试中，最好的一次夏普是 {best_sharpe:.2f}（出现在第 {best_try} 次）')
print('这说明：即使策略完全没有 alpha，只要试得够多，也能"试出"一个高夏普！')
print('这就是"数据窥探"的危险——你以为找到了圣杯，其实只是运气好。')
```

这个例子很有冲击力：**纯随机的策略，试 1000 次也能「试出」夏普 3 以上的结果**。所以看到高夏普回测时，第一反应应该是「这会不会是试出来的」，而不是「哇好厉害」。

---

<a name="第八章实战流程从数据到实盘的完整链路"></a>
## 第八章：实战流程（从数据到实盘的完整链路）

```
数据获取 → 数据清洗 → 特征工程 → 标签设计 → 模型训练 → 样本外验证 → 回测 → 实盘
```

### 8.1 特征工程（怎么准备「线索」）

- **量价因子**：动量、波动率、换手率（从价格、成交量算）；
- **技术指标**：SMA（均线）、RSI（强弱）、MACD（趋势）；
- **财务因子**：PE、PB、ROE、毛利率；
- **情绪特征**：新闻、股吧情感打分；
- **另类数据**：搜索热度、供应链、卫星图像。

**用 pandas 算几个常用因子（衔接本仓库的 pandas 教程）**：

```python
import pandas as pd
import numpy as np

# 模拟某股票的日线数据
np.random.seed(0)
dates = pd.date_range('2023-01-01', periods=100, freq='D')
close = 100 * np.cumprod(1 + np.random.randn(100) * 0.01)
volume = np.random.randint(1000, 5000, 100)
df = pd.DataFrame({'close': close, 'volume': volume}, index=dates)

# 1. 动量因子：过去 20 日涨幅
df['动量'] = df['close'].pct_change(20)

# 2. 波动率因子：过去 20 日收益率的标准差
df['波动率'] = df['close'].pct_change().rolling(20).std()

# 3. 均线偏离：收盘价 / 20日均线 - 1
df['均线偏离'] = df['close'] / df['close'].rolling(20).mean() - 1

# 4. 换手率（用成交量近似）：当日成交量 / 过去20日平均成交量
df['量比'] = df['volume'] / df['volume'].rolling(20).mean()

print(df[['close', '动量', '波动率', '均线偏离', '量比']].tail(10).round(3))
# 这些列就是"特征"，未来涨跌就是"标签"，两者组合就是机器学习的数据
```

### 8.2 模型选择

| 数据规模 | 推荐模型 |
|----------|----------|
| 小样本、低维 | SVM、逻辑回归 |
| 中等样本、表格数据 | XGBoost、LightGBM、随机森林 |
| 大样本、时序数据 | LSTM、GRU、CNN-LSTM |
| 多资产关联 | GNN、Transformer |
| 动态决策 | 强化学习（PPO、DDPG） |

**给新手的建议**：从「随机森林」开始（可解释、抗过拟合、上手快），跑通整个流程后，再尝试 XGBoost，最后再碰深度学习。

---

<a name="第九章一个完整的量化-ml-实战案例"></a>
## 第九章：一个完整的量化 ML 实战案例（把前面学的串起来）

这一章是「总复习」——把前面所有概念串成一个**端到端的完整案例**：用随机森林预测股票涨跌，从造数据到评估一气呵成。

```python
"""
完整量化 ML 实战案例（教学版）：
用随机森林，根据多个因子预测"股票未来是否上涨"。

注意：这是【教学示例】，数据是模拟的，目的是让你理解完整流程。
真实场景里，你要把 X 换成聚宽 get_fundamentals 拉取的真实因子。
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import roc_auc_score

np.random.seed(42)

# ===== 第一步：构造"模拟"的股票因子数据 =====
n_stocks = 2000       # 2000 只股票
n_dates = 60          # 60 个交易日（时序）
dates = pd.date_range('2023-01-01', periods=n_dates, freq='D')

records = []
for d in dates:
    # 每只股票 5 个因子（特征）
    momentum = np.random.randn(n_stocks)          # 动量
    pe_ratio = np.abs(np.random.randn(n_stocks) * 10)  # PE
    roe = np.random.randn(n_stocks)               # ROE
    volatility = np.abs(np.random.randn(n_stocks))    # 波动率
    turnover = np.abs(np.random.randn(n_stocks))      # 换手率

    # 标签：未来是否上涨（由动量+ROE 驱动，加噪声）
    score = momentum * 0.3 + roe * 0.3 + np.random.randn(n_stocks) * 0.8
    label = (score > 0).astype(int)

    for i in range(n_stocks):
        records.append([d, momentum[i], pe_ratio[i], roe[i],
                        volatility[i], turnover[i], label[i]])

df = pd.DataFrame(records, columns=[
    'date', '动量', 'PE', 'ROE', '波动率', '换手率', '未来涨'])

# ===== 第二步：划分特征 X 和标签 y =====
feature_cols = ['动量', 'PE', 'ROE', '波动率', '换手率']
X = df[feature_cols].values
y = df['未来涨'].values

print('数据规模：', X.shape, '样本 ×', len(feature_cols), '特征')

# ===== 第三步：时序切分（金融里必须用，不能用随机K折！）=====
# 用前 80% 的时间做训练，后 20% 做测试（严格"用过去预测未来"）
split_point = int(len(dates) * 0.8)
split_idx = split_point * n_stocks
X_train, X_test = X[:split_idx], X[split_idx:]
y_train, y_test = y[:split_idx], y[split_idx:]
print(f'训练集：{X_train.shape[0]} 样本（前 {split_point} 天）')
print(f'测试集：{X_test.shape[0]} 样本（后 {len(dates)-split_point} 天）')

# ===== 第四步：训练模型 =====
model = RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42)
model.fit(X_train, y_train)

# ===== 第五步：评估（重点看"样本外"表现）=====
train_auc = roc_auc_score(y_train, model.predict_proba(X_train)[:, 1])
test_auc  = roc_auc_score(y_test,  model.predict_proba(X_test)[:, 1])
print(f'\n训练集 AUC: {train_auc:.3f}')
print(f'测试集 AUC: {test_auc:.3f}  ← 这才是模型真实水平')
print('解读：AUC 0.5 = 瞎猜，0.55 以上 = 有一定预测力，0.6 以上 = 很强')

# ===== 第六步：看特征重要性（哪些因子最有用）=====
print('\n因子重要性：')
for name, imp in zip(feature_cols, model.feature_importances_):
    print(f'  {name}: {imp:.3f}')
print('解读：重要性高的因子（动量、ROE）是真正的 alpha 来源，'
      '重要性接近0的（PE、波动率、换手率）可能是噪声')
```

**这个案例教你的完整链路**：

1. **数据准备**：把「因子」组织成特征矩阵，把「未来涨跌」组织成标签；
2. **时序切分**：严格用「过去」训练、「未来」测试（防未来函数）；
3. **训练**：随机森林 `fit`；
4. **样本外评估**：看「测试集」的 AUC，而非「训练集」（防过拟合）；
5. **因子归因**：看「特征重要性」，理解哪些因子真正有用。

**把这段代码「升级」成真实聚宽策略**，就是本仓库的《进阶策略 8：机器学习因子合成》——那里用真实的 `get_fundamentals` 拉因子、用真实的 `attribute_history` 算动量，跑在聚宽回测引擎上。

---

<a name="第十章常见陷阱速查表"></a>
## 第十章：常见陷阱速查表

| 陷阱 | 表现 | 解决 |
|------|------|------|
| 未来函数 | 回测虚高，实盘失效 | 数据滞后使用、动态复权、时序切分 |
| 过拟合 | 样本内极好，样本外崩溃 | 正则化、早停、Walk-Forward |
| 数据窥探 | 反复调参直到好看 | 严格样本外、PBO 检测 |
| 非平稳性 | 模型在风格切换时失效 | 滚动重训、在线学习 |
| 黑箱问题 | 无法解释决策 | 特征重要性、SHAP、注意力可视化 |
| 幸存者偏差 | 只用现在还存在的股票 | 回测包含退市股 |

**给新手的三条「保命」原则**：

1. **永远用样本外数据验证**：训练时留一块「没碰过」的数据，最终只信它的结果；
2. **警惕任何「太好」的回测**：夏普 3 以上先怀疑「是不是试出来的/未来函数」；
3. **可解释优先**：能讲清楚「为什么」的简单模型，胜过说不清的黑箱复杂模型。

---

<a name="第十一章学习资源"></a>
## 第十一章：学习资源

### 书籍

- **《Advances in Financial Machine Learning》**（Marcos López de Prado）：金融 ML 必读，系统讲解数据标注、特征工程、回测陷阱；
- **《Hands-On Machine Learning with Scikit-Learn, Keras & TensorFlow》**（Aurélien Géron）：机器学习上手最好的书之一，代码详实；
- **《机器学习》（周志华，西瓜书）**：中文经典教材，理论扎实。

### 开源框架

- **Qlib**（微软）：端到端量化 ML 流水线；
- **vn.py / VeighNa**：量化交易框架，含 ML 模块；
- **scikit-learn**：通用机器学习（本文大量用到，新手第一站）；
- **XGBoost / LightGBM**：梯度提升树（量化高频使用）。

### 论文方向

- 混合模型（XGBoost + LSTM、CNN-LSTM）；
- 注意力机制与强化学习结合；
- 图神经网络在多资产建模中的应用。

### 本仓库配套阅读

- 《进阶策略 8：机器学习因子合成》——ML 在聚宽里的真实落地；
- 《进阶策略 10：舆情情绪策略》——非结构化数据 + 情感分析；
- 《pandas 量化应用指南》——本文所有数据操作的基础。

---

<a name="第十二章知识体系总结"></a>
## 第十二章：知识体系总结（一张图记住全部）

```
机器学习（量化）
├── 基础
│   ├── 监督学习（有答案：预测涨跌、因子合成）
│   ├── 无监督学习（没答案：聚类选股、降维）
│   └── 强化学习（试错奖惩：动态仓位）
├── 金融特殊性（区别于普通ML的关键）
│   ├── 标签设计：用"截面排名"而非"绝对涨跌"
│   ├── 时序交叉验证：Walk-Forward，防未来函数
│   └── 防陷阱：未来函数、幸存者偏差、过拟合
├── 模型
│   ├── 树模型：决策树、随机森林、XGBoost、LightGBM
│   ├── 线性模型：逻辑回归
│   ├── 深度学习：LSTM、CNN、Transformer
│   ├── 图神经网络：GNN（多资产关联）
│   └── 强化学习：PPO、DDPG（策略优化）
├── 评估
│   ├── 通用：准确率、精确率、召回率、AUC
│   ├── 金融：IC、IC_IR、分层回测单调性
│   └── 过拟合检测：PBO、Deflated Sharpe
└── 实战
    ├── 特征工程（因子/情绪/另类数据）
    ├── 模型选择与调优
    └── 端到端部署
```

**一句话总结**：量化 ML = 通用 ML 基础 + 金融数据特殊性 + 时序/图/强化学习模型 + 严格验证 + 防陷阱工程。**核心不是模型多复杂，而是理解金融数据的本质，并用正确的方法处理它。**

---

## 给新手的最后建议

1. **先跑通，再深入**：先用「随机森林 + 简单因子」跑通整个流程（数据→训练→回测），比一开始就啃 LSTM 有用得多；
2. **把「防过拟合」刻在骨子里**：量化 ML 最大的敌人不是「模型不够强」，而是「你以为很强，其实过拟合了」；
3. **可解释 > 高精度**：一个能解释「为什么」的简单模型，比一个黑箱但精度略高的复杂模型更值得信任；
4. **别指望 ML 是「圣杯」**：ML 是「更好地利用数据的工具」，不是「稳赚不赔的魔法」。真正赚钱的，永远是「对市场的理解 + 正确的方法 + 严格的纪律」；
5. **亲手跑代码**：本文每个代码块都能运行。别只「看」，打开 Python 环境「跑」一遍，边跑边改参数，观察结果变化——这才是真正的学习。

结合本仓库的《进阶策略 8：机器学习因子合成》和《进阶策略 10：舆情情绪策略》一起看，你能看到 ML 在量化里的具体落地。
