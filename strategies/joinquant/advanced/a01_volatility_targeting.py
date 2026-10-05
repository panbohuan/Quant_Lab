# -*- coding: utf-8 -*-
# 【聚宽原生策略 · 云端运行】粘贴到 joinquant.com 策略编辑器即可，无需本地依赖
# 本地可运行版：strategies/backtrader/advanced/bt_a01_volatility_targeting.py
# 详细讲解：docs/joinquant/advanced/01_volatility_targeting.md
"""
策略 1：波动率目标策略（Volatility Targeting）
类型：风险控制 / 仓位管理 ｜ 难度：★★★★☆
核心思路：根据市场波动率动态调整仓位，让组合波动率维持在目标水平。
"""
import numpy as np

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

    # 策略参数
    g.security = '000300.XSHG'   # 标的：沪深300指数（也可换成 ETF 如 '510300.XSHG'）
    g.lookback = 60              # 波动率回看窗口：过去60个交易日
    g.target_vol = 0.15          # 目标年化波动率（15%，即中等风险）
    g.max_weight = 1.0           # 仓位上限（100%，不放大杠杆；如需杠杆可设 >1）
    g.min_weight = 0.0           # 仓位下限（最低空仓）

    # 每周第一个交易日 09:30 检查并调仓
    run_weekly(rebalance, 1, time='09:30')

def calc_annual_vol(context, security, lookback):
    """
    计算标的的年化波动率。

    参数：
        context  : 聚宽上下文
        security : 标的代码
        lookback : 回看窗口（交易日数）

    返回：
        年化波动率（float），历史数据不足时返回 None
    """
    # 取过去 lookback+1 个交易日的收盘价（多取1根以保证能算出 lookback 个收益率）
    df = attribute_history(security, lookback + 1, '1d', 'close', df=True)
    if len(df) < lookback + 1:
        return None

    closes = df['close'].values
    # 计算日收益率序列：r_t = p_t / p_{t-1} - 1
    rets = closes[1:] / closes[:-1] - 1.0

    # 年化波动率 = 日收益率标准差 * sqrt(252)
    vol = np.std(rets) * np.sqrt(252)
    return vol

def rebalance(context):
    """每周调仓：根据当前波动率调整仓位，使组合波动率逼近目标。"""

    # 1. 计算当前年化波动率
    vol = calc_annual_vol(context, g.security, g.lookback)
    if vol is None or vol <= 0:
        return

    # 2. 目标仓位 = 目标波动率 / 当前波动率（波动率越高，仓位越低）
    #    例：目标15%，当前30% → 仓位 0.5（半仓）
    #        目标15%，当前10% → 仓位 1.0（满仓，受 max_weight 限制）
    target_weight = g.target_vol / vol
    target_weight = min(g.max_weight, max(g.min_weight, target_weight))

    # 3. 把仓位调整到目标市值
    target_value = context.portfolio.total_value * target_weight
    order_target_value(g.security, target_value)

    # 4. 记录日志（便于观察仓位随波动率的变化）
    log.info('当前年化波动率: %.2f%%, 目标仓位: %.2f%%' % (vol * 100, target_weight * 100))
