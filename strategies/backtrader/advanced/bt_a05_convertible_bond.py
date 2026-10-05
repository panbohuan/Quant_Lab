# -*- coding: utf-8 -*-
# 【backtrader 本地回测版】运行：python strategies/backtrader/advanced/bt_a05_convertible_bond.py
# 对应聚宽版：strategies/joinquant/advanced/a05_convertible_bond.py
# 详细讲解：docs/backtrader/advanced/05_convertible_bond.md
"""
策略 5：低价可转债轮动（backtrader 本地版）
类型：跨品种 / 可转债 ｜ 难度：★★★★☆
核心思路：在可转债里选价格最低的 TOPN 只等权持有，价格低意味着债底保护强、下行有限。
注意：经典「双低」需要历史转股溢价率，免费源只有当前快照，本地版因此只用历史价格。
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

MAX_CANDIDATES = 60         # 候选池：按发行规模取前 N 只
MIN_COVERAGE = 0.50         # 数据覆盖度下限（区间内数据太少的转债剔除）
TOPN = 5                    # 持有价格最低的 5 只


class LowPriceBond(PanelStrategy):
    """低价转债轮动：按现价升序取 TOPN 只，每月等权。"""

    params = (('topn', TOPN), ('rebalance', 'monthly'),)

    def on_rebalance(self, cur):
        scored = {}
        for d in self.tradables:
            if not self.live(d, cur):
                continue
            price = d.close[0]
            if price > 0:
                scored[d._name] = price
        if len(scored) < self.p.topn:
            return
        target = sorted(scored, key=scored.get)[:self.p.topn]
        self.equal_weight_order(target, cur)


def build_bond_universe():
    """构造可转债候选池：按发行规模取前 N 只，剔除数据覆盖不足的。

    注意：listed_bonds 用的是**当前**转债列表（只含今天还存续的品种），
    天然带幸存者偏差，只能当作教学用的候选池。
    """
    print(f'[1/3] 从已上市转债中取发行规模最大的 {MAX_CANDIDATES} 只 ...')
    table = listed_bonds(before=START, top=MAX_CANDIDATES)
    print(f'      候选 {len(table)} 只（上市时间均早于 {START}）')

    print('[2/3] 加载转债日线并检查数据覆盖度 ...')
    total_days = len(pd.bdate_range(pd.Timestamp(START), pd.Timestamp(END)))
    data = {}
    for _, row in table.iterrows():
        code = row['bond_code']
        try:
            df = load_bond_daily(code, start=START, end=END)
        except Exception:  # noqa: BLE001
            continue
        if len(df) < total_days * MIN_COVERAGE:
            continue
        data[bond_symbol(code)] = df
    print(f'      数据可用转债 {len(data)} 只（覆盖度 >= {MIN_COVERAGE:.0%}）')
    data['__CAL__'] = load_daily(BENCHMARK, start=START, end=END)
    return data


def main():
    data = build_bond_universe()
    if len(data) <= 1:
        print('可用转债样本不足，无法回测。请检查网络或放宽 MIN_COVERAGE。')
        return

    print('[3/3] 开始 backtrader 回测 ...')
    run_strategy(LowPriceBond, data, cash=CASH, benchmark=BENCHMARK,
                 title='进阶5 低价可转债轮动（backtrader · 价格升序）',
                 plot_path=PLOT)


if __name__ == '__main__':
    main()
