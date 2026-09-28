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
  - valuation.market_cap            总市值字段（单位：亿元）
  - valuation.circulating_market_cap 流通市值字段（单位：亿元）
  - get_all_securities(['stock'])   获取全市场股票列表
  - df.set_index('code')            【关键】把查询结果索引设为股票代码
================================================================================
"""
from jqdata import *
from datetime import timedelta


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
    g.cap_field = 'market_cap'      # 可改为 'circulating_market_cap' 用流通市值
    g.min_list_days = 60

    run_monthly(rebalance, 1, time='09:30')


def filter_stocks(context, stock_list):
    """统一的股票池过滤函数（剔除 ST/退市/停牌/次新/涨跌停）。"""
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


def rebalance(context):
    # 1. 全市场股票池
    pool = get_all_securities(['stock'], date=context.current_dt.date()).index.tolist()

    # 2. 过滤 ST、退市、停牌、次新、涨跌停
    pool = filter_stocks(context, pool)
    if len(pool) == 0:
        return

    # 3. 查询市值因子
    q = query(
        valuation.code,
        valuation.market_cap,               # 总市值（单位：亿元）
        valuation.circulating_market_cap    # 流通市值
    ).filter(
        valuation.code.in_(pool)
    ).order_by(
        valuation.market_cap.asc()          # 市值升序（越小越靠前）
    )

    df = get_fundamentals(q, date=context.current_dt.date())
    df = df.set_index('code')               # 【关键】索引设为股票代码

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
