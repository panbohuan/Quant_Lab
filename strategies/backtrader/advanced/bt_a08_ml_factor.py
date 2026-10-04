# -*- coding: utf-8 -*-
# ==========================================================================================
# 【backtrader 本地回测版 · 可离线运行】对应聚宽版：strategies/joinquant/advanced/a08_ml_factor.py
#
# 回测内核：backtrader（官方开源框架）｜数据：btlab.datasource（免费，无需聚宽账号）
# 运行方式（项目根目录）：python strategies/backtrader/advanced/bt_a08_ml_factor.py
# 需要额外依赖：scikit-learn
#
# 与聚宽版的差异：
#   1) 用**梯度提升回归树**（GradientBoostingRegressor）直接回归"未来 20 日收益率"，
#      与 s10 的随机森林分类（涨/跌）形成对照：回归给出的是收益幅度预期，
#      分类给出的是方向概率。
#   2) 逐期滚动扩窗训练，样本标签必须等预测窗口结束后才确认 —— 严格避免未来函数。
#   3) 未做时序交叉验证调参（聚宽版提到过），这里固定一组较保守的超参数以避免过拟合。
# ==========================================================================================
"""
================================================================================
进阶策略 8：机器学习因子合成（ML Factor Combination）· backtrader 本地版
================================================================================
策略类型：机器学习进阶 / 因子合成
难度等级：★★★★★
核心思路：用梯度提升树把多个因子**非线性地**合成为一个预期收益预测，
          替代 s07 的手工线性加权。让模型自己学习"因子如何组合才能预测收益"。

【特征（6 个）】
  量价类：20 日动量、60 日动量、20 日波动率、量比
  基本面类：PB（z-score）、对数市值（z-score）
【标签】
  未来 20 个交易日的收益率（连续值，回归任务）

【学习重点】
  - 回归 vs 分类：预测"涨多少"比预测"涨不涨"信息量更大，但也更难
  - 时序滚动训练：每月用"标签已确认"的历史样本重新训练，样本随月份增长
  - 防止过拟合的三板斧：浅树（max_depth=3）、叶子样本下限（min_samples_leaf）、
    特征少而稳定（6 个）——树越深越容易记住噪声
  - 特征重要性（model.feature_importances_）：模型自己告诉我们哪个因子有用
  - 可解释性：线性模型看系数，树模型看特征重要性
================================================================================
"""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sklearn.ensemble import GradientBoostingRegressor                # noqa: E402

from btlab.datasource import load_daily, load_index_members           # noqa: E402
from btlab.runner import (PanelStrategy, run_strategy, load_universe,  # noqa: E402
                          value_panel, asof)

# ============================ 回测参数 ============================
START = '2016-01-01'
END = None
CASH = 1_000_000
BENCHMARK = '000300'
PLOT = os.path.join('results', 'bt_a08_result.png')

UNIVERSE_SIZE = 40
TOPN = 10
HORIZON = 20                # 预测窗口：未来 20 个交易日
MIN_SAMPLES = 400
FEATURE_NAMES = ['mom20', 'mom60', 'vol20', 'vol_ratio', 'pb_z', 'logmv_z']


def zscore(s):
    s = pd.Series(s, dtype=float)
    return (s - s.mean()) / (s.std() + 1e-12)


