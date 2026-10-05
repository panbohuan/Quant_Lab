# -*- coding: utf-8 -*-
# 【backtrader 本地回测版】运行：python strategies/backtrader/beginner/bt_s07_multi_factor_score.py
# 对应聚宽版：strategies/joinquant/beginner/s07_multi_factor_score.py
# 详细讲解：docs/backtrader/beginner/07_multi_factor_score.md
"""
策略 7：多因子打分模型（四因子：质量 + 估值 + 动量 + 规模）
类型：多因子选股（z-score 标准化 + 线性加权） ｜ 难度：★★★★☆
核心思路：综合四大类经典因子，用 z-score 标准化后按方向加权合成综合分：
"""
import os
import sys

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from btlab.datasource import load_daily, load_index_members           # noqa: E402
from btlab.runner import (PanelStrategy, run_strategy, load_universe,  # noqa: E402
                          value_panel, roe_panel, asof)

# ============================ 回测参数 ============================
START = '2018-01-01'
END = None
CASH = 1_000_000
BENCHMARK = '000300'
PLOT = os.path.join('results', 'bt_s07_result.png')

UNIVERSE_SIZE = 40
TOPN = 10
LOOKBACK = 60
ROE_LAG = 45                # 报告期 → 可用日 的滞后天数


def zscore(s):
    """z-score 标准化（分母加 1e-12 防止标准差为 0 时除零）。"""
    s = pd.Series(s, dtype=float)
    return (s - s.mean()) / (s.std() + 1e-12)


class MultiFactorScore(PanelStrategy):
    """四因子 z-score 加权打分选股。"""

    params = (('topn', TOPN), ('lookback', LOOKBACK), ('rebalance', 'monthly'),)

    def __init__(self):
        super().__init__()
        codes = [d._name for d in self.tradables]
        print('  预加载因子面板（PB / 市值 / ROE）...')
        self.pb = value_panel(codes, 'pb')
        self.mv = value_panel(codes, 'total_mv')
        self.roe = roe_panel(codes, lag_days=ROE_LAG)

    def on_rebalance(self, cur):
        pb, mv, roe = asof(self.pb, cur), asof(self.mv, cur), asof(self.roe, cur)
        if pb is None or mv is None or roe is None:
            return

        # 1) 行情类因子：动量
        mom = {}
        for d in self.tradables:
            if not self.live(d, cur):
                continue
            closes = self.hist_close(d, self.p.lookback + 1)
            if closes is None or closes[0] <= 0:
                continue
            mom[d._name] = closes[-1] / closes[0] - 1.0
        mom = pd.Series(mom, dtype=float)

        # 2) 四个因子对齐到共同股票集合
        common = mom.index
        for s in (pb, mv, roe):
            common = common.intersection(s.index)
        if len(common) < self.p.topn:
            return
        mom, pb, mv, roe = mom[common], pb[common], mv[common], roe[common]
        pb = pb[pb > 0]
        mv = mv[mv > 0]
        common = pb.index.intersection(mv.index)
        if len(common) < self.p.topn:
            return
        mom, pb, mv, roe = mom[common], pb[common], mv[common], roe[common]

        # 3) 标准化 + 按方向加权合成
        score = (zscore(roe)             # 质量 +
                 - zscore(pb)            # 估值 -
                 + zscore(mom)           # 动量 +
                 - zscore(mv))           # 规模 -
        names = score.sort_values(ascending=False).index[:self.p.topn].tolist()
        self.equal_weight_order(names, cur)


def main():
    print(f'[1/3] 获取沪深300成分股（前 {UNIVERSE_SIZE} 只）...')
    codes = load_index_members('000300')[:UNIVERSE_SIZE]

    print('[2/3] 加载日线 ...')
    data = load_universe(codes, start=START, end=END, adjust='qfq', label='股票池')
    data['__CAL__'] = load_daily(BENCHMARK, start=START, end=END)

    print('[3/3] 开始 backtrader 回测 ...')
    run_strategy(MultiFactorScore, data, cash=CASH, benchmark=BENCHMARK,
                 title='策略7 多因子打分模型（backtrader · ROE/PB/动量/市值 z-score）',
                 plot_path=PLOT)


if __name__ == '__main__':
    main()
