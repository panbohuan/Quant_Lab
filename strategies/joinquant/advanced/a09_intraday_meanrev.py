# -*- coding: utf-8 -*-
# 【聚宽原生策略 · 云端运行】粘贴到 joinquant.com 策略编辑器即可，无需本地依赖
# 本地可运行版：strategies/backtrader/advanced/bt_a09_intraday_meanrev.py
# 详细讲解：docs/joinquant/advanced/09_intraday_meanrev.md
"""
策略 9：高频均值回归策略（Intraday Mean Reversion）
类型：日内交易 / 均值回归 ｜ 难度：★★★★★
核心思路：在分钟级数据上，捕捉短期超跌反弹。比如开盘 30 分钟跌幅超过 2% 的
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
    set_slippage(FixedSlippage(0.02))
    log.set_level('order', 'error')

    g.drop_threshold = -0.02     # 超跌阈值：开盘以来跌幅超过 -2%
    g.max_hold = 5               # 最多持有股票数
    g.min_list_days = 60

    # 记录已买入的股票（当日不再重复买入）
    g.bought_today = set()

    # 每日开盘后运行一次（本地引擎为日级近似；聚宽云端可用分钟级 every_bar）
    run_daily(minute_trade, time='09:35')

def minute_trade(context):
    """每日检查：发现超跌股则买入，博取反弹。

    说明：本地引擎为日级近似——用"当日开盘价相对前收盘价"的跌幅作为超跌信号，
    模拟日内超跌反弹。若需真正的分钟级回测，请在聚宽云端用 frequency='minute'
    的数据 + run_daily(time='every_bar') 实现。
    """

    # 1. 股票池
    pool = get_index_stocks('000300.XSHG')

    # 2. 计算每只股票"开盘相对昨收"的跌幅
    current_data = get_current_data()
    for s in pool:
        # 已买入或已持有则跳过
        if s in g.bought_today or s in context.portfolio.positions:
            continue

        d = current_data[s]
        if d.paused or d.day_open <= 0:
            continue

        # 前收盘价（用最近两根K线的倒数第二根近似）
        open_price = d.day_open
        last_price = d.last_price
        if open_price <= 0:
            continue

        # 开盘以来跌幅（日级近似：用当日涨跌幅模拟）
        change = last_price / open_price - 1.0

        # 超跌（跌幅超过阈值）且未跌停 → 买入博反弹
        if change <= g.drop_threshold and last_price < d.high_limit:
            # 买入
            per_value = context.portfolio.total_value / g.max_hold
            order_target_value(s, per_value)
            g.bought_today.add(s)

            # 达到持仓上限则停止
            if len(g.bought_today) >= g.max_hold:
                return

    # 收盘前清空当日买入记录（日级近似：每日调仓后重置）
    g.bought_today = set()
