# -*- coding: utf-8 -*-
# 【聚宽原生策略 · 云端运行】粘贴到 joinquant.com 策略编辑器即可，无需本地依赖
# 本地可运行版：strategies/backtrader/advanced/bt_a03_long_short.py
# 详细讲解：docs/joinquant/advanced/03_long_short.md
"""
策略 3：多空对冲策略（Long-Short Equity）
类型：绝对收益 / 市场中性 ｜ 难度：★★★★★
核心思路：买入因子排名前 10% 的股票（多头），同时卖出排名后 10% 的股票（空头），
"""

# ============================ 回测设置说明 ============================
# 回测区间 / 初始资金：在聚宽策略编辑器右上角的「回测面板」中设置（无需改代码）。
# 基准指数：由 initialize() 中的 set_benchmark(BENCHMARK) 指定。
# 以下参数可在代码中直接修改，改完点击「编译运行」即生效。
BENCHMARK    = '000300.XSHG'  # 基准：沪深300指数

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
