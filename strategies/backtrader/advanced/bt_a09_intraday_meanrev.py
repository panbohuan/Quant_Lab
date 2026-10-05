# -*- coding: utf-8 -*-
# 【backtrader 本地回测版】运行：python strategies/backtrader/advanced/bt_a09_intraday_meanrev.py
# 对应聚宽版：strategies/joinquant/advanced/a09_intraday_meanrev.py
# 详细讲解：docs/backtrader/advanced/09_intraday_meanrev.md
"""
策略 9：短期均值回归 / 超跌反弹策略（日线降频版）
类型：均值回归 / 反转 ｜ 难度：★★★★★
核心思路：捕捉"过度反应"后的修复。股票短期大幅下跌后，往往出现反弹。
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from btlab.datasource import load_daily, load_index_members           # noqa: E402
from btlab.runner import (PanelStrategy, run_strategy, load_universe)  # noqa: E402

# ============================ 回测参数 ============================
START = '2015-01-01'
END = None
CASH = 1_000_000
BENCHMARK = '000300'
PLOT = os.path.join('results', 'bt_a09_result.png')

UNIVERSE_SIZE = 40
TOPN = 10
WINDOW = 5                  # 回看 5 个交易日
THRESHOLD = -0.08           # 累计跌幅超过 8% 才算"超跌"
REBALANCE = 'weekly'        # 每周调仓（约持有 5 个交易日）


class ShortTermReversal(PanelStrategy):
    """短期反转：买过去 WINDOW 日跌幅最大（且超过阈值）的股票，等权持有约一周。"""

    params = (('topn', TOPN), ('window', WINDOW), ('threshold', THRESHOLD),
              ('rebalance', REBALANCE),)

    def on_rebalance(self, cur):
        scores = {}
        for d in self.tradables:
            if not self.live(d, cur):
                continue
            closes = self.hist_close(d, self.p.window + 1)
            if closes is None or closes[0] <= 0:
                continue
            scores[d._name] = closes[-1] / closes[0] - 1.0

        # 只保留"跌破阈值"的超跌股；一个都没有就空仓
        oversold = {k: v for k, v in scores.items() if v <= self.p.threshold}
        if not oversold:
            self.close_all(cur)
            return
        names = sorted(oversold, key=oversold.get)[:self.p.topn]     # 跌得最狠的优先
        self.equal_weight_order(names, cur)


def main():
    print(f'[1/3] 获取沪深300成分股（前 {UNIVERSE_SIZE} 只）...')
    codes = load_index_members('000300')[:UNIVERSE_SIZE]

    print('[2/3] 加载日线 ...')
    data = load_universe(codes, start=START, end=END, adjust='qfq', label='股票池')
    data['__CAL__'] = load_daily(BENCHMARK, start=START, end=END)

    print('[3/3] 开始 backtrader 回测 ...')
    run_strategy(ShortTermReversal, data, cash=CASH, benchmark=BENCHMARK,
                 title='进阶9 短期超跌反弹（backtrader · 日线降频版）',
                 plot_path=PLOT)


if __name__ == '__main__':
    main()
