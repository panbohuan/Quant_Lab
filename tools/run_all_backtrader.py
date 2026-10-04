# -*- coding: utf-8 -*-
"""
批量运行全部 backtrader 策略并汇总绩效
================================================================================
用法（在项目根目录执行）：

    python tools/run_all_backtrader.py              # 跑全部 20 个
    python tools/run_all_backtrader.py s01 a05      # 只跑名字里含 s01 / a05 的
    python tools/run_all_backtrader.py --no-plot    # 预留：不带图跑（当前始终画图）

它会：
  1. 依次用当前解释器运行 strategies/backtrader/{beginner,advanced}/ 下的全部脚本；
  2. 把每个策略的完整输出写到 results/logs/<策略名>.log；
  3. 在终端打印一张汇总绩效表（累计收益 / 年化 / 最大回撤 / 夏普 / 耗时）。

注意：首次运行需要联网拉取数据（约 3~10 分钟），之后有 data_cache/ 缓存会快很多。
================================================================================
"""
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(ROOT, 'results', 'logs')
BASE = os.path.join(ROOT, 'strategies', 'backtrader')


def discover():
    """按「入门 → 进阶」的顺序收集全部策略脚本。"""
    targets = []
    for level in ('beginner', 'advanced'):
        d = os.path.join(BASE, level)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if fn.endswith('.py') and fn.startswith('bt_'):
                targets.append((level, fn, os.path.join(d, fn)))
    return targets


def main():
    os.makedirs(LOG_DIR, exist_ok=True)
    wins = [a for a in sys.argv[1:] if not a.startswith('-')]
    targets = discover()
    if wins:
        targets = [t for t in targets if any(w in t[1] for w in wins)]

    print(f'共 {len(targets)} 个 backtrader 策略待运行\n')
    rows = []
    for i, (level, fn, path) in enumerate(targets, 1):
        print(f'[{i}/{len(targets)}] {level}/{fn} ...', flush=True)
        t0 = time.time()
        try:
            p = subprocess.run([sys.executable, path], cwd=ROOT, capture_output=True,
                               text=True, encoding='utf-8', errors='replace',
                               timeout=3600)
            out = (p.stdout or '') + (p.stderr or '')
            code = p.returncode
        except subprocess.TimeoutExpired:
            out, code = 'TIMEOUT: 运行超过 1 小时', -1
        dt = time.time() - t0

        with open(os.path.join(LOG_DIR, fn.replace('.py', '.log')), 'w',
                  encoding='utf-8') as f:
            f.write(out)

        def grab(label):
            m = re.search(label + r'\s*:\s*(-?[\d.]+)', out)
            return float(m.group(1)) if m else None

        if code != 0 or '累计收益率' not in out:
            lines = [l for l in out.strip().splitlines() if l.strip()]
            tail = '\n'.join(lines[-8:])
            print(f'    ✗ 失败（{dt:.0f}s）\n{tail}\n', flush=True)
            rows.append((level, fn, 'FAIL', None, None, None, None, dt))
            continue
        rows.append((level, fn, 'OK', grab('累计收益率'), grab('年化收益率'),
                     grab('最大回撤'), grab('夏普比率'), dt))
        print(f'    ✓ {dt:.0f}s  累计 {grab("累计收益率")}%  年化 {grab("年化收益率")}%  '
              f'回撤 {grab("最大回撤")}%  夏普 {grab("夏普比率")}', flush=True)

    print('\n' + '=' * 92)
    print(f'{"策略":<34}{"状态":<6}{"累计%":>10}{"年化%":>10}{"回撤%":>10}{"夏普":>8}{"耗时s":>8}')
    print('-' * 92)
    for level, fn, st, tot, ann, dd, sh, dt in rows:
        name = f'{level[:3]}/{fn[:-3]}'
        print(f'{name:<34}{st:<6}'
              f'{(tot or 0):>10.2f}{(ann or 0):>10.2f}{(dd or 0):>10.2f}'
              f'{(sh or 0):>8.2f}{dt:>8.0f}')
    print('=' * 92)
    bad = [r for r in rows if r[2] != 'OK']
    print(f'成功 {len(rows) - len(bad)}/{len(rows)}，失败 {len(bad)} 个')
    print(f'完整输出见 {os.path.relpath(LOG_DIR, ROOT)}/')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
