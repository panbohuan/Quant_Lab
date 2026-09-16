# Quant Lab — PandaAI 因子挖掘实验室

基于 PandaAI 平台（pandaaiquant.com）的 A 股量化因子挖掘工作区，围绕两个
社区 Skill 组织：支持 AI 主导盲挖的 `skill-factor-mining-pandaai`，以及面向
第四届因子大赛的 `skill-pandaai-factor-online`。所有回测结果均为历史诊断，
仅供研究，不构成投资建议。

## JoinQuant 量化策略学习（新增）

本仓库同时收录了一套面向量化初学者的 **聚宽(JoinQuant) 策略学习库**，位于
[`joinquant_strategies/`](joinquant_strategies/) 目录，包含 **10 个从简单到复杂的完整策略**：

技术择时 → 单因子选股 → 多因子合成 → 因子中性化 → 因子 IC 加权 → 机器学习选股。

每个策略都附带**完整可运行代码（strategies/）+ 逐行详解文档（docs/）**，涵盖
思路讲解、算法结构、聚宽函数解析与基本面概念（PE/PB/ROE/IC/IR 等）。

详见 [joinquant_strategies/README.md](joinquant_strategies/README.md)。

## 环境

| 组件        | 版本/要求              | 说明                                            |
| ----------- | ---------------------- | ----------------------------------------------- |
| Python      | >= 3.10（本机 3.13.9） | 脚本解释器                                      |
| uv          | 0.10+                  | 隔离安装 pandaai-cli                            |
| pandaai-cli | 0.1.7                  | PandaAI 官方 CLI，`uv tool install pandaai-cli` |
| pdfplumber  | 0.11+                  | 仅 PDF 文档提取模式需要                         |

登录凭据保存在 `~/.pandaai/config.yaml`，通过交互式 `pandaai-cli login` 完成，
凭据不进入仓库。

## 目录结构

```
Quant_Lab/
├── skill-factor-mining-pandaai/    # 盲挖模式 Skill（三阶段遗传引擎）
│   ├── SKILL.md                    # 技能定义与工作流
│   ├── references/                 # CLI 参考、盲挖工作流、算子映射、字段来源
│   └── scripts/                    # wrapper / 候选生成 / 遗传引擎 / 批量执行
├── skill-pandaai-factor-online/    # 在线挖掘 Skill（第四届因子大赛）
│   ├── SKILL.zh-CN.md              # 中文技能定义（体检→参数→试探→全区间→样本外）
│   ├── references/                 # 348 字段 / 137 算子 / 949 回测目录 / 比赛规则
│   └── scripts/                    # bootstrap / batch / analyze / competition_proxy
├── mining_runs/                    # 实际挖掘产出（断点续跑、研究台账）
│   ├── competition/                # 大赛候选批次（试探→主窗口→样本外）
│   └── smallcap_reversal/          # 小市值反转盲挖批次（第一阶段）
└── skill-pandaai-factor-online.tar.gz  # 网络受限时通过 codeload 下载的归档
```

## 快速开始

```powershell
# 1. 体检（不花算力）：环境、登录、余额、因子数量
cd skill-pandaai-factor-online
python scripts/bootstrap.py

# 2. 批量运行候选（每行: 名称 ~ 公式 ~ 方向）
python scripts/batch.py ..\mining_runs\competition\candidates_probe.txt `
  --start 20250101 --end 20250331 --cycle 3 --group-number 10 --prefix "probe-"

# 3. 重建报告（不花算力）
python scripts/batch.py ..\mining_runs\competition\candidates_probe.txt `
  --start 20250101 --end 20250331 --cycle 3 --report-only
```

Windows 下建议先设置 `$env:PYTHONUTF8=1`，避免 GBK 控制台编码问题。

## 研究流程（比赛口径）

1. **定参数**：调仓周期（3 日，提交后锁定）、分组数（10）、单边成本（0.3%）。
2. **短区间试探**（约 3 个月）：便宜地暴露公式/字段错误。
3. **5 年主窗口**（20210913-20260912，对齐比赛 A 口径）：幸存者评估排序。
4. **样本外**（20160901-20210831）：幸存者换不重叠更早区间复核。
5. **复盘**：机制归因、与市值相关性检查、成本折算、按年拆分。

## 已探明的平台约束（2026-09 实测）

- **回测窗口上限 5 年**：超过即运行失败（`回测时间范围不能超过5年`），
  普通账号无 10 年权限；窗口必须精确 ≤ 5 年（20210901-20260912 会因超出
  11 天被拒）。
- **计费**：短窗口每次运行约扣 2 算力，5 年长窗口每次约扣 4 算力；失败运行
  同样扣费。
- **CLI 0.1.7 与 Skill 参考（基于 0.1.2/0.1.3）的差异**：
  `factor_list --offset` 已改为 `--page`；`--json` 会静默关闭 `--download`；
  `factor_delete --pattern` 不可用，须按 id 位置参数删除；
  控制台打印 emoji 在 GBK 下会崩溃（设 `PYTHONUTF8=1` 规避）。
- **比赛口径**：IC 为 Pearson、RankIC 为 Spearman；A=历史（20%）/
  B=样本外（35%）/ C=扣成本多头组合（45%）；因子池 ≤ 50 只，删改仅限每月
  1-3 日。

## 当前进展

- 账户：已登录，算力余额约 400（2026-09-13）。
- 试探批次：12 个候选（6 个假设族）3 个月窗口全部语法通过，低成交额族
  短窗口净值最优。
- 5 年主窗口批次：rev5 已完成（IC 显著为负但 3 日调仓下换手成本过高）；
  rev20/bias20/small_rev10/low_amount/low_price/low_vol 已跑，low_price
  净值 +6.51%、low_amount +4.05% 暂居前二；剩余候选待继续。

## 安全边界

- 不提交、不打印 token / 密码 / 配置文件内容。
- 每次运行都扣算力：先 `balance`，先短窗口试探，再批量。
- 回测结果是历史诊断，不代表未来收益；本地计算结果均为比赛规则代理，
  官方积分以平台后台结算为准。
