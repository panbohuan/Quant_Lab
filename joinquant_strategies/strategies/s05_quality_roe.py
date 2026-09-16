# -*- coding: utf-8 -*-
"""
================================================================================
策略 5：单因子质量选股策略（ROE 质量因子）
================================================================================
策略类型：单因子选股（基本面·质量因子）
难度等级：★★★☆☆
核心思路：质量投资——买入"赚钱能力强"的好公司。净资产收益率(ROE)越高，
          代表公司利用股东资本创造利润的效率越高。
          每个调仓日按 ROE 从大到小排序，买入最高的 K 只，等权持有。

本策略新增的关键函数（聚宽）：
  - indicator.roe          财务指标表·净资产收益率字段
  - indicator.roa          总资产收益率字段
  - indicator.gross_profit_margin  毛利率字段
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
    g.factor = 'roe'          # 可改为 'roa' 或 'gross_profit_margin'

    run_monthly(rebalance, 1, time='09:30')


def rebalance(context):
    # 1. 全市场股票池
    pool = get_all_securities(['stock'], date=context.current_dt.date()).index.tolist()

    # 2. 过滤 ST、停牌
    current_data = get_current_data()
    pool = [s for s in pool
            if not current_data[s].is_st
            and not current_data[s].paused]

    # 3. 查询质量因子
    q = query(
        valuation.code,
        indicator.roe,                  # 净资产收益率
        indicator.roa,                  # 总资产收益率
        indicator.gross_profit_margin   # 毛利率
    ).filter(
        valuation.code.in_(pool)
    ).order_by(
        indicator.roe.desc()            # ROE 降序（越高越靠前）
    ).limit(g.stock_num * 3)

    df = get_fundamentals(q, date=context.current_dt.date())

    # 4. 清洗：剔除缺失值（ROE 无正负过滤，但可剔除极端值，见文档）
    df = df.dropna(subset=[g.factor])

    # 5. 取 ROE 最高的前 stock_num 只
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
