# -*- coding: utf-8 -*-
# 【backtrader 本地回测版】运行：python strategies/backtrader/beginner/bt_s02_momentum.py
# 对应聚宽版：strategies/joinquant/beginner/s02_momentum.py
# 详细讲解：docs/backtrader/beginner/02_momentum.md
"""
策略 2：单因子动量选股策略（Momentum）
类型：单因子选股（量价因子） ｜ 难度：★★☆☆☆
核心思路：动量效应——过去一段时间涨幅靠前的股票，未来一段时间倾向于继续跑赢。
注意：股票池是「当前」沪深300成分股，含幸存者偏差；聚宽版能取历史成分股，本轮换成历史池。
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from btlab.datasource import load_daily, load_index_members       # noqa: E402
from btlab.runner import PanelStrategy, run_strategy, load_universe  # noqa: E402

# ============================ 回测参数（改这里即可） ============================
START = '2015-01-01'
END = None
CASH = 1_000_000
BENCHMARK = '000300'
PLOT = os.path.join('results', 'bt_s02_result.png')

UNIVERSE_SIZE = 40          # 股票池大小（取沪深300成分股的前 N 只，控制拉数时间）
LOOKBACK = 60               # 动量回看期（交易日）
TOPN = 10                   # 持仓只数
REBALANCE = 'monthly'       # 调仓频率：daily / weekly / monthly


class Momentum(PanelStrategy):
    """动量选股：按过去 LOOKBACK 日涨幅排序，买最强的 TOPN 只，每月等权调仓。"""

    params = (
        ('lookback', LOOKBACK),
        ('topn', TOPN),
        ('rebalance', REBALANCE),
    )

    def on_rebalance(self, cur):
        """调仓日：算动量 → 排序 → 取前 topn → 等权下单。"""
        scores = {}
        for d in self.tradables:
            if not self.live(d, cur):          # 停牌 / 未上市 → 跳过
                continue
            closes = self.hist_close(d, self.p.lookback + 1)
            if closes is None or closes[0] <= 0:
                continue
            scores[d._name] = closes[-1] / closes[0] - 1.0     # 区间收益率

        if len(scores) < self.p.topn:          # 有效样本不足，本月不调仓
            return

        target = sorted(scores, key=scores.get, reverse=True)[:self.p.topn]
        self.equal_weight_order(target, cur)


def main():
    print(f'[1/3] 获取沪深300成分股（前 {UNIVERSE_SIZE} 只）...')
    codes = load_index_members('000300')[:UNIVERSE_SIZE]

    print(f'[2/3] 加载 {len(codes)} 只股票日线（前复权）...')
    data = load_universe(codes, start=START, end=END, adjust='qfq', label='股票池')
    # 交易日历：基准指数每个交易日都有行情，用它当"时钟"
    data['__CAL__'] = load_daily(BENCHMARK, start=START, end=END)

    print('[3/3] 开始 backtrader 回测 ...')
    run_strategy(
        Momentum,
        data,
        cash=CASH,
        benchmark=BENCHMARK,
        title='策略2 单因子动量选股（backtrader · 沪深300成分股）',
        plot_path=PLOT,
    )


if __name__ == '__main__':
    main()
