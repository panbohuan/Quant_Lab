# -*- coding: utf-8 -*-
"""
================================================================================
进阶策略 9：高频均值回归策略（Intraday Mean Reversion）
================================================================================
策略类型：日内交易 / 均值回归
难度等级：★★★★★
核心思路：在分钟级数据上，捕捉短期超跌反弹。比如开盘 30 分钟跌幅超过 2% 的
          股票，日内可能反弹。利用"过度反应"后的均值回归效应。

学习重点：
  - 分钟数据获取（get_price frequency='minute' / get_bars）
  - 日内交易成本（T+1 约束、手续费、滑点对高频策略的影响）
  - 超跌反弹的统计规律

进阶价值：从日频到日内，理解高频交易的逻辑和成本结构。
          高频策略的核心不是"预测准"，而是"成本控制"——交易太频繁，
          手续费和滑点会吃掉所有收益。

================================================================================
算法结构
--------------------------------------------------------------------------------
每分钟运行（run_daily 分钟级）：
  1. 获取当日开盘至今的分钟数据
  2. 计算开盘以来累计跌幅
  3. 若某股开盘30分钟内跌幅超过阈值（如 -2%），标记为"超跌"
  4. 买入超跌股，博取日内反弹（注意 T+1：当日买入次日才能卖）
================================================================================
"""


from jqbt.api import *          # 聚宽风格 API
from jqbt import login, run_backtest, plot_result


# ============================ 回测参数（可自由修改） ============================
START_DATE   = '2016-01-01'   # 回测开始日期
END_DATE     = '2024-01-01'   # 回测结束日期
INITIAL_CASH = 1000000        # 初始资金（元）
BENCHMARK    = '000300.XSHG'  # 基准指数（沪深300）

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

# ============================ 一键回测入口 ============================
if __name__ == '__main__':
    # 登录聚宽数据（首次运行请修改 config.py 填入账号，或设置环境变量
    #   JQDATA_PHONE / JQDATA_PASSWORD）
    login()

    # 运行回测（可自由修改 START_DATE / END_DATE / INITIAL_CASH 等参数）
    result = run_backtest(initialize, START_DATE, END_DATE,
                          initial_cash=INITIAL_CASH, benchmark=BENCHMARK)

    # 打印详细绩效报告
    print(result.summary())

    # 绘制净值曲线与回撤曲线，并保存图片
    plot_result(result, save_path='a09_intraday_meanrev_result.png')

