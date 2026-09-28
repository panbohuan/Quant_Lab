# -*- coding: utf-8 -*-
"""
================================================================================
进阶策略 3：多空对冲策略（Long-Short Equity）
================================================================================
策略类型：绝对收益 / 市场中性
难度等级：★★★★★
核心思路：买入因子排名前 10% 的股票（多头），同时卖出排名后 10% 的股票（空头），
          剥离市场 Beta，纯赚 Alpha。多头和空头的市值相等，实现 Beta 中性。

学习重点：
  - 融券/做空机制（聚宽中通过负的 order_target_value 实现）
  - 多空平衡（多头市值 ≈ 空头市值，对冲市场风险）
  - Beta 中性（组合对市场涨跌不敏感）

进阶价值：理解 Alpha 和 Beta 的分离，是走向专业量化的关键一步。
          "Alpha" = 超越市场的超额收益（选股能力）
          "Beta"  = 跟随市场波动的系统性收益（承担市场风险换来的）

================================================================================
算法结构
--------------------------------------------------------------------------------
每月第1个交易日调仓：
  1. 股票池：沪深300成分股（可融券标的多为大盘股）
  2. 计算因子（本例用动量因子）
  3. 多头 = 因子排名前 long_num 只，空头 = 排名后 short_num 只
  4. 多头买入正市值，空头卖出负市值（order_target_value 传负数）
  5. 保持多头总市值 ≈ 空头总市值（Beta 中性）
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
    # 融券成本通常更高，这里简化处理
    set_slippage(FixedSlippage(0.02))
    log.set_level('order', 'error')

    # 策略参数
    g.long_num = 10             # 多头持仓数量
    g.short_num = 10            # 空头持仓数量
    g.lookback = 60             # 动量回看期
    g.min_list_days = 60        # 次新股过滤
    g.leverage = 1.0            # 总杠杆（多头 + 空头各占 1.0，即 1 倍多头 + 1 倍空头）

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


def rebalance(context):
    """每月调仓：做多强势股，做空弱势股，市值对冲。"""

    # 1. 股票池（沪深300成分股，多为可融券标的）
    pool = get_index_stocks('000300.XSHG')
    pool = filter_stocks(context, pool)
    if len(pool) < g.long_num + g.short_num:
        return

    # 2. 计算动量因子
    momentum = {}
    for s in pool:
        df = attribute_history(s, g.lookback, '1d', 'close', df=True)
        if len(df) >= g.lookback:
            momentum[s] = df['close'].iloc[-1] / df['close'].iloc[0] - 1

    if len(momentum) < g.long_num + g.short_num:
        return

    # 3. 排序：动量降序
    ranked = sorted(momentum, key=momentum.get, reverse=True)

    # 4. 多头 = 前 long_num 只，空头 = 后 short_num 只
    long_stocks = ranked[:g.long_num]
    short_stocks = ranked[-g.short_num:]

    # 5. 清空所有旧持仓（包括多空）
    for s in list(context.portfolio.positions):
        order_target(s, 0)

    # 6. 多头买入：每只分配 total_value * leverage / long_num
    long_per = context.portfolio.total_value * g.leverage / g.long_num
    for s in long_stocks:
        order_target_value(s, long_per)

    # 7. 空头卖出：order_target_value 传负数 → 卖出空头（融券）
    short_per = context.portfolio.total_value * g.leverage / g.short_num
    for s in short_stocks:
        order_target_value(s, -short_per)

    log.info('多头 %d 只，空头 %d 只' % (len(long_stocks), len(short_stocks)))
