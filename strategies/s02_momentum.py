# -*- coding: utf-8 -*-
"""
================================================================================
策略 2：单因子动量选股策略（Momentum）
================================================================================
策略类型：单因子选股（量价因子）
难度等级：★★☆☆☆
核心思路：动量效应——过去一段时间涨幅靠前的股票，未来一段时间倾向于继续跑赢。
          每个调仓日计算股票池内各股过去 N 日收益率，买入涨幅最大的 K 只，等权持有。

本策略新增的关键函数（聚宽）：
  - get_index_stocks(...)        获取指数成分股列表（股票池）
  - get_current_data()           获取当日实时数据，用于过滤 ST / 停牌
  - run_monthly(func, monthday)  每月第 monthday 个交易日运行
  - context.portfolio.positions  当前持仓字典，用于遍历卖出
  - order_target(security, 0)    清仓某只股票
================================================================================
"""


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

    # 策略参数
    g.stock_num = 20        # 持有股票数量
    g.lookback = 60         # 动量回看期：过去60个交易日（约3个月）的涨幅

    # 每月第一个交易日 09:30 调仓
    run_monthly(rebalance, 1, time='09:30')


def rebalance(context):
    """每月调仓：选出动量最强的 stock_num 只股票等权持有。"""

    # 1. 股票池：沪深300成分股（换成 get_all_securities 可用全市场，见文档）
    pool = get_index_stocks('000300.XSHG')

    # 2. 过滤：剔除 ST、停牌、当日未开盘的股票
    current_data = get_current_data()
    pool = [s for s in pool
            if not current_data[s].is_st        # 不是 ST
            and not current_data[s].paused      # 不停牌
            and current_data[s].day_open > 0]   # 当日正常开盘

    # 3. 计算每只股票的动量因子：过去 lookback 日收益率
    momentum = {}
    for s in pool:
        df = attribute_history(s, g.lookback, '1d', 'close', df=True)
        # 历史K线不足（如次新股）则跳过
        if len(df) >= g.lookback:
            momentum[s] = df['close'].iloc[-1] / df['close'].iloc[0] - 1

    # 4. 按动量降序排序，取前 stock_num 只
    target = sorted(momentum, key=momentum.get, reverse=True)[:g.stock_num]
    if not target:
        return

    # 5. 卖出不在目标列表中的持仓
    for s in list(context.portfolio.positions):
        if s not in target:
            order_target(s, 0)          # 目标股数=0 → 清仓

    # 6. 等权买入：每只股票分配相同金额
    per_value = context.portfolio.total_value / len(target)
    for s in target:
        order_target_value(s, per_value)
