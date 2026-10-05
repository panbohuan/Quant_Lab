# -*- coding: utf-8 -*-
# 【backtrader 本地回测版】运行：python strategies/backtrader/beginner/bt_s08_factor_neutralize.py
# 对应聚宽版：strategies/joinquant/beginner/s08_factor_neutralize.py
# 详细讲解：docs/backtrader/beginner/08_factor_neutralize.md
"""
策略 8：因子中性化选股（市值 + 行业中性化）
类型：多因子进阶（因子提纯） ｜ 难度：★★★★☆
核心思路：原始因子往往"污染"了其他风格的影响。例如动量因子可能与市值、行业强相关。
"""
import os
import sys

import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from btlab.datasource import load_daily, load_index_members           # noqa: E402
from btlab.runner import (PanelStrategy, run_strategy, load_universe,  # noqa: E402
                          value_panel, asof, industry_map)

# ============================ 回测参数 ============================
START = '2018-01-01'
END = None
CASH = 1_000_000
BENCHMARK = '000300'
PLOT = os.path.join('results', 'bt_s08_result.png')

UNIVERSE_SIZE = 40
TOPN = 10
LOOKBACK = 60               # 被中性化的因子 = 60 日动量
NEUTRALIZE_BY = ('logmv', 'industry')   # 中性化维度：对数市值 + 行业


def neutralize(factor, logmv=None, industry=None):
    """对 factor 做截面回归取残差。logmv / industry 为 None 表示不中性化该维度。"""
    y = pd.Series(factor, dtype=float)
    X = pd.DataFrame(index=y.index)
    if logmv is not None:
        X['logmv'] = pd.Series(logmv, dtype=float).reindex(y.index)
    if industry is not None:
        # 行业缺失的股票归入「未知」类别，避免整只股票被剔除出回归样本
        ind = pd.Series(industry).reindex(y.index).fillna('未知')
        dummies = pd.get_dummies(ind, prefix='ind', drop_first=True)
        X = pd.concat([X, dummies.astype(float)], axis=1)
    if X.shape[1] == 0:
        return y - y.mean()
    X = sm.add_constant(X, has_constant='add')
    mask = y.notna() & X.notna().all(axis=1)
    if mask.sum() < X.shape[1] + 5:            # 样本太少，退化为去均值
        return y - y.mean()
    model = sm.OLS(y[mask], X[mask]).fit()
    resid = pd.Series(np.nan, index=y.index)
    resid[mask] = model.resid
    return resid


class FactorNeutralize(PanelStrategy):
    """动量因子做「对数市值 + 申万一级行业」中性化，按纯因子（残差）选股。"""

    params = (('topn', TOPN), ('lookback', LOOKBACK), ('rebalance', 'monthly'),)

    def __init__(self):
        super().__init__()
        codes = [d._name for d in self.tradables]
        print('  预加载市值面板 ...')
        self.mv = value_panel(codes, 'total_mv')
        print('  构建行业映射（首次较慢，之后读缓存）...')
        self.ind_map = industry_map(codes)

    def on_rebalance(self, cur):
        mv = asof(self.mv, cur)
        if mv is None:
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
        if len(mom) < self.p.topn + 5:
            return

        mv = mv[mv > 0]
        common = mom.index.intersection(mv.index)
        mom, mv = mom[common], mv[common]
        logmv = np.log(mv)
        ind = pd.Series({c: self.ind_map.get(c) for c in common})

        use_ind = ind if 'industry' in NEUTRALIZE_BY and ind.notna().any() else None
        pure = neutralize(mom, logmv=logmv if 'logmv' in NEUTRALIZE_BY else None,
                          industry=use_ind)
        pure = pure.dropna()
        if len(pure) < self.p.topn:
            return
        names = pure.sort_values(ascending=False).index[:self.p.topn].tolist()
        self.equal_weight_order(names, cur)


def main():
    print(f'[1/3] 获取沪深300成分股（前 {UNIVERSE_SIZE} 只）...')
    codes = load_index_members('000300')[:UNIVERSE_SIZE]

    print('[2/3] 加载日线 ...')
    data = load_universe(codes, start=START, end=END, adjust='qfq', label='股票池')
    data['__CAL__'] = load_daily(BENCHMARK, start=START, end=END)

    print('[3/3] 开始 backtrader 回测 ...')
    run_strategy(FactorNeutralize, data, cash=CASH, benchmark=BENCHMARK,
                 title='策略8 因子中性化选股（backtrader · 动量 对 市值+行业 中性化）',
                 plot_path=PLOT)


if __name__ == '__main__':
    main()
