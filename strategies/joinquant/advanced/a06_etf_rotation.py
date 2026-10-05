# -*- coding: utf-8 -*-
# 【聚宽原生策略 · 云端运行】粘贴到 joinquant.com 策略编辑器即可，无需本地依赖
# 本地可运行版：strategies/backtrader/advanced/bt_a06_etf_rotation.py
# 详细讲解：docs/joinquant/advanced/06_etf_rotation.md
"""
策略 6：ETF轮动策略（ETF Rotation）
类型：资产配置 / ETF轮动 ｜ 难度：★★★★☆
核心思路：在宽基、行业、跨境、商品 ETF 之间，按动量轮动，买入近期表现最强的
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
        type='fund'
    )
    set_slippage(FixedSlippage(0.02))
    log.set_level('order', 'error')

    # 候选 ETF 池（覆盖宽基、行业、跨境、商品）
    g.etf_pool = [
        '510300.XSHG',   # 沪深300ETF
        '510500.XSHG',   # 中证500ETF
        '510050.XSHG',   # 上证50ETF
        '159915.XSHE',   # 创业板ETF
        '512880.XSHG',   # 证券ETF
        '512800.XSHG',   # 银行ETF
        '512690.XSHG',   # 酒ETF
        '513100.XSHG',   # 纳指ETF（跨境）
        '518880.XSHG',   # 黄金ETF（商品）
        '159981.XSHE',   # 能源化工ETF
    ]

    g.top_n = 3                 # 持有 ETF 数量
    g.lookback = 60             # 动量回看期

    run_monthly(rebalance, 1, time='09:30')

def rebalance(context):
    """每月调仓：按动量选出最强的 top_n 只 ETF。"""

    # 1. 计算每只 ETF 的动量
    momentum = {}
    for etf in g.etf_pool:
        df = attribute_history(etf, g.lookback, '1d', 'close', df=True)
        if len(df) >= g.lookback:
            momentum[etf] = df['close'].iloc[-1] / df['close'].iloc[0] - 1

    if not momentum:
        return

    # 2. 选出动量最强的 top_n 只
    target = sorted(momentum, key=momentum.get, reverse=True)[:g.top_n]
    if not target:
        return

    # 3. 卖出不在目标列表的持仓
    for s in list(context.portfolio.positions):
        if s not in target:
            order_target(s, 0)

    # 4. 等权买入
    per_value = context.portfolio.total_value / len(target)
    for s in target:
        order_target_value(s, per_value)

    log.info('当前持有: %s' % ','.join(target))
