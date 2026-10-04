# -*- coding: utf-8 -*-
# ==========================================================================================
# 【backtrader 本地回测版 · 可离线运行】对应聚宽版：strategies/joinquant/advanced/a03_long_short.py
#
# 回测内核：backtrader（官方开源框架）｜数据：btlab.datasource（免费，无需聚宽账号）
# 运行方式（项目根目录）：python strategies/backtrader/advanced/bt_a03_long_short.py
#
# 与聚宽版的差异 / 重要假设：
#   1) 本回测**不做融券可行性校验**，也**不计融券利息与借券费**，属于理想化模型；
#      真实 A 股融券标的有限、券源紧张、成本约年化 8%~10%，会显著削弱绝对收益。
#   2) 多空市值各占净值的 LONG_EXPOSURE 比例（默认 40%+40%，总敞口 0.8 倍），
#      比聚宽示例的"满仓多空"保守，避免净值被极端行情打到负数。
#   3) 股票池为「当前」沪深300成分股（大盘股多、券商券源多），存在幸存者偏差。
# ==========================================================================================
"""
================================================================================
进阶策略 3：多空对冲策略（Long-Short Equity）· backtrader 本地版
================================================================================
策略类型：绝对收益 / 市场中性
难度等级：★★★★★
核心思路：买入因子排名前 10% 的股票（多头），同时卖出排名后 10% 的股票（空头），
          剥离市场 Beta，纯赚 Alpha。多头和空头市值相等 → Beta 中性。

【学习重点】
  - backtrader 中做空的实现：self.sell() 之后持仓 size 变为负数，
    账户总资产 = 现金 + Σ(持仓数量 × 现价)，空头自然形成"负市值"，
    股价下跌时空头盈利 —— 与真实融券的盈亏方向一致
  - 多空平衡：多头市值 ≈ 空头市值，组合对大盘涨跌不敏感
  - Alpha 与 Beta 的分离："Beta"=跟随市场的收益，"Alpha"=选股带来的超额收益
  - 资金占用：做空会收到现金，所以能买入更多多头（回测里体现为可用现金变多）
================================================================================
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from btlab.datasource import load_daily, load_index_members           # noqa: E402
from btlab.runner import (PanelStrategy, run_strategy, load_universe,  # noqa: E402
                          round_lot)

# ============================ 回测参数 ============================
START = '2015-01-01'
END = None
CASH = 1_000_000
BENCHMARK = '000300'
PLOT = os.path.join('results', 'bt_a03_result.png')

UNIVERSE_SIZE = 40
LOOKBACK = 60               # 动量因子回看期
LONG_NUM = 10               # 多头只数
SHORT_NUM = 10              # 空头只数
LONG_EXPOSURE = 0.40        # 多头市值 / 净值
SHORT_EXPOSURE = 0.40       # 空头市值 / 净值
STOP_EQUITY_RATIO = 0.40    # 净值跌破初始资金的该比例时停止交易（风控保险丝）


class LongShort(PanelStrategy):
    """动量多空：做多动量最强的 LONG_NUM 只，做空最弱的 SHORT_NUM 只。"""

    params = (('lookback', LOOKBACK), ('long_num', LONG_NUM), ('short_num', SHORT_NUM),
              ('long_exposure', LONG_EXPOSURE), ('short_exposure', SHORT_EXPOSURE),
              ('rebalance', 'monthly'),)

    def on_rebalance(self, cur):
        # 0) 风控保险丝：净值被打到很低时清仓并停止交易
        if self.broker.getvalue() < CASH * STOP_EQUITY_RATIO:
            self.close_all(cur)
            print(f'  [{cur}] 净值跌破 {STOP_EQUITY_RATIO:.0%}，清仓停止交易')
            return

        # 1) 计算动量因子
        mom = {}
        for d in self.tradables:
            if not self.live(d, cur):
                continue
            closes = self.hist_close(d, self.p.lookback + 1)
            if closes is None or closes[0] <= 0:
                continue
            mom[d._name] = closes[-1] / closes[0] - 1.0
        if len(mom) < self.p.long_num + self.p.short_num:
            return
        ranked = sorted(mom, key=mom.get, reverse=True)
        longs = ranked[:self.p.long_num]
        shorts = ranked[-self.p.short_num:]
        if set(longs) & set(shorts):        # 样本太少时可能重叠，直接跳过
            return

        equity = self.broker.getvalue()
        per_long = round_lot(equity * self.p.long_exposure / len(longs) / 1.0)
        per_short = round_lot(equity * self.p.short_exposure / len(shorts) / 1.0)

        # 2) 先平掉不在名单里的仓位
        for d in self.tradables:
            if d._name in longs or d._name in shorts:
                continue
            if self.getposition(d).size and self.live(d, cur):
                self.close(d)

        # 3) 多头：目标为正的股数
        for name in longs:
            self._target_size(name, per_long, cur)

        # 4) 空头：目标为负的股数
        for name in shorts:
            self._target_size(name, per_short, cur, short=True)

    def _target_size(self, name, capital, cur, short=False):
        """把某只股票调整到目标股数（空头时目标为负数）。"""
        d = self.getdatabyname(name)
        price = d.close[0]
        if price <= 0:
            return
        want = round_lot(capital / price)
        if short:
            want = -want
        delta = want - self.getposition(d).size
        if delta > 0:
            self.buy(d, size=delta)
        elif delta < 0:
            self.sell(d, size=-delta)


def main():
    print(f'[1/3] 获取沪深300成分股（前 {UNIVERSE_SIZE} 只）...')
    codes = load_index_members('000300')[:UNIVERSE_SIZE]

    print('[2/3] 加载日线 ...')
    data = load_universe(codes, start=START, end=END, adjust='qfq', label='股票池')
    data['__CAL__'] = load_daily(BENCHMARK, start=START, end=END)

    print('[3/3] 开始 backtrader 回测 ...')
    run_strategy(LongShort, data, cash=CASH, benchmark=BENCHMARK,
                 title='进阶3 多空对冲策略（backtrader · 动量多空，Beta 中性）',
                 plot_path=PLOT)


if __name__ == '__main__':
    main()
