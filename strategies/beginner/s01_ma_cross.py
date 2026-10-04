# -*- coding: utf-8 -*-
"""
================================================================================
策略 1：双均线趋势跟踪策略（MA Cross）
================================================================================
策略类型：技术指标择时（单标的，非选股）
难度等级：★☆☆☆☆（入门）
核心思路：短期均线上穿长期均线（金叉）→ 买入；下穿（死叉）→ 卖出。
交易标的：沪深300ETF（510300.XSHG）

【本地一键回测】在 PyCharm 中直接运行本文件即可回测，可自由修改：
  - START_DATE / END_DATE  回测起止日期
  - INITIAL_CASH           初始资金
  - g.short / g.long       均线周期参数

本策略用到的关键函数（聚宽风格，由 jqbt 本地引擎提供）：
  - initialize(context)            策略初始化，注册定时任务与参数
  - set_benchmark / set_option     设定基准与真实价格模式
  - set_order_cost / set_slippage  设定手续费与滑点
  - run_daily(func, time=...)      每天在指定时间运行一次 func
  - attribute_history(...)         获取个股历史K线数据
  - order_target_value(...)        把某标的持仓调整到目标市值
  - log.info(...)                  输出日志（调试用）
================================================================================
"""
from jqbt.api import *          # 聚宽风格 API：g / log / run_daily / attribute_history / order_target_value 等
from jqbt import login, run_backtest, plot_result   # 本地回测引擎


# ============================ 回测参数（可自由修改） ============================
START_DATE = '2016-01-01'   # 回测开始日期
END_DATE   = '2026-01-01'   # 回测结束日期
INITIAL_CASH = 1000000      # 初始资金（元）
BENCHMARK  = '000300.XSHG'  # 基准指数（沪深300）


def initialize(context):
    """初始化函数：回测开始时只运行一次，用于注册配置和定时任务。"""
    # 1. 设定基准：策略收益会与该基准对比（沪深300指数）
    set_benchmark(BENCHMARK)

    # 2. 开启动态复权（真实价格模式），让回测价格更贴近实盘
    set_option('use_real_price', True)

    # 3. 设定交易成本：
    #    - 印花税：卖出时收取 0.1%（close_tax=0.001），买入不收（open_tax=0）
    #    - 佣金：买卖各 0.03%（open/close_commission=0.0003），最低5元
    set_order_cost(
        OrderCost(open_tax=0, close_tax=0.001,
                  open_commission=0.0003, close_commission=0.0003,
                  close_today_commission=0, min_commission=5),
        type='stock'
    )
    # 4. 设定滑点：每次成交比理想价格差 0.02%（模拟冲击成本）
    set_slippage(FixedSlippage(0.02))

    # 5. 过滤 order 相关日志，只保留 error 级别，减少输出噪声
    log.set_level('order', 'error')

    # 6. 用全局变量 g 保存策略参数（g 在整个回测期间都存在）
    g.security = '510300.XSHG'   # 交易标的：沪深300ETF
    g.short = 5                  # 短期均线周期（5日均线）
    g.long = 20                  # 长期均线周期（20日均线）

    # 7. 注册定时任务：每个交易日 14:50（临近收盘）运行一次 trade 函数
    run_daily(trade, time='14:50')


def trade(context):
    """调仓函数：每天 14:50 执行，判断均线是否交叉并据此买卖。"""
    security = g.security

    # 获取过去 g.long+1 个交易日的收盘价（均为已经收盘的完整K线）
    closes = attribute_history(security, g.long + 1, '1d', 'close', df=True)['close']

    # 数据不足保护
    if len(closes) < g.long + 1:
        return

    # 计算"今天"的均线
    short_ma_now = closes.iloc[-g.short:].mean()   # 5日均线
    long_ma_now = closes.iloc[-g.long:].mean()     # 20日均线

    # 计算"昨天"的均线（判断是否发生交叉）
    short_ma_prev = closes.iloc[-g.short - 1:-1].mean()
    long_ma_prev = closes.iloc[-g.long - 1:-1].mean()

    # 金叉：短均线上穿长均线 → 满仓买入
    if short_ma_now > long_ma_now and short_ma_prev <= long_ma_prev:
        order_target_value(security, context.portfolio.total_value * 0.95)
        log.info('金叉买入 %s', security)

    # 死叉：短均线下穿长均线 → 清仓卖出
    elif short_ma_now < long_ma_now and short_ma_prev >= long_ma_prev:
        order_target_value(security, 0)
        log.info('死叉卖出 %s', security)


# ============================ 一键回测入口 ============================
if __name__ == '__main__':
    # 登录聚宽数据（首次运行请先修改 config.py 或设置环境变量）
    login()

    # 运行回测
    result = run_backtest(initialize, START_DATE, END_DATE,
                          initial_cash=INITIAL_CASH, benchmark=BENCHMARK)

    # 打印详细绩效报告
    print(result.summary())

    # 绘制净值曲线与回撤曲线
    plot_result(result, save_path='s01_result.png')
