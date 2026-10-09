# TensorFlow / Keras 详解——深度学习框架

## 1. 库的定位与安装

TensorFlow 是 Google 开源的深度学习框架，Keras 是 TensorFlow 的高层 API，让搭建神经网络像搭积木一样简单。

```bash
pip install tensorflow
```

## 2. 模块结构

```
tensorflow.keras/
├── models/
│   ├── Sequential        # 顺序模型（层堆叠）
│   └── Model             # 函数式API模型
├── layers/
│   ├── Dense             # 全连接层
│   ├── LSTM              # 长短期记忆层
│   ├── GRU               # 门控循环单元
│   ├── Conv1D            # 一维卷积层
│   ├── Conv2D            # 二维卷积层
│   ├── MaxPooling1D      # 一维最大池化
│   ├── GlobalAveragePooling1D  # 全局平均池化
│   ├── Dropout           # 随机失活
│   ├── BatchNormalization # 批归一化
│   └── Embedding         # 嵌入层
├── optimizers/
│   ├── Adam              # 自适应学习率优化器
│   └── RMSprop           # 均方根传播优化器
├── losses/               # 损失函数
├── metrics/              # 评估指标
└── callbacks/            # 回调函数
```

## 3. 核心类与函数详解

### 3.1 Sequential——顺序模型

```python
from tensorflow import keras
from tensorflow.keras import layers

model = keras.Sequential([
    layers.Dense(16, activation='relu', input_shape=(10,)),
    layers.Dense(8, activation='relu'),
    layers.Dense(1, activation='sigmoid'),
])
```

`Sequential` 按顺序堆叠层，数据从第一层流向最后一层。

### 3.2 Dense——全连接层

```python
layers.Dense(units=16, activation='relu', input_shape=(10,))
```

| 参数 | 含义 | 常用值 |
|------|------|--------|
| `units` | 神经元数量 | 8-256 |
| `activation` | 激活函数 | 'relu', 'sigmoid', 'softmax' |
| `input_shape` | 输入维度 | 仅第一层需要 |

### 3.3 LSTM——长短期记忆层

```python
layers.LSTM(units=32, input_shape=(10, 2), return_sequences=False)
```

| 参数 | 含义 | 说明 |
|------|------|------|
| `units` | 记忆单元数量 | 16-128 |
| `return_sequences` | 是否返回完整序列 | True时返回每个时间步的输出 |
| `dropout` | 输入dropout率 | 0.1-0.3 |
| `recurrent_dropout` | 循环dropout率 | 0.1-0.3 |

**金融应用**：LSTM 的"记忆门"能捕捉长期依赖，例如"3个月前发生的某个事件对今天的影响"。

### 3.4 Conv1D——一维卷积层

```python
layers.Conv1D(filters=16, kernel_size=3, activation='relu', input_shape=(10, 1))
```

| 参数 | 含义 | 说明 |
|------|------|------|
| `filters` | 卷积核数量 | 16-128 |
| `kernel_size` | 卷积窗口大小 | 3（看连续3天） |
| `strides` | 步长 | 通常为1 |
| `padding` | 填充方式 | 'valid'或'same' |

**金融应用**：kernel_size=3 表示"卷积窗口看3天"，自动捕捉"连续3天上涨"等局部模式。

### 3.5 GlobalAveragePooling1D——全局平均池化

```python
layers.GlobalAveragePooling1D()
```

将每个卷积核的输出在时间维度上取平均，把变长序列压缩为固定长度向量。

### 3.6 编译与训练

```python
model.compile(
    optimizer='adam',               # 优化器
    loss='binary_crossentropy',     # 损失函数
    metrics=['accuracy']            # 评估指标
)

model.fit(
    X, y,
    epochs=20,          # 训练轮次
    batch_size=32,      # 批次大小
    validation_split=0.2,  # 验证集比例
    verbose=0           # 是否打印进度
)
```

| 参数 | 含义 | 常用值 |
|------|------|--------|
| `optimizer` | 优化器 | 'adam', 'rmsprop' |
| `loss` | 损失函数 | 'binary_crossentropy', 'mse' |
| `metrics` | 评估指标 | ['accuracy'] |
| `epochs` | 训练轮次 | 10-100 |
| `batch_size` | 批次大小 | 16-128 |

## 4. 量化应用：LSTM预测股票涨跌

```python
from tensorflow import keras
from tensorflow.keras import layers
import numpy as np

# 输入形状：(样本数, 时间步长, 特征数)
X = np.random.randn(200, 10, 2)   # 200个样本，10天，2个特征
y = (X[:, -1, 0] > 0).astype(int)

model = keras.Sequential([
    layers.LSTM(32, input_shape=(10, 2)),
    layers.Dropout(0.2),
    layers.Dense(1, activation='sigmoid'),
])
model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
model.fit(X, y, epochs=10, batch_size=32, validation_split=0.2, verbose=0)

print('准确率:', round(model.evaluate(X, y, verbose=0)[1], 3))
```
