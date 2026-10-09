# ChromaDB 详解——向量数据库

## 1. 库的定位与安装

ChromaDB 是一个开源的向量数据库，用于存储和检索高维向量，是 RAG（检索增强生成）系统的核心组件。

```bash
pip install chromadb
```

## 2. 模块结构

```
chromadb/
├── Client              # 客户端（连接数据库）
├── Collection          # 集合（类似表）
├── Search              # 搜索API（高级）
├── K                   # 字段选择器
├── Knn                 # K近邻搜索
└── utils/
    └── embedding_functions/  # 嵌入函数
```

## 3. 核心类与函数详解

### 3.1 Client——创建客户端

```python
import chromadb

client = chromadb.Client()              # 内存模式（数据不持久化）
client = chromadb.PersistentClient(path="./db")  # 持久化模式
```

### 3.2 Collection——集合操作

```python
# 创建集合
collection = client.create_collection(name="quant_research")

# 获取已有集合
collection = client.get_collection(name="quant_research")
```

### 3.3 add——添加文档

```python
collection.add(
    documents=["2024年新能源车销量同比增长35%", "央行降准0.5个百分点"],
    metadatas=[{"type": "行业"}, {"type": "宏观"}],
    ids=["doc1", "doc2"]
)
```

| 参数 | 含义 | 是否必需 |
|------|------|----------|
| `documents` | 文档内容列表 | 与embeddings二选一 |
| `metadatas` | 元数据列表 | 可选 |
| `ids` | 唯一标识列表 | **必需** |
| `embeddings` | 预计算向量 | 与documents二选一 |

### 3.4 query——相似性搜索

```python
results = collection.query(
    query_texts=["新能源车市场表现如何？"],
    n_results=2,
    where={"type": "行业"}   # 元数据过滤
)
print("检索结果:", results['documents'])
```

| 参数 | 含义 | 默认值 |
|------|------|--------|
| `query_texts` | 查询文本列表 | 与query_embeddings二选一 |
| `n_results` | 返回结果数 | 10 |
| `where` | 元数据过滤条件 | None |
| `include` | 返回字段 | ['documents', 'metadatas', 'distances'] |

### 3.5 Search API——高级搜索

Chroma 的 Search API 提供了统一的搜索接口，替代了原有的 `query()` 和 `get()` 方法：

```python
from chromadb import Search, K, Knn

search = (
    Search()
    .where(K("category") == "science")
    .limit(10)
    .select(K.DOCUMENT, K.SCORE)
)

result = collection.search(search.rank(Knn(query="量子计算最新进展")))
```

## 4. 量化应用：研报知识库

```python
import chromadb

client = chromadb.PersistentClient(path="./research_db")
collection = client.create_collection("reports")

# 添加研报片段
collection.add(
    documents=[
        "新能源车渗透率突破40%，产业链上游锂矿受益明显",
        "半导体库存周期见底，预计Q3迎来拐点，关注设备龙头",
        "消费复苏不及预期，白酒板块估值承压",
    ],
    metadatas=[
        {"industry": "新能源", "date": "2024-01"},
        {"industry": "半导体", "date": "2024-03"},
        {"industry": "消费", "date": "2024-02"},
    ],
    ids=["r1", "r2", "r3"]
)

# 检索
results = collection.query(
    query_texts=["新能源车产业链机会"],
    n_results=1
)
print(results['documents'])
```
