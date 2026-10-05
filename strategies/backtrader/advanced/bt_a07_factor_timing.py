# -*- coding: utf-8 -*-
# 【backtrader 本地回测版】运行：python strategies/backtrader/advanced/bt_a07_factor_timing.py
# 对应聚宽版：strategies/joinquant/advanced/a07_factor_timing.py
# 详细讲解：docs/backtrader/advanced/07_factor_timing.md
"""
策略 7：因子择时策略（Factor Timing）
类型：因子进阶 / 动态多因子 ｜ 难度：★★★★★
核心思路：根据市场环境动态调整因子权重。市场估值高（贵、拥挤）时超配
"""
import os
import sys

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from btlab.datasource import (load_daily, load_index_members,         # noqa: E402
                             load_index_pe)
from btlab.runner import (PanelStrategy, run_strategy, load_universe,  # noqa: E402
                          value_panel, roe_panel, asof)

# ============================ 回测参数 ============================
START = '2018-01-01'
END = None
CASH = 1_000_000
BENCHMARK = '000300'
PLOT = os.path.join('results', 'bt_a07_result.png')

UNIVERSE_SIZE = 40
TOPN = 10
LOOKBACK = 60
ROE_LAG = 45
HIGH_PCT = 0.70             # 估值分位高于此 → risk-off
LOW_PCT = 0.30              # 估值分位低于此 → risk-on


def zscore(s):
    s = pd.Series(s, dtype=float)
    return (s - s.mean()) / (s.std() + 1e-12)


class FactorTiming(PanelStrategy):
    """按市场估值分位动态切换因子权重的多因子策略。"""

    params = (('topn', TOPN), ('lookback', LOOKBACK), ('rebalance', 'monthly'),)

    def __init__(self):
        super().__init__()
        codes = [d._name for d in self.tradables]
        print('  预加载因子面板（PB / 市值 / ROE）...')
        self.pb = value_panel(codes, 'pb')
        self.mv = value_panel(codes, 'total_mv')
        self.roe = roe_panel(codes, lag_days=ROE_LAG)
        print('  加载沪深300指数 PE（月度，2005 年起）...')
        self.pe = load_index_pe('沪深300')

    def _temperature(self, cur):
        """返回当前 PE 的历史分位（0~1）；历史不足 36 个月则返回 None。"""
        s = self.pe.loc[:pd.Timestamp(cur)].dropna()
        if len(s) < 36:
            return None
        return float((s < s.iloc[-1]).mean())

    def _weights(self, pct):
        if pct is None:
            return {'roe': 1.0, 'pb': 1.0, 'mom': 1.0, 'mv': 1.0}, '均衡(历史不足)'
        if pct > HIGH_PCT:
            return {'roe': 1.5, 'pb': 1.5, 'mom': 0.3, 'mv': 0.5}, '高估 → 防守'
        if pct < LOW_PCT:
            return {'roe': 0.7, 'pb': 0.7, 'mom': 2.0, 'mv': 1.0}, '低估 → 进攻'
        return {'roe': 1.0, 'pb': 1.0, 'mom': 1.0, 'mv': 1.0}, '均衡'

    def on_rebalance(self, cur):
        pb, mv, roe = asof(self.pb, cur), asof(self.mv, cur), asof(self.roe, cur)
        if pb is None or mv is None or roe is None:
            return
        mom = {}
        for d in self.tradables:
            if not self.live(d, cur):
                continue
            closes = self.hist_close(d, self.p.lookback + 1)
            if closes is None or closes[0] <= 0:
                continue
            mom[d._name] = closes[-1] / closes[0] - 1.0
        mom = pd.Series(mom, dtype=float)
        pb, mv = pb[pb > 0], mv[mv > 0]
        common = mom.index.intersection(pb.index).intersection(mv.index).intersection(roe.index)
        if len(common) < self.p.topn:
            return
        mom, pb, mv, roe = mom[common], pb[common], mv[common], roe[common]

        pct = self._temperature(cur)
        w, regime = self._weights(pct)
        print(f'  [{cur}] 估值分位 {"N/A" if pct is None else f"{pct:.0%}"} → {regime}')

        score = (w['roe'] * zscore(roe) - w['pb'] * zscore(pb)
                 + w['mom'] * zscore(mom) - w['mv'] * zscore(mv))
        names = score.sort_values(ascending=False).index[:self.p.topn].tolist()
        self.equal_weight_order(names, cur)


def main():
    print(f'[1/3] 获取沪深300成分股（前 {UNIVERSE_SIZE} 只）...')
    codes = load_index_members('000300')[:UNIVERSE_SIZE]

    print('[2/3] 加载日线 ...')
    data = load_universe(codes, start=START, end=END, adjust='qfq', label='股票池')
    data['__CAL__'] = load_daily(BENCHMARK, start=START, end=END)

    print('[3/3] 开始 backtrader 回测 ...')
    run_strategy(FactorTiming, data, cash=CASH, benchmark=BENCHMARK,
                 title='进阶7 因子择时策略（backtrader · 估值分位动态权重）',
                 plot_path=PLOT)


if __name__ == '__main__':
    main()
