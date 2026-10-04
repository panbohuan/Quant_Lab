# -*- coding: utf-8 -*-
# ==========================================================================================
# 【backtrader 本地回测版 · 可离线运行】对应聚宽版：strategies/joinquant/advanced/a06_etf_rotation.py
#
# 回测内核：backtrader（官方开源框架）｜数据：btlab.datasource（免费，无需聚宽账号）
# 运行方式（项目根目录）：python strategies/backtrader/advanced/bt_a06_etf_rotation.py
#
# 与聚宽版的差异：
#   1) 聚宽用 get_all_securities(['etf']) 取全市场 ETF；本地版用固定的 7 只代表性 ETF
#      （覆盖宽基、成长、商品、跨境、债券五类资产），保证长历史与可复现性。
#   2) 本版额外加了"风险开关"：若最强 ETF 的动量为负，则全部切换到国债 ETF（避险）。
#   3) ETF 采用「加回分红」口径（见 btlab/datasource.py 说明）。
# ==========================================================================================
"""
================================================================================
进阶策略 6：ETF 轮动策略（ETF Rotation）· backtrader 本地版
================================================================================
策略类型：资产配置 / ETF 轮动
难度等级：★★★★☆
核心思路：在宽基、行业、跨境、商品、债券 ETF 之间按动量轮动，买入近期表现最强的
          几只 ETF，实现大类资产配置；再用一个"风险开关"在熊市里躲到债券里。

【候选资产池（7 只，覆盖 5 类资产）】
  510050 上证50ETF    宽基（大盘价值）
  510300 沪深300ETF   宽基（核心）
  510500 中证500ETF   宽基（中盘）
  159915 创业板ETF    宽基（成长）
  518880 黄金ETF      商品
  513100 纳指ETF      跨境（美股）
  511010 国债ETF      债券（避险资产）

【学习重点】
  - 大类资产配置：不同资产相关性低，轮动能分散风险、捕捉结构性机会
  - 动量轮动 + 风险开关：一个极简但有效的"趋势跟踪资产配置"模板
  - 为什么加债券：股票动量全为负时，持有债券能显著降低回撤
  - 资产数量少 → 权重集中度高（top3 各 1/3），这是 ETF 轮动的固有特征
================================================================================
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from btlab.datasource import load_daily                               # noqa: E402
from btlab.runner import PanelStrategy, run_strategy                  # noqa: E402

# ============================ 回测参数 ============================
START = '2014-01-01'
END = None
CASH = 1_000_000
BENCHMARK = '000300'
PLOT = os.path.join('results', 'bt_a06_result.png')

POOL = {
    '510050': '上证50ETF',
    '510300': '沪深300ETF',
    '510500': '中证500ETF',
    '159915': '创业板ETF',
    '518880': '黄金ETF',
    '513100': '纳指ETF',
}
DEFENSIVE = '511010'        # 避险资产：国债ETF
DEFENSIVE_NAME = '国债ETF'

TOPN = 3                    # 持有动量最强的 3 只
LOOKBACK = 60               # 动量回看期


class ETFRotation(PanelStrategy):
    """ETF 动量轮动 + 风险开关（动量全负时躲进国债）。"""

    params = (('topn', TOPN), ('lookback', LOOKBACK), ('rebalance', 'monthly'),
              ('defensive', None),)

    def on_rebalance(self, cur):
        scores = {}
        for d in self.tradables:
            if d._name == self.p.defensive:       # 避险资产不参与动量排序
                continue
            if not self.live(d, cur):
                continue
            closes = self.hist_close(d, self.p.lookback + 1)
            if closes is None or closes[0] <= 0:
                continue
            scores[d._name] = closes[-1] / closes[0] - 1.0
        if not scores:
            return

        target = sorted(scores, key=scores.get, reverse=True)[:self.p.topn]
        best = max(scores.values())

        # 风险开关：最强资产动量仍为负 → 全部转入避险资产
        if best <= 0 and self.p.defensive:
            d = self.getdatabyname(self.p.defensive)
            if self.live(d, cur):
                print(f'  [{cur}] 风险开关触发（最强动量 {best * 100:.2f}%）→ 转入 {DEFENSIVE_NAME}')
                self.equal_weight_order([self.p.defensive], cur)
                return
        self.equal_weight_order(target, cur)


def main():
    print(f'[1/2] 加载 {len(POOL) + 1} 只 ETF 日线 ...')
    data = {}
    for code, name in POOL.items():
        data[f'{name}({code})'] = load_daily(code, start=START, end=END)
    data[f'{DEFENSIVE_NAME}({DEFENSIVE})'] = load_daily(DEFENSIVE, start=START, end=END)
    data['__CAL__'] = load_daily(BENCHMARK, start=START, end=END)
    for name, df in list(data.items())[:-1]:
        print(f'      {name}: {df.index[0].date()} ~ {df.index[-1].date()}  {len(df)} 行')

    print('[2/2] 开始 backtrader 回测 ...')
    run_strategy(ETFRotation, data, cash=CASH, benchmark=BENCHMARK,
                 title='进阶6 ETF轮动策略（backtrader · 6 类资产 + 国债避险开关）',
                 plot_path=PLOT, defensive=f'{DEFENSIVE_NAME}({DEFENSIVE})')


if __name__ == '__main__':
    main()
