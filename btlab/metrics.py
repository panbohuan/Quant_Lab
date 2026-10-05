# -*- coding: utf-8 -*-
"""
btlab.metrics —— 由每日净值算绩效指标（累计/年化收益、最大回撤、夏普、波动率、
日胜率）并绘制净值 + 回撤曲线；另含基准对比与由成交记录估算的累计换手率。
"""
import numpy as np
import pandas as pd


def perf_from_nav(nav, initial_cash=None):
    """由每日净值（账户总资产）序列计算绩效指标，返回 dict。

    参数：
        nav          : pd.Series(index=date, values=账户总资产或净值)
        initial_cash : 若给出，则期末资产按「净值起点=初始资金」折算；
                       为 None 时直接把 nav 的最后一个值当作期末资产（元）。
    """
    nav = pd.Series(nav).dropna()
    if len(nav) < 2:
        return {}
    rets = nav.pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    base = float(nav.iloc[0])
    last = float(nav.iloc[-1])
    if base <= 0:                     # 净值起点非正（异常），避免除零
        return {}

    total = last / base - 1.0
    years = len(nav) / 252.0
    annual = ((last / base) ** (1 / years) - 1) if (years > 0 and last > 0) else float('nan')
    peak = nav.cummax()
    drawdown = nav / peak - 1.0
    max_dd = drawdown.min()
    vol = rets.std() * np.sqrt(252)
    sharpe = (rets.mean() / rets.std() * np.sqrt(252)) if rets.std() > 0 else 0.0
    r = rets[rets != 0]
    win = (r > 0).mean() if len(r) else 0.0
    final_value = last if initial_cash is None else float(last / base * initial_cash)

    return {
        'start': nav.index[0], 'end': nav.index[-1], 'days': len(nav),
        'total_return': float(total), 'annual_return': float(annual),
        'max_drawdown': float(max_dd), 'sharpe': float(sharpe),
        'volatility': float(vol), 'win_rate': float(win),
        'final_value': final_value,
        'drawdown_series': drawdown,
    }


def format_report(metrics, initial_cash=None, benchmark_ret=None, trade_count=None,
                  turnover=None, title='回测绩效报告（backtrader）'):
    """把绩效指标格式化为可打印的中文报告字符串。

    turnover 为「累计成交额 / 初始资金」，即区间累计换手率。
    """
    lines = ['=' * 60, title, '=' * 60]
    if initial_cash is not None:
        lines.append(f"初始资金        : {initial_cash:,.0f} 元")
    lines.append(f"期末资产        : {metrics.get('final_value', 0):,.0f} 元")
    lines.append(f"累计收益率      : {metrics.get('total_return', 0) * 100:8.2f}%")
    lines.append(f"年化收益率      : {metrics.get('annual_return', 0) * 100:8.2f}%")
    if benchmark_ret is not None and not np.isnan(benchmark_ret):
        lines.append(f"基准累计收益率  : {benchmark_ret * 100:8.2f}%")
        lines.append(f"超额收益(vs基准): {(metrics.get('total_return', 0) - benchmark_ret) * 100:8.2f}%")
    lines.append(f"最大回撤        : {metrics.get('max_drawdown', 0) * 100:8.2f}%")
    lines.append(f"夏普比率        : {metrics.get('sharpe', 0):8.2f}")
    lines.append(f"年化波动率      : {metrics.get('volatility', 0) * 100:8.2f}%")
    lines.append(f"日胜率          : {metrics.get('win_rate', 0) * 100:8.2f}%")
    if trade_count is not None:
        lines.append(f"总成交笔数      : {trade_count}")
    if turnover is not None:
        lines.append(f"累计换手率      : {turnover * 100:8.2f}%  (累计成交额/初始资金)")
    lines.append(f"回测区间        : {str(metrics.get('start'))[:10]} ~ {str(metrics.get('end'))[:10]}"
                 f"（{metrics.get('days', 0)} 个交易日）")
    lines.append('=' * 60)
    return '\n'.join(lines)


def plot_equity(nav, benchmark_nav=None, save_path=None, title='策略净值曲线',
                drawdown_series=None, show=False):
    """绘制净值曲线 + 回撤曲线（上下两个子图）。

    参数：
        nav              : 策略净值 Series
        benchmark_nav    : 基准净值 Series（可空）
        save_path        : 图片保存路径（如 'bt_s01_result.png'）
        drawdown_series  : 回撤序列（可空；为空时由 nav 计算）
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import rcParams

    rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
    rcParams['axes.unicode_minus'] = False

    # 统一归一化到「起点=1」，这样账户总资产与净值两种口径都能直接画
    nav = pd.Series(nav).dropna()
    nav = nav / nav.iloc[0]
    if drawdown_series is None:
        drawdown_series = (nav / nav.cummax() - 1.0)
    else:
        drawdown_series = pd.Series(drawdown_series).reindex(nav.index)
    if benchmark_nav is not None and len(benchmark_nav):
        benchmark_nav = pd.Series(benchmark_nav).dropna()
        benchmark_nav = benchmark_nav / benchmark_nav.iloc[0]

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True,
                             gridspec_kw={'height_ratios': [2.2, 1]})
    ax1, ax2 = axes

    ax1.plot(nav.index, nav.values, label='策略净值', color='#c0392b', linewidth=1.6)
    if benchmark_nav is not None and len(benchmark_nav):
        ax1.plot(benchmark_nav.index, benchmark_nav.values, label='基准净值',
                 color='#2c7fb8', linewidth=1.2, alpha=0.85)
    ax1.axhline(1.0, color='#888888', linewidth=0.8, linestyle='--')
    ax1.set_title(title, fontsize=13)
    ax1.set_ylabel('净值（起点=1）')
    ax1.legend(loc='upper left')
    ax1.grid(alpha=0.3)

    ax2.fill_between(drawdown_series.index, drawdown_series.values * 100, 0,
                     color='#e67e22', alpha=0.55)
    ax2.set_ylabel('回撤（%）')
    ax2.set_xlabel('日期')
    ax2.grid(alpha=0.3)

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=120)
        print(f'[btlab] 图表已保存: {save_path}')
    if show:
        plt.show()
    plt.close(fig)
