# tiktoken 详解——OpenAI 分词器

## 1. 库的定位与安装

tiktoken 是 OpenAI 开源的分词器库，用于将文本转换为 Token 序列。它用 Rust 编写，速度极快，是计算 LLM 成本和分析文本结构的必备工具。

```bash
pip install tiktoken
```

## 2. 模块结构

```
tiktoken/
├── get_encoding()          # 按编码名称获取分词器
├── encoding_for_model()    # 按模型名称获取分词器
├── list_encoding_names()   # 列出所有可用编码
└── Encoding                # 分词器对象
    ├── encode()            # 文本 → Token IDs
    ├── decode()            # Token IDs → 文本
    └── encode_with_special_tokens()  # 含特殊Token
```

## 3. 支持的编码格式

| 编码名称 | 对应模型 | 说明 |
|----------|----------|------|
| `cl100k_base` | GPT-3.5, GPT-4 | 最常用 |
| `o200k_base` | GPT-4o, o1, o3 | 更新的编码 |
| `p50k_base` | Codex, 旧版GPT-3 | 代码模型 |
| `r50k_base` | GPT-2 | 旧版 |

## 4. 核心函数详解

```python
import tiktoken

# 方式1：按编码名称获取
enc = tiktoken.get_encoding("cl100k_base")

# 方式2：按模型名称获取（推荐）
enc = tiktoken.encoding_for_model("gpt-4o")

# 文本 → Token IDs
text = "机器学习是人工智能的核心分支"
tokens = enc.encode(text)
print(f"Token数: {len(tokens)}")
print(f"Token IDs: {tokens}")

# Token IDs → 文本
decoded = enc.decode(tokens)
print(f"解码: {decoded}")
```

| 函数 | 输入 | 输出 | 用途 |
|------|------|------|------|
| `get_encoding(name)` | 编码名称字符串 | Encoding对象 | 获取分词器 |
| `encoding_for_model(model)` | 模型名称字符串 | Encoding对象 | 获取对应模型的分词器 |
| `enc.encode(text)` | 文本字符串 | Token ID列表 | 分词 |
| `enc.decode(tokens)` | Token ID列表 | 文本字符串 | 反分词 |

## 5. 量化应用：估算LLM调用成本

```python
import tiktoken

enc = tiktoken.encoding_for_model("gpt-4o")

# 估算研报摘要的Token数
report = "某公司发布2024年三季报，营收同比增长15%，净利润同比增长20%..."
tokens = enc.encode(report)
print(f"Token数: {len(tokens)}")
print(f"预估成本: ${len(tokens) / 1000 * 0.005:.4f}")  # 假设$0.005/1K tokens
```
