# PandaAI Factor Research Report

- Candidates: 12; completed: 12; failed: 0
- Settings: 3-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0042
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| low_amount | 0 | -0.0972 | -0.4015 | 21.88% | 30.63% | 15.44% | 6.44% | 5.2836 | 3.11% | 100.00% |
| bias20 | 0 | -0.0740 | -0.4487 | 16.83% | 43.27% | 21.81% | -4.98% | 3.0207 | 7.17% | 66.67% |
| rev20 | 0 | -0.0731 | -0.2939 | 14.50% | 43.63% | 21.99% | -7.49% | 2.9837 | 6.81% | 66.67% |
| small_rev10 | 0 | -0.0514 | -0.4578 | 15.77% | 54.19% | 27.31% | -11.54% | 3.1318 | 6.64% | 66.67% |
| low_price | 0 | -0.0242 | -0.2635 | -10.76% | 2.90% | 1.46% | -12.22% | 3.1598 | 2.83% | 100.00% |
| corr_pv | 0 | -0.0248 | -0.0126 | 0.85% | 36.94% | 18.62% | -17.77% | 4.4394 | 2.86% | 100.00% |
| vol_surge | 0 | -0.0434 | -0.3490 | 11.09% | 61.86% | 31.18% | -20.09% | 3.3252 | 5.55% | 66.67% |
| rev5 | 0 | -0.0515 | -0.4079 | 16.17% | 73.93% | 37.26% | -21.09% | 3.0610 | 7.72% | 66.67% |
| low_pb | 0 | -0.0153 | -0.1175 | -25.42% | 2.92% | 1.47% | -26.89% | 2.6036 | 2.41% | 100.00% |
| value_bm | 1 | 0.0170 | -0.1542 | -25.58% | 3.09% | 1.56% | -27.14% | 2.5220 | 2.44% | 100.00% |
| low_turnover | 0 | -0.0347 | -0.1910 | -22.29% | 26.63% | 13.42% | -35.71% | 4.3332 | 1.77% | 100.00% |
| low_vol | 0 | -0.0324 | -0.0236 | -32.94% | 16.06% | 8.09% | -41.03% | 2.9557 | 1.95% | 100.00% |
