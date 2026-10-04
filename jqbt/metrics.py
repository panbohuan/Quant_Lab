# -*- coding: utf-8 -*-
"""
jqbt.metrics —— 绩效可视化
================================================================================
把回测结果画成图表：净值曲线（策略 vs 基准）、回撤曲线、持仓数量等。
================================================================================
"""
import matplotlib
matplotlib.use('Agg')  # 非交互后端，适配 PyCharm 控制台运行

import matplotlib.pyplot as plt
import numpy as np


def _set_zh_font():
    try:
        plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS']
        plt.rcParams['axes.unicode_minus'] = False
    except Exception:
        pass


def plot_result(result, save_path=None):
    """绘制回测结果：净值曲线 + 回撤曲线。"""
    _set_zh_font()
    df = result.df

    fig, axes = plt.subplots(2, 1, figsize=(12, 9), sharex=True)

    # 上图：净值曲线
    ax1 = axes[0]
    ax1.plot(df.index, df['nav'], label='策略净值', color='#C0392B', linewidth=1.5)
    if df['benchmark_nav'].notna().any():
        ax1.plot(df.index, df['benchmark_nav'], label='基准净值', color='#2980B9',
                 linewidth=1.2, alpha=0.8)
    ax1.set_title('净值曲线（策略 vs 基准）')
    ax1.set_ylabel('净值')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)

    # 下图：回撤曲线
    ax2 = axes[1]
    nav = df['nav']
    drawdown = nav / nav.cummax() - 1.0
    ax2.fill_between(df.index, drawdown, 0, color='#2E7D32', alpha=0.4)
    ax2.plot(df.index, drawdown, color='#1B5E20', linewidth=1.0)
    ax2.set_title('回撤曲线')
    ax2.set_ylabel('回撤')
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"[jqbt] 图表已保存: {save_path}")
    return fig


def plot_positions(result, save_path=None):
    """绘制每日持仓数量（股票数）。"""
    _set_zh_font()
    df = result.df
    if 'positions' not in df.columns:
        return None
    n_pos = df['positions'].apply(lambda p: len(p) if isinstance(p, dict) else 0)

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(df.index, n_pos, color='#8E44AD', linewidth=1.2)
    ax.set_title('每日持仓标的数量')
    ax.set_ylabel('持仓数')
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
    return fig
