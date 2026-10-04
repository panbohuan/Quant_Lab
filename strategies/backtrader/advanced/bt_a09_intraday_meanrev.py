# -*- coding: utf-8 -*-
# ==========================================================================================
# 【backtrader 本地回测版 · 可离线运行】对应聚宽版：strategies/joinquant/advanced/a09_intraday_meanrev.py
#
# 回测内核：backtrader（官方开源框架）｜数据：btlab.datasource（免费，无需聚宽账号）
# 运行方式（项目根目录）：python strategies/backtrader/advanced/bt_a09_intraday_meanrev.py
#
# 与聚宽版的差异（重要）：
#   聚宽版用**分钟级**数据做日内超跌反弹。本地免费分钟数据源不稳定（东财接口常被限流/不可达），
#   因此本版本**降频到日线**：改为"过去 5 日累计跌幅过大 → 反弹"的短期反转策略。
#   原理与日内超跌反弹一致（都是均值回归/过度反应修复），只是时间尺度从分钟放大到日。
#   如果你想做真正的分钟级回测，可自行接入 tushare / 米筐等数据源，策略骨架可复用。
# ==========================================================================================
"""
================================================================================
进阶策略 9：短期均值回归 / 超跌反弹策略 · backtrader 本地版（日线降频版）
================================================================================
策略类型：均值回归 / 反转
难度等级：★★★★★
核心思路：捕捉"过度反应"后的修复。股票短期大幅下跌后，往往出现反弹。
          每周扫描全池，选出**过去 5 个交易日累计跌幅超过阈值**的股票，取跌幅最大的
          TOPN 只等权买入，持有到下个调仓日（约 5 个交易日）后自然退出。

【学习重点】
  - 均值回归 vs 动量：两者方向相反，但在不同时间尺度上可以同时成立
    （短期反转、中期动量是 A 股常见的现象组合）
  - 高频/短周期策略的核心不是"预测准"，而是**成本控制**：
    交易越频繁，手续费+滑点越是收益杀手。可以在本策略上调参数观察：
    换成日度调仓后，收益往往被交易成本吃掉一大截
  - 换手率与收益的权衡：本策略报告里的"累计换手率"会明显高于月度调仓的策略
  - 空仓纪律：没有满足"超跌"条件的股票时就该空仓，而不是硬凑 10 只
================================================================================
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
