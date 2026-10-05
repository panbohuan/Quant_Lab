# -*- coding: utf-8 -*-
"""
btlab —— Quant_Lab 本地回测工具包

    datasource.py  免费长历史数据适配（akshare：新浪 / 中证 / 东财 / 申万）
    runner.py      backtrader 样板封装（A 股费用、滑点、净值记录、绩效报告）
    metrics.py     绩效指标计算与净值/回撤绘图

回测内核是 backtrader 官方引擎，本包不含任何自研撮合/账务逻辑。
用法见 docs/本地回测使用指南.md，策略见 strategies/backtrader/。
"""
__version__ = '4.1.1'
