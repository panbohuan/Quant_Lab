# -*- coding: utf-8 -*-
"""
================================================================================
进阶策略 7：因子择时策略（Factor Timing）
================================================================================
策略类型：因子进阶 / 动态多因子
难度等级：★★★★★
核心思路：根据市场环境动态调整因子权重。比如市场情绪高涨时超配动量因子，
          市场低迷时超配质量因子（低估值、高ROE）。让多因子模型的权重
          "随行就市"。

学习重点：
  - 因子收益归因（理解每个因子在不同环境下的表现）
  - 宏观/市场情绪数据（市场波动率、估值分位等）
  - 动态权重（从静态加权到条件加权）

进阶价值：从"静态多因子"到"动态多因子"，理解因子也有周期。
          没有永远有效的因子，只有适应环境的因子组合。

================================================================================
算法结构
--------------------------------------------------------------------------------
每月第1个交易日调仓：
  1. 判断当前市场状态（用市场波动率/估值分位作为"情绪温度计"）
     - 高波动（risk-on）：超配动量因子
     - 低波动（risk-off）：超配质量因子（估值/ROE）
  2. 计算各股票的多个因子值
  3. 按"动态权重"加权合成综合分
  4. 按综合分排序取前 N 只
================================================================================
"""
import numpy as np
import pandas as pd


def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_order_cost(
        OrderCost(open_tax=0, close_tax=0.001,
                  open_commission=0.0003, close_commission=0.0003,
                  close_today_commission=0, min_commission=5),
        type='stock'
    )
    set_slippage(FixedSlippage(0.02))
    log.set_level('order', 'error')

    g.stock_num = 20            # 持有股票数量
    g.lookback = 60             # 动量回看期
    g.min_list_days = 60        # 次新股过滤

    run_monthly(rebalance, 1, time='09:30')


def filter_stocks(context, stock_list):
    """过滤 ST/退市/停牌/次新/涨跌停。"""
    current_data = get_current_data()
    yesterday = context.previous_date
    result = []
    for s in stock_list:
        d = current_data[s]
        if d.is_st or '退' in d.name:
            continue
        if d.paused:
            continue
        if d.day_open <= 0:
            continue
        info = get_security_info(s)
        if info is None or (yesterday - info.start_date).days < g.min_list_days:
            continue
        if d.high_limit <= d.last_price or d.low_limit >= d.last_price:
            continue
        result.append(s)
    return result


def detect_market_regime(context):
    """
    判断当前市场状态（简化版）。

    用市场（沪深300）的波动率作为"情绪温度计"：
      - 高波动 → risk-on（市场活跃，趋势/动量因子更有效）
      - 低波动 → risk-off（市场谨慎，质量/价值因子更抗跌）

    返回：dict，key=因子名，value=该环境下的权重
    """
    # 计算沪深300近 lookback 日年化波动率
    df = attribute_history('000300.XSHG', g.lookback + 1, '1d', 'close', df=True)
    if len(df) < g.lookback + 1:
        # 数据不足，用默认权重
        return {'momentum': 0.5, 'value': 0.25, 'quality': 0.25}

    closes = df['close'].values
    rets = closes[1:] / closes[:-1] - 1.0
    vol = np.std(rets) * np.sqrt(252)

    # 根据波动率设定权重（波动率阈值可调）
    if vol > 0.30:
        # 高波动：超配动量（趋势跟随），低估质量
        weights = {'momentum': 0.6, 'value': 0.15, 'quality': 0.25}
        regime = 'risk-on'
    elif vol < 0.15:
        # 低波动：超配质量（防御），低估动量
        weights = {'momentum': 0.2, 'value': 0.3, 'quality': 0.5}
        regime = 'risk-off'
    else:
        # 中性：均衡配置
        weights = {'momentum': 0.4, 'value': 0.3, 'quality': 0.3}
        regime = 'neutral'

    log.info('市场波动率: %.2f%%, 状态: %s, 权重: %s' % (vol * 100, regime, weights))
    return weights


def rebalance(context):
    """每月调仓：按市场状态动态调整因子权重，合成综合分选股。"""

    # 1. 股票池
    pool = get_index_stocks('000300.XSHG')
    pool = filter_stocks(context, pool)
    if len(pool) == 0:
        return

    # 2. 判断市场状态，得到动态权重
    weights = detect_market_regime(context)

    # 3. 计算各因子的原始值
    #    动量因子（越高越好）
    momentum = {}
    for s in pool:
        df = attribute_history(s, g.lookback, '1d', 'close', df=True)
        if len(df) >= g.lookback:
            momentum[s] = df['close'].iloc[-1] / df['close'].iloc[0] - 1

    #    价值因子（PE 越低越好）和质量因子（ROE 越高越好）
    q = query(
        valuation.code,
        valuation.pe_ratio,
        indicator.roe
    ).filter(
        valuation.code.in_(pool)
    )
    df = get_fundamentals(q, date=context.current_dt.date())
    df = df.set_index('code')

    # 4. 合成综合分（这里用简单的排名合成，避免量纲问题）
    #    先对所有有效股票做 z-score 或排名，再按权重加总
    #    为保持简单，用"排名百分位"（0~1，越大越好）合成
    valid_codes = set(momentum.keys()) & set(df.index.tolist())

    # 计算各因子在有效股票中的排名百分位
    def rank_pct(series, ascending=True):
        """返回序列的排名百分位（0~1，1=最好）。ascending=True 表示值越大越好。"""
        s = series.rank(pct=True, ascending=ascending)
        return s

    mom_pct = rank_pct(pd.Series({c: momentum[c] for c in valid_codes}), ascending=True)
    pe_pct = rank_pct(df.loc[list(valid_codes), 'pe_ratio'], ascending=False)  # PE越小越好
    roe_pct = rank_pct(df.loc[list(valid_codes), 'roe'], ascending=True)       # ROE越大越好

    # 5. 加权合成
    score = (weights['momentum'] * mom_pct +
             weights['value'] * pe_pct +
             weights['quality'] * roe_pct)

    # 6. 按综合分降序取前 stock_num 只
    target = score.sort_values(ascending=False).index.tolist()[:g.stock_num]
    if not target:
        return

    # 7. 卖出不在目标列表的持仓
    for s in list(context.portfolio.positions):
        if s not in target:
            order_target(s, 0)

    # 8. 等权买入
    per_value = context.portfolio.total_value / len(target)
    for s in target:
        order_target_value(s, per_value)
