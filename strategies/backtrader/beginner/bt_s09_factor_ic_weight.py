# -*- coding: utf-8 -*-
# ==========================================================================================
# 【backtrader 本地回测版 · 可离线运行】对应聚宽版：strategies/joinquant/beginner/s09_factor_ic_weight.py
#
# 回测内核：backtrader（官方开源框架）｜数据：btlab.datasource（免费，无需聚宽账号）
# 运行方式（项目根目录）：python strategies/backtrader/beginner/bt_s09_factor_ic_weight.py
# ==========================================================================================
"""
================================================================================
策略 9：因子 IC / IR 加权选股（动态权重多因子）· backtrader 本地版
================================================================================
策略类型：多因子进阶（因子有效性度量 + 动态加权）
难度等级：★★★★★
核心思路：前面策略用"等权"合成因子，但不同因子的有效性随时间变化。
          本策略引入 IC（信息系数）与 IR（信息比率）度量因子有效性：
              IC_t = corr( 因子_t , 下一期实际收益_t )
              IR   = mean(滚动 IC) / std(滚动 IC)
          用 IR 作为因子权重动态加权。IR 为负的因子直接归零（不反向使用，避免不稳定）。

【学习重点】
  - IC：因子值与"未来收益"的截面相关系数（衡量因子预测能力的方向与强弱）
  - IR：IC 的均值 / IC 的标准差（衡量因子预测能力的**稳定性**）
  - 滚动窗口（本策略取近 6 期）动态更新权重
  - **时序纪律**：本期只能用上期因子 + 本期已实现收益来算 IC，
    下一期收益要等下一期结束才知道——这是 IC 计算最容易犯未来函数错误的地方
================================================================================
"""
import os
import sys

import numpy as np
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
PLOT = os.path.join('results', 'bt_s09_result.png')

UNIVERSE_SIZE = 40
TOPN = 10
LOOKBACK = 60
ROE_LAG = 45
IC_WINDOW = 6               # 滚动 IC 窗口（期）
FACTORS = ('mom', 'roe', 'pb', 'mv')


def zscore(s):
    s = pd.Series(s, dtype=float)
    return (s - s.mean()) / (s.std() + 1e-12)


class ICFactorWeight(PanelStrategy):
    """用滚动 IC/IR 动态加权四个因子，按照有效性自动决定谁说了算。"""

    params = (('topn', TOPN), ('lookback', LOOKBACK), ('rebalance', 'monthly'),
              ('ic_window', IC_WINDOW),)

    def __init__(self):
        super().__init__()
        codes = [d._name for d in self.tradables]
        print('  预加载因子面板（PB / 市值 / ROE）...')
        self.pb = value_panel(codes, 'pb')
        self.mv = value_panel(codes, 'total_mv')
        self.roe = roe_panel(codes, lag_days=ROE_LAG)
        self.prev_factors = None      # 上一期的因子快照
        self.prev_price = {}          # 上一期的价格（用于算本期已实现收益）
        self.ic_hist = {k: [] for k in FACTORS}

    def _current_factors(self, cur):
        """算出本期四个因子，并对齐到同一股票集合。返回 (dict, {code: price})。"""
        pb, mv, roe = asof(self.pb, cur), asof(self.mv, cur), asof(self.roe, cur)
        if pb is None or mv is None or roe is None:
            return None, None
        mom, price = {}, {}
        for d in self.tradables:
            if not self.live(d, cur):
                continue
            closes = self.hist_close(d, self.p.lookback + 1)
            if closes is None or closes[0] <= 0:
                continue
            mom[d._name] = closes[-1] / closes[0] - 1.0
            price[d._name] = d.close[0]
        if len(mom) < self.p.topn:
            return None, None
        mom = pd.Series(mom, dtype=float)
        pb, mv = pb[pb > 0], mv[mv > 0]
        common = mom.index.intersection(pb.index).intersection(mv.index).intersection(roe.index)
        if len(common) < self.p.topn:
            return None, None
        return ({'mom': mom[common], 'roe': roe[common],
                 'pb': pb[common], 'mv': mv[common]}, price)

    def _update_ic(self, price):
        """用「上期因子 + 本期已实现收益」更新各因子的 IC。"""
        if self.prev_factors is None:
            return
        codes = [c for c in self.prev_factors['mom'].index
                 if c in price and self.prev_price.get(c, 0) > 0]
        if len(codes) < 10:
            return
        realized = pd.Series({c: price[c] / self.prev_price[c] - 1.0 for c in codes})
        for k in FACTORS:
            f = self.prev_factors[k].reindex(codes)
            r = realized.reindex(codes)
            mask = f.notna() & r.notna()
            if mask.sum() >= 10:
                self.ic_hist[k].append(float(f[mask].corr(r[mask])))
        latest = {k: round(v[-1], 3) for k, v in self.ic_hist.items() if v}
        if latest:
            print(f'  最新一期 IC: {latest}')

    def _weights(self):
        """IR = mean(IC)/std(IC)；IC 不足或 IR 为负时退化为等权 1.0。"""
        w = {}
        for k in FACTORS:
            arr = [x for x in self.ic_hist[k][-self.p.ic_window:] if pd.notna(x)]
            if len(arr) >= 3 and np.std(arr) > 1e-9:
                ir = float(np.mean(arr) / np.std(arr))
            else:
                ir = 1.0
            w[k] = max(ir, 0.0)
        if sum(w.values()) <= 0:
            w = {k: 1.0 for k in FACTORS}
        return w

    def on_rebalance(self, cur):
        factors, price = self._current_factors(cur)
        if factors is None:
            return
        self._update_ic(price)
        w = self._weights()

        score = (w['roe'] * zscore(factors['roe'])          # 质量 +
                 - w['pb'] * zscore(factors['pb'])          # 估值 -
                 + w['mom'] * zscore(factors['mom'])        # 动量 +
                 - w['mv'] * zscore(factors['mv']))         # 规模 -
        names = score.sort_values(ascending=False).index[:self.p.topn].tolist()
        self.equal_weight_order(names, cur)

        self.prev_factors = factors
        self.prev_price = price


def main():
    print(f'[1/3] 获取沪深300成分股（前 {UNIVERSE_SIZE} 只）...')
    codes = load_index_members('000300')[:UNIVERSE_SIZE]

    print('[2/3] 加载日线 ...')
    data = load_universe(codes, start=START, end=END, adjust='qfq', label='股票池')
    data['__CAL__'] = load_daily(BENCHMARK, start=START, end=END)

    print('[3/3] 开始 backtrader 回测 ...')
    run_strategy(ICFactorWeight, data, cash=CASH, benchmark=BENCHMARK,
                 title='策略9 因子 IC/IR 加权选股（backtrader · 动态权重多因子）',
                 plot_path=PLOT)


if __name__ == '__main__':
    main()