class MLFactor(PanelStrategy):
    """用梯度提升树把 6 个因子非线性合成为一个预期收益预测。"""

    params = (('topn', TOPN), ('horizon', HORIZON), ('rebalance', 'monthly'),
              ('min_samples', MIN_SAMPLES),)

    def __init__(self):
        super().__init__()
        codes = [d._name for d in self.tradables]
        print('  预加载估值面板（PB / 市值）...')
        self.pb = value_panel(codes, 'pb')
        self.mv = value_panel(codes, 'total_mv')
        self.X, self.y = [], []
        self.pending = []
        self.model = None
        self._reported = False

    def _features(self, d, cur):
        c20 = self.hist_close(d, 21)
        c60 = self.hist_close(d, 61)
        if c20 is None or c60 is None or min(c60) <= 0:
            return None
        vols = d.volume.get(size=61)
        if len(vols) < 61:
            return None
        rets = pd.Series(c20, dtype=float).pct_change().dropna()
        row = None
        pb, mv = asof(self.pb, cur), asof(self.mv, cur)
        name = d._name
        if pb is not None and mv is not None and name in pb.index and name in mv.index:
            row = (pb, mv)
        return {
            'mom20': c20[-1] / c20[0] - 1.0,
            'mom60': c60[-1] / c60[0] - 1.0,
            'vol20': float(rets.std()),
            'vol_ratio': float(np.mean(vols[-5:]) / (np.mean(vols) + 1e-9)),
            'pb': float(row[0][name]) if row else np.nan,
            'mv': float(row[1][name]) if row else np.nan,
        }

    def _label_pending(self):
        still = []
        for code, feats, p0, bars0 in self.pending:
            d = self.getdatabyname(code)
            if len(d) - bars0 >= self.p.horizon:
                p1 = d.close[0]
                if p0 > 0 and p1 > 0 and np.isfinite(feats).all():
                    self.X.append(list(feats))
                    self.y.append(p1 / p0 - 1.0)          # 回归标签：真实收益率
            else:
                still.append((code, feats, p0, bars0))
        self.pending = still

    def on_rebalance(self, cur):
        # 1) 确认上一批样本的标签
        self._label_pending()

        # 2) 本期原始特征
        raw = {}
        price = {}
        for d in self.tradables:
            if not self.live(d, cur):
                continue
            f = self._features(d, cur)
            if f is None:
                continue
            raw[d._name] = f
            price[d._name] = d.close[0]
        if len(raw) < self.p.topn:
            return
        codes = list(raw)

        # 3) 基本面特征做截面 z-score（量价特征本身已可比）
        pb_s = pd.Series({c: raw[c]['pb'] for c in codes}, dtype=float)
        mv_s = pd.Series({c: raw[c]['mv'] for c in codes}, dtype=float)
        mv_s = np.log(mv_s.where(mv_s > 0))
        pb_z, mv_z = zscore(pb_s), zscore(mv_s)
        vectors = []
        for c in codes:
            f = raw[c]
            vectors.append([f['mom20'], f['mom60'], f['vol20'], f['vol_ratio'],
                            float(pb_z.get(c, np.nan)), float(mv_z.get(c, np.nan))])

        # 4) 训练 + 预测
        if len(self.X) >= self.p.min_samples:
            self.model = GradientBoostingRegressor(
                n_estimators=150, max_depth=3, learning_rate=0.05,
                min_samples_leaf=20, subsample=0.8, random_state=42)
            self.model.fit(self.X, self.y)
            pred = self.model.predict(vectors)
            order = [codes[i] for i in np.argsort(-pred)]
            if not self._reported:
                imp = ', '.join(f'{n}={v:.2f}' for n, v in
                                zip(FEATURE_NAMES, self.model.feature_importances_))
                print(f'  模型特征重要性：{imp}')
                self._reported = True
            print(f'  [{cur}] ML 因子合成（样本 {len(self.X)} 条）预期收益最高 '
                  f'{max(pred) * 100:.2f}%')
        else:
            order = sorted(codes, key=lambda c: raw[c]['mom20'], reverse=True)
            print(f'  [{cur}] 样本不足（{len(self.X)}/{self.p.min_samples}），暂用 20 日动量兜底')
        names = order[:self.p.topn]

        # 5) 登记本期样本，等预测窗口结束后打标签
        for i, c in enumerate(codes):
            self.pending.append((c, np.array(vectors[i]), price[c],
                                 len(self.getdatabyname(c))))

        self.equal_weight_order(names, cur)


def main():
    print(f'[1/3] 获取沪深300成分股（前 {UNIVERSE_SIZE} 只）...')
    codes = load_index_members('000300')[:UNIVERSE_SIZE]

    print('[2/3] 加载日线 ...')
    data = load_universe(codes, start=START, end=END, adjust='qfq', label='股票池')
    data['__CAL__'] = load_daily(BENCHMARK, start=START, end=END)

    print('[3/3] 开始 backtrader 回测 ...')
    run_strategy(MLFactor, data, cash=CASH, benchmark=BENCHMARK,
                 title='进阶8 机器学习因子合成（backtrader · 梯度提升树）',
                 plot_path=PLOT)


if __name__ == '__main__':
    main()
