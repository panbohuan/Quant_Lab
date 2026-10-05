# -*- coding: utf-8 -*-
# 【backtrader 本地回测版】运行：python strategies/backtrader/beginner/bt_s04_size_cap.py
# 对应聚宽版：strategies/joinquant/beginner/s04_size_cap.py
# 详细讲解：docs/backtrader/beginner/04_size_cap.md
"""
策略 4：单因子小市值选股策略（Size / 市值因子）
类型：单因子选股（基本面·规模因子） ｜ 难度：★★☆☆☆
核心思路：小市值效应——长期看，小市值股票的平均收益高于大市值股票（A股尤甚）。
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from btlab.datasource import load_daily, load_index_members           # noqa: E402
from btlab.runner import (PanelStrategy, run_strategy, load_universe,  # noqa: E402
                          value_panel, asof)

# ============================ 回测参数 ============================
START = '2018-01-01'
END = None
CASH = 1_000_000
BENCHMARK = '000300'
PLOT = os.path.join('results', 'bt_s04_result.png')

UNIVERSE_SIZE = 40
TOPN = 10
FACTOR = 'total_mv'         # 'total_mv' 总市值 / 'circ_mv' 流通市值


class SmallCap(PanelStrategy):
    """小市值选股：按总市值升序取最小的 TOPN 只，每月等权调仓。"""

    params = (('topn', TOPN), ('rebalance', 'monthly'),)

    def __init__(self):
        super().__init__()
        codes = [d._name for d in self.tradables]
        print(f'  预加载 {len(codes)} 只股票的市值面板 ...')
        self.panel = value_panel(codes, FACTOR)

    def on_rebalance(self, cur):
        row = asof(self.panel, cur)
        if row is None or len(row) < self.p.topn:
            return
        row = row[row > 0]
        names = [c for c in row.sort_values().index[:self.p.topn]   # 升序 = 市值最小
                 if c in self.getdatanames()]
        self.equal_weight_order(names, cur)


def main():
    print(f'[1/3] 获取沪深300成分股（前 {UNIVERSE_SIZE} 只）...')
    codes = load_index_members('000300')[:UNIVERSE_SIZE]

    print('[2/3] 加载日线 ...')
    data = load_universe(codes, start=START, end=END, adjust='qfq', label='股票池')
    data['__CAL__'] = load_daily(BENCHMARK, start=START, end=END)

    print('[3/3] 开始 backtrader 回测 ...')
    run_strategy(SmallCap, data, cash=CASH, benchmark=BENCHMARK,
                 title=f'策略4 单因子小市值选股（backtrader · 因子={FACTOR}）',
                 plot_path=PLOT)


if __name__ == '__main__':
    main()
