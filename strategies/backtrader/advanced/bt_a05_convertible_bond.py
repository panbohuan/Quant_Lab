# -*- coding: utf-8 -*-
# ==========================================================================================
# 【backtrader 本地回测版 · 可离线运行】对应聚宽版：strategies/joinquant/advanced/a05_convertible_bond.py
#
# 回测内核：backtrader（官方开源框架）｜数据：btlab.datasource（免费，无需聚宽账号）
# 运行方式（项目根目录）：python strategies/backtrader/advanced/bt_a05_convertible_bond.py
#
# 与聚宽版的差异（重要，务必了解）：
#   1) 聚宽可查任意历史时点的**转股溢价率**；本地免费源（新浪/东财）只有
#      **当前时点**的转股溢价率快照。因此本策略使用静态溢价率，
#      双低指标实际上退化为「以低价为主、静态溢价率微调」——
#      这与聚宽版"真实双低"的行为不完全一致。
#   2) 回测区间固定为 2019-01-01 ~ 2025-06-30，并只保留**数据覆盖度 >= 50%** 的转债。
#      区间中途被强赎/到期退市的转债，其持仓按最后成交价冻结（近似视为到期赎回），
#      存在小幅偏差；同时样本只含"活下来"的转债，存在幸存者偏差。
#   3) 未计入转债的 T+0 交易、赎回条款触发等细节。
# ==========================================================================================
"""
================================================================================
进阶策略 5：可转债双低策略（Convertible Bond）· backtrader 本地版
================================================================================
策略类型：跨品种 / 可转债
难度等级：★★★★☆
核心思路：在可转债中选"价格低 + 转股溢价率低"的品种。
          低价提供债底保护（下有保底），低溢价率保留股性弹性（上不封顶）。

【经典双低公式】
      双低值 = 转债价格 + 转股溢价率(%)
      双低值越小越好 → 越低越"便宜"

【学习重点】
  - 可转债的"债性"与"股性"：价格接近 100 元 → 债性强；转股溢价率低 → 股性强
  - "下有保底、上不封顶"的非对称收益结构（本质是内嵌看涨期权）
  - 与股票策略的差异：转债有 T+0、无涨跌停（部分）、可被强制赎回
  - 数据可得性对策略复现的影响（溢价率只有快照，无法做真实历史双低）
================================================================================
"""
import os
import sys

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from btlab.datasource import (load_daily, load_bond_daily, listed_bonds,  # noqa: E402
                             bond_symbol)
from btlab.runner import PanelStrategy, run_strategy                       # noqa: E402

# ============================ 回测参数 ============================
START = '2019-01-01'
END = '2025-06-30'
CASH = 1_000_000
BENCHMARK = '000300'
PLOT = os.path.join('results', 'bt_a05_result.png')

MAX_CANDIDATES = 60         # 先按发行规模取前 N 只作为候选池
MIN_COVERAGE = 0.50         # 数据覆盖度下限（覆盖不到区间的转债会被剔除）
TOPN = 5                    # 持有双低值最小的 5 只


class ConvertibleDoubleLow(PanelStrategy):
    """可转债双低：双低值 = 现价 + 转股溢价率(%)，取最小的 TOPN 只，每月等权。"""

    params = (
        ('topn', TOPN),
        ('rebalance', 'monthly'),
        ('premium', None),          # 静态溢价率快照 {代码: 溢价率(%)}，由 main() 注入
    )

    def on_rebalance(self, cur):
        premium = self.p.premium or {}
        scored = {}
        for code, prem in premium.items():
            if code not in set(self.getdatanames()):
                continue
            d = self.getdatabyname(code)
            if not self.live(d, cur):
                continue
            price = d.close[0]
            if price <= 0:
                continue
            prem = 0.0 if pd.isna(prem) else float(prem)
            scored[code] = price + prem          # 双低值：越小越便宜
        if len(scored) < self.p.topn:
            return
        target = sorted(scored, key=scored.get)[:self.p.topn]
        self.equal_weight_order(target, cur)


def build_bond_universe():
    """构造可转债候选池：按发行规模取前 N 只，剔除数据覆盖不足的。"""
    print(f'[1/3] 从已上市转债中取发行规模最大的 {MAX_CANDIDATES} 只 ...')
    table = listed_bonds(before=START, top=MAX_CANDIDATES)
    print(f'      候选 {len(table)} 只（上市时间均早于 {START}）')

    print('[2/3] 加载转债日线并检查数据覆盖度 ...')
    span_start = pd.Timestamp(START)
    span_end = pd.Timestamp(END)
    total_days = len(pd.bdate_range(span_start, span_end))
    data, premium = {}, {}
    for _, row in table.iterrows():
        code = row['bond_code']
        try:
            df = load_bond_daily(code, start=START, end=END)
        except Exception:  # noqa: BLE001
            continue
        if len(df) < total_days * MIN_COVERAGE:
            continue
        data[bond_symbol(code)] = df
        premium[bond_symbol(code)] = row['premium']
    print(f'      数据可用转债 {len(data)} 只（覆盖度 >= {MIN_COVERAGE:.0%}）')
    data['__CAL__'] = load_daily(BENCHMARK, start=START, end=END)
    return data, premium


def main():
    data, premium = build_bond_universe()
    if len(data) <= 1:
        print('可用转债样本不足，无法回测。请检查网络或放宽 MIN_COVERAGE。')
        return

    print('[3/3] 开始 backtrader 回测 ...')
    run_strategy(ConvertibleDoubleLow, data, cash=CASH, benchmark=BENCHMARK,
                 title='进阶5 可转债双低策略（backtrader · 价格+溢价率）',
                 plot_path=PLOT, premium=premium)


if __name__ == '__main__':
    main()
