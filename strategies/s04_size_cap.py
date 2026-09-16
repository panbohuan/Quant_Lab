# -*- coding: utf-8 -*-
"""
================================================================================
策略 4：单因子小市值选股策略（Size / 市值因子）
================================================================================
策略类型：单因子选股（基本面·规模因子）
难度等级：★★☆☆☆
核心思路：小市值效应——长期看，小市值股票的平均收益高于大市值股票（A股尤甚）。
          用总市值(或流通市值)作为因子，市值越小排名越靠前。
          每个调仓日按市值升序排序，买入市值最小的 K 只，等权持有。

本策略新增的关键函数（聚宽）：
  - valuation.market_cap            总市值字段
  - valuation.circulating_market_cap 流通市值字段
  - get_all_securities(['stock'])   获取全市场股票列表
================================================================================
"""
from jqdata import *


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

    g.stock_num = 30
    g.cap_field = 'market_cap'   # 可改为 'circulating_market_cap' 用流通市值

    run_monthly(rebalance, 1, time='09:30')


def rebalance(context):
    # 1. 全市场股票池
    pool = get_all_securities(['stock'], date=context.current_dt.date()).index.tolist()

    # 2. 过滤 ST、停牌
    current_data = get_current_data()
    pool = [s for s in pool
            if not current_data[s].is_st
            and not current_data[s].paused]

    # 3. 查询市值因子
    q = query(
        valuation.code,
        valuation.market_cap,               # 总市值（单位：亿元）
        valuation.circulating_market_cap    # 流通市值
    ).filter(
        valuation.code.in_(pool)
    ).order_by(
        valuation.market_cap.asc()          # 市值升序（越小越靠前）
    ).limit(g.stock_num * 3)

    df = get_fundamentals(q, date=context.current_dt.date())

    # 4. 清洗：剔除缺失与异常市值
    df = df.dropna(subset=[g.cap_field])
    df = df[df[g.cap_field] > 0]

    # 5. 取市值最小的前 stock_num 只
    target = df.index.tolist()[:g.stock_num]
    if not target:
        return

    # 6. 卖出不在目标列表中的持仓
    for s in list(context.portfolio.positions):
        if s not in target:
            order_target(s, 0)

    # 7. 等权买入
    per_value = context.portfolio.total_value / len(target)
    for s in target:
        order_target_value(s, per_value)
