# -*- coding: utf-8 -*-
# 【backtrader 本地回测版】运行：python strategies/backtrader/advanced/bt_a10_sentiment.py
# 对应聚宽版：strategies/joinquant/advanced/a10_sentiment.py
# 详细讲解：docs/backtrader/advanced/10_sentiment.md
"""
策略 10：舆情情绪策略（量价情绪代理版）
类型：另类数据 / 情绪分析（代理变量） ｜ 难度：★★★★★
核心思路：情绪驱动的定价偏差——情绪温度高的股票短期更容易被追捧上涨。
"""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from btlab.datasource import load_daily, load_index_members           # noqa: E402
from btlab.runner import PanelStrategy, run_strategy, load_universe    # noqa: E402

# ============================ 回测参数 ============================
START = '2015-01-01'
END = None
CASH = 1_000_000
BENCHMARK = '000300'
PLOT = os.path.join('results', 'bt_a10_result.png')

UNIVERSE_SIZE = 40
TOPN = 10
LOOKBACK = 20               # 动量回看期
SHORT_WIN = 5               # 情绪观测窗口（短）
LONG_WIN = 60               # 情绪基准窗口（长）


def zscore(s):
    s = pd.Series(s, dtype=float)
    return (s - s.mean()) / (s.std() + 1e-12)


class SentimentProxy(PanelStrategy):
    """量价情绪代理因子 + 动量 合成选股。"""

    params = (('topn', TOPN), ('lookback', LOOKBACK), ('rebalance', 'monthly'),)

    def _sentiment(self, d):
        """返回 (量能异常, 波动放大, 隔夜跳空) 三个情绪代理值；数据不足返回 None。"""
        closes = self.hist_close(d, self.p.lookback + 1)
        highs, lows = d.high.get(size=SHORT_WIN), d.low.get(size=SHORT_WIN)
        opens, vols = d.open.get(size=SHORT_WIN), d.volume.get(size=LONG_WIN)
        if (closes is None or closes[0] <= 0 or len(highs) < SHORT_WIN
                or len(opens) < SHORT_WIN or len(vols) < LONG_WIN):
            return None
        prev_close = closes[-(SHORT_WIN + 1):-1] if len(closes) > SHORT_WIN else None
        if prev_close is None or len(prev_close) < SHORT_WIN:
            return None
        amp = float(np.mean([(highs[i] - lows[i]) / closes[-1] for i in range(SHORT_WIN)]))
        gap = float(np.mean([abs(opens[i] / prev_close[i] - 1.0) for i in range(SHORT_WIN)]))
        vol_ratio = float(np.mean(vols[-SHORT_WIN:]) / (np.mean(vols) + 1e-9))
        return vol_ratio, amp, gap

    def on_rebalance(self, cur):
        rows = {}
        for d in self.tradables:
            if not self.live(d, cur):
                continue
            sent = self._sentiment(d)
            if sent is None:
                continue
            closes = self.hist_close(d, self.p.lookback + 1)
            mom = closes[-1] / closes[0] - 1.0
            rows[d._name] = {'vol_ratio': sent[0], 'amp': sent[1], 'gap': sent[2], 'mom': mom}
        if len(rows) < self.p.topn:
            return
        df = pd.DataFrame(rows).T

        # 情绪分 = 量能异常 + 波动放大 + 隔夜跳空（各自标准化后相加）
        sentiment = (zscore(df['vol_ratio']) + zscore(df['amp']) + zscore(df['gap']))
        score = zscore(sentiment) + zscore(df['mom'])     # 情绪 + 动量
        names = score.sort_values(ascending=False).index[:self.p.topn].tolist()
        self.equal_weight_order(names, cur)


def main():
    print(f'[1/3] 获取沪深300成分股（前 {UNIVERSE_SIZE} 只）...')
    codes = load_index_members('000300')[:UNIVERSE_SIZE]

    print('[2/3] 加载日线 ...')
    data = load_universe(codes, start=START, end=END, adjust='qfq', label='股票池')
    data['__CAL__'] = load_daily(BENCHMARK, start=START, end=END)

    print('[3/3] 开始 backtrader 回测 ...')
    run_strategy(SentimentProxy, data, cash=CASH, benchmark=BENCHMARK,
                 title='进阶10 舆情情绪策略（backtrader · 量价情绪代理因子）',
                 plot_path=PLOT)


if __name__ == '__main__':
    main()
