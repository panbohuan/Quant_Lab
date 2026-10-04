# -*- coding: utf-8 -*-
"""
jqbt —— 本地聚宽风格回测引擎
================================================================================
一个轻量级、教学友好的回测框架，让你在 PyCharm 本地一键回测聚宽风格策略。

快速开始（策略文件底部）：
    from jqbt import run_backtest, login, plot_result

    login("你的聚宽手机号", "你的密码")   # 或设置环境变量 JQDATA_PHONE / JQDATA_PASSWORD

    result = run_backtest(initialize, start_date='2016-01-01', end_date='2026-01-01',
                          initial_cash=1000000)
    print(result.summary())
    plot_result(result)

子模块：
    jqbt.data     —— jqdatasdk 数据适配层（登录、拉数据、缓存）
    jqbt.api      —— 聚宽风格 API（g / context / log / order_* / attribute_history 等）
    jqbt.engine   —— 回测引擎（调度、撮合、持仓、资金、绩效）
    jqbt.metrics  —— 绩效可视化（净值曲线、回撤曲线、持仓图）
================================================================================
"""
from .engine import BacktestEngine, BacktestResult, run_backtest
from .data import login, is_auth, clear_cache
from .api import g, log
from .metrics import plot_result, plot_positions

__all__ = [
    'run_backtest', 'BacktestEngine', 'BacktestResult',
    'login', 'is_auth', 'clear_cache',
    'g', 'log', 'plot_result', 'plot_positions',
]

__version__ = '1.0.0'
