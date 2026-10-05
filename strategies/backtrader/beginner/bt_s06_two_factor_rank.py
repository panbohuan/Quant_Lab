# -*- coding: utf-8 -*-
# 【backtrader 本地回测版】运行：python strategies/backtrader/beginner/bt_s06_two_factor_rank.py
# 对应聚宽版：strategies/joinquant/beginner/s06_two_factor_rank.py
# 详细讲解：docs/backtrader/beginner/06_two_factor_rank.md
"""
策略 6：双因子组合选股（动量 + 市值，排序打分法）
类型：双因子选股（量价 + 规模） ｜ 难度：★★★☆☆
核心思路：单因子过于单一，容易受单一风格影响。把两个因子合成：
"""
import os
import sys

import pandas as pd

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
PLOT = os.path.join('results', 'bt_s06_result.png')

UNIVERSE_SIZE = 40
TOPN = 10
LOOKBACK = 60               # 动量回看期


class TwoFactorRank(PanelStrategy):
    """动量 + 小市值：两因子各自排名后相加，取综合排名最优的 TOPN 只。"""

    params = (('topn', TOPN), ('lookback', LOOKBACK), ('rebalance', 'monthly'),)

    def __init__(self):
        super().__init__()
        codes = [d._name for d in self.tradables]
        print('  预加载市值面板 ...')
        self.mv = value_panel(codes, 'total_mv')

    def on_rebalance(self, cur):
        mv = asof(self.mv, cur)
        if mv is None:
            return

        # 1) 从行情数据算动量因子
        mom = {}
        for d in self.tradables:
            if not self.live(d, cur):
                continue
            closes = self.hist_close(d, self.p.lookback + 1)
            if closes is None or closes[0] <= 0:
                continue
            mom[d._name] = closes[-1] / closes[0] - 1.0
        mom = pd.Series(mom, dtype=float)

        # 2) 两个因子对齐到共同的股票集合
        common = mom.index.intersection(mv[mv > 0].index)
        if len(common) < self.p.topn:
            return
        mom, mv = mom[common], mv[common]

        # 3) 排序打分：动量越大名次越小；市值越小名次越小
        score = (-mom).rank() + mv.rank()
        names = score.sort_values().index[:self.p.topn].tolist()
        self.equal_weight_order(names, cur)


def main():
    print(f'[1/3] 获取沪深300成分股（前 {UNIVERSE_SIZE} 只）...')
    codes = load_index_members('000300')[:UNIVERSE_SIZE]

    print('[2/3] 加载日线 ...')
    data = load_universe(codes, start=START, end=END, adjust='qfq', label='股票池')
    data['__CAL__'] = load_daily(BENCHMARK, start=START, end=END)

    print('[3/3] 开始 backtrader 回测 ...')
    run_strategy(TwoFactorRank, data, cash=CASH, benchmark=BENCHMARK,
                 title='策略6 双因子组合选股（backtrader · 动量+市值 排序打分）',
                 plot_path=PLOT)


if __name__ == '__main__':
    main()
