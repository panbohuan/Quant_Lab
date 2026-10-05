# -*- coding: utf-8 -*-
"""
btlab.datasource —— 免费数据源适配层（akshare，不依赖聚宽）

提供股票/指数/ETF 日线、指数成分股、个股估值与市值、财务指标、申万行业、可转债、
指数 PE，全部来自公开免费源（新浪 / 中证 / 东财 / 申万 / 乐咕乐股）。

特性：磁盘缓存（data_cache/）、网络抖动自动重试、代码归一化。
局限：成分股与行业分类只有「当前」快照，历史回测存在幸存者偏差。
"""
import os
import re
import time

import pandas as pd

# ============================ 缓存目录 ============================
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CACHE_DIR = os.path.join(_ROOT, 'data_cache')


def cache_dir():
    """返回缓存目录（不存在则创建）。"""
    os.makedirs(_CACHE_DIR, exist_ok=True)
    return _CACHE_DIR


def clear_cache(prefix=None):
    """清空本地数据缓存（prefix 可指定只清某类，如 'daily_'）。返回删除文件数。"""
    d = cache_dir()
    n = 0
    for fn in os.listdir(d):
        if fn.endswith('.csv') and (prefix is None or fn.startswith(prefix)):
            os.remove(os.path.join(d, fn))
            n += 1
    return n


def _cache_path(name):
    return os.path.join(cache_dir(), name)


def _fresh(fp, days=30):
    """缓存文件是否存在且未过期（按文件修改时间判断）。"""
    return os.path.exists(fp) and (time.time() - os.path.getmtime(fp)) < days * 86400


def _retry(fn, tries=3, wait=1.2):
    """网络抖动自动重试。"""
    last = None
    for _ in range(tries):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(wait)
    raise last


def _today():
    return time.strftime('%Y-%m-%d')


def _refresh_floor(days=7):
    """缓存「新鲜度」下界：缓存里最新日期早于今天-7天，就认为该刷新了。"""
    return (pd.Timestamp(_today()) - pd.Timedelta(days=days)).strftime('%Y-%m-%d')


def _slice(df, start, end):
    """按日期区间切片（start/end 为 'YYYY-MM-DD' 字符串）。"""
    if df is None or len(df) == 0:
        return df
    return df[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))]


# ============================ 代码归一化 ============================
# 常见「裸 6 位数字」指数白名单：这些代码写出来时按指数处理。
# 注意：000001 默认按【平安银行(SZ)】处理——上证指数请显式写 'sh000001' 或 kind='index'。
_INDEX_KNOWN = {
    '000300', '000905', '000016', '000852', '000688', '000010', '000009',
    '000985', '000922', '000906', '000903', '000991', '000992', '000990',
}
# 显式写成 sh 前缀时视为指数的代码（sz000001 仍是平安银行，不是指数）
_INDEX_EXPLICIT = {'000001', '000002', '000003', '000300', '000905', '000016',
                   '000852', '000688', '000010', '000009'}
# 指数号码段前缀（399xxx 深市指数、930/980 中证指数、801xxx 申万、88xxxx 万得）
_INDEX_PREFIX = ('399', '930', '980', '801', '88')
# ETF / 场内基金号码段
_ETF_PREFIX = ('159', '150', '510', '511', '512', '513', '515', '516', '518',
               '560', '561', '562', '563', '588', '589', '501', '502', '506',
               '508', '159', '160', '161', '162', '163', '164', '165', '166',
               '167', '168', '169', '18')


def _plain(code):
    """取 6 位纯数字部分。"""
    c = str(code).strip().lower().replace('.', '')
    if c.startswith(('sh', 'sz', 'bj')):
        c = c[2:]
    return c.zfill(6) if c.isdigit() else c


def _explicit_market(code):
    """若调用者写了 sh/sz/bj 前缀，返回该前缀，否则 None。"""
    c = str(code).strip().lower().replace('.', '')
    return c[:2] if c.startswith(('sh', 'sz', 'bj')) else None


def classify(code):
    """把代码判定为 'index' / 'etf' / 'stock'。"""
    num = _plain(code)
    pre = _explicit_market(code)
    if num in _INDEX_KNOWN or num.startswith(_INDEX_PREFIX):
        return 'index'
    if pre == 'sh' and num in _INDEX_EXPLICIT:
        return 'index'
    if num.startswith(_ETF_PREFIX):
        return 'etf'
    return 'stock'


def normalize_code(code, kind=None):
    """归一化为新浪风格代码（小写市场前缀 + 6 位数字）。

    例：'600000'→'sh600000'、'000001'→'sz000001'、'000300'→'sh000300'、
        '510300'→'sh510300'、'159915'→'sz159915'、'sh000001'→'sh000001'。

    kind 可显式指定 'stock' / 'etf' / 'index'，用于消除 000001 这类歧义。
    """
    pre = _explicit_market(code)
    num = _plain(code)
    if pre:                       # 调用者已显式指定市场，直接尊重
        return pre + num
    kind = kind or classify(num)
    if kind == 'index':
        return ('sz' if num.startswith('399') else 'sh') + num
    if num.startswith(('6', '9', '5')):
        return 'sh' + num
    if num.startswith(('0', '3', '1', '2')):
        return 'sz' + num
    if num.startswith(('4', '8')):
        return 'bj' + num
    return 'sh' + num


def is_index(code):
    """判断是否为指数代码。"""
    return classify(code) == 'index'


def is_etf(code):
    return classify(code) == 'etf'


# ============================ 日线行情 ============================

_INDEX_NAME = {'000300': '沪深300', '000905': '中证500', '000016': '上证50',
               '000852': '中证1000', '399006': '创业板指', '000688': '科创50',
               '000001': '上证指数', '399001': '深证成指'}


def index_name(code):
    return _INDEX_NAME.get(_plain(code), normalize_code(code))


def _standardize(df):
    """列名/类型统一为 [open, high, low, close, volume]。"""
    df = df.copy()
    df.index = pd.to_datetime(df.index)
    for col in ['open', 'high', 'low', 'close', 'volume']:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors='coerce')
    return df[['open', 'high', 'low', 'close', 'volume']].sort_index()


def load_daily(code, start='2010-01-01', end=None, adjust='qfq', kind=None,
               use_cache=True):
    """加载日线行情（自动识别 股票 / ETF / 指数）。

    参数：
        code   : '600000' / 'sh600000' / '000001' / '510300' / '000300' ...
        start  : 'YYYY-MM-DD'
        end    : 'YYYY-MM-DD'，None 表示到今天
        adjust : 'qfq' 前复权 / 'hfq' 后复权 / '' 不复权（指数与 ETF 忽略）
        kind   : 'stock' / 'etf' / 'index'，显式指定可消除 000001 歧义
    返回：
        DataFrame(index=DatetimeIndex, columns=[open, high, low, close, volume])

    缓存说明：磁盘上按「标的 + 复权方式」缓存**整段历史**，所以同一天里
    不同 start/end 的多次调用只联网一次，速度极快。
    """
    c = normalize_code(code, kind=kind)
    k = kind or classify(c)
    if k == 'etf' and adjust == 'qfq':
        adjust = 'hfq'            # ETF 新浪只有不复权价，默认按「含分红」口径处理
    start = str(start)[:10] if start else '1990-01-01'
    end = str(end)[:10] if end else _today()
    if end > _today():            # 数据源偶尔给出未来交易日，统一截断
        end = _today()

    fp = _cache_path(f'daily_{c}_{k}_{adjust or "raw"}.csv')
    if use_cache and os.path.exists(fp):
        cached = _standardize(pd.read_csv(fp, parse_dates=['date'], index_col='date'))
        # 数据日期够新，或缓存本身是最近 7 天内写的（退市标的不会再更新）→ 直接用
        if len(cached) and (str(cached.index[-1].date()) >= _refresh_floor(7)
                            or _fresh(fp, 7)):
            return _slice(cached, start, end)

    import akshare as ak
    if k == 'index':
        df = _retry(lambda: ak.stock_zh_index_daily(symbol=c))
    elif k == 'etf':
        df = _retry(lambda: ak.fund_etf_hist_sina(symbol=c))
    else:
        df = _retry(lambda: ak.stock_zh_a_daily(
            symbol=c, start_date='19900101', end_date=end.replace('-', ''),
            adjust=adjust or ''))

    if df is None or len(df) == 0:
        raise RuntimeError(f'未取到 {code} 的行情数据（{start} ~ {end}）')

    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
    out = _standardize(df)
    out = _slice(out, '1990-01-01', end)
    # ETF 只有不复权价；若请求 hfq，则加回历史累计分红做「含分红」口径修正
    if k == 'etf' and adjust == 'hfq':
        try:
            out = _apply_etf_dividend(out, _etf_dividend_table(c))
        except Exception as e:  # noqa: BLE001
            print(f'  [提示] {c} 分红数据不可用，ETF 按不复权价回测：{str(e)[:50]}')
    if use_cache:
        out.to_csv(fp, encoding='utf-8')
    return _slice(out, start, end)


def _etf_dividend_table(code, use_cache=True):
    """场内基金累计分红表（新浪），返回 Series(index=date, values=累计每份分红)。"""
    c = normalize_code(code, kind='etf')
    fp = _cache_path(f'etfdiv_{c}.csv')
    if use_cache and os.path.exists(fp):
        s = pd.read_csv(fp, parse_dates=['日期'], index_col='日期').iloc[:, 0]
        return pd.to_numeric(s, errors='coerce').sort_index()
    import akshare as ak
    df = _retry(lambda: ak.fund_etf_dividend_sina(symbol=c))
    df = df.copy()
    df['日期'] = pd.to_datetime(df['日期'])
    df = df.set_index('日期').sort_index()
    s = pd.to_numeric(df['累计分红'], errors='coerce')
    if use_cache:
        s.to_csv(fp, encoding='utf-8')
    return s


def _apply_etf_dividend(df, cum_div):
    """把 ETF 不复权价改造成「含分红」口径：adj(t) = 价格(t) + 截至 t 的累计分红。

    这样 (adj_end - adj_start) / adj_start 就等于「价格涨跌 + 期间分红」的真实总收益，
    用来弥补新浪 ETF 接口只提供不复权价的缺陷。
    """
    if cum_div is None or len(cum_div) == 0:
        return df
    s = cum_div.sort_index()
    s = s.reindex(s.index.union(df.index)).ffill().fillna(0.0)
    d = s.reindex(df.index).fillna(0.0).values
    out = df.copy()
    for col in ['open', 'high', 'low', 'close']:
        out[col] = out[col].values + d
    return out


def load_many(codes, start='2010-01-01', end=None, adjust='qfq', kind=None,
              verbose=True):
    """批量加载多只标的，返回 {归一化代码: DataFrame}（失败的跳过并提示）。"""
    out = {}
    for i, code in enumerate(codes, 1):
        try:
            out[normalize_code(code, kind=kind)] = load_daily(code, start, end, adjust, kind)
        except Exception as e:  # noqa: BLE001
            if verbose:
                print(f'  [跳过] {code}: {str(e)[:60]}')
        if verbose and i % 20 == 0:
            print(f'  已加载 {i}/{len(codes)} ...', flush=True)
    return out


# ============================ 指数成分股 ============================

def load_index_members(index_code='000300'):
    """加载指数成分股（中证指数官网优先，新浪兜底），返回股票代码列表。"""
    num = _plain(index_code)
    fp = _cache_path(f'members_{num}.csv')
    if _fresh(fp, 30):
        return pd.read_csv(fp, dtype=str)['code'].tolist()

    import akshare as ak
    try:
        df = _retry(lambda: ak.index_stock_cons_csindex(symbol=num))
        col = '成分券代码' if '成分券代码' in df.columns else df.columns[4]
        raw = [str(x).zfill(6) for x in df[col].tolist()]
    except Exception:
        df = _retry(lambda: ak.index_stock_cons_sina(symbol=num))
        col = '品种代码' if '品种代码' in df.columns else df.columns[0]
        raw = [str(x).zfill(6) for x in df[col].tolist()]

    # 【关键】成分股列里是股票代码，必须按「股票」规则归一化，不能按指数规则
    codes = [normalize_code(x, kind='stock') for x in raw]
    pd.DataFrame({'code': codes}).to_csv(fp, index=False, encoding='utf-8')
    return codes


# ============================ 个股估值 / 市值 ============================

_VALUE_RENAME = {'数据日期': 'date', '当日收盘价': 'close', '总市值': 'total_mv',
                 '流通市值': 'circ_mv', 'PE(TTM)': 'pe_ttm', 'PE(静)': 'pe',
                 '市净率': 'pb', '市销率': 'ps', 'PEG值': 'peg'}


def load_stock_value(code, use_cache=True):
    """个股每日估值与市值（东方财富，约 2018 年起）。

    返回 DataFrame(index=date, columns=[close, total_mv, circ_mv, pe_ttm, pe, pb, ps, peg])
        其中 total_mv / circ_mv 单位为「元」。
    """
    c = normalize_code(code, kind='stock')
    fp = _cache_path(f'value_{c}.csv')
    if use_cache and os.path.exists(fp):
        return pd.read_csv(fp, parse_dates=['date'], index_col='date')

    import akshare as ak
    df = _retry(lambda: ak.stock_value_em(symbol=_plain(c)))
    if df is None or len(df) == 0:
        raise RuntimeError(f'未取到 {code} 的估值数据')
    df = df.rename(columns=_VALUE_RENAME)
    keep = [k for k in ['date', 'close', 'total_mv', 'circ_mv', 'pe_ttm', 'pe', 'pb', 'ps', 'peg']
            if k in df.columns]
    df = df[keep].copy()
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date').sort_index()
    for col in keep[1:]:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    if use_cache:
        df.to_csv(fp, encoding='utf-8')
    return df


# ============================ 个股财务指标 ============================

def load_financial_indicator(code, start_year='2015', use_cache=True):
    """个股财务指标（新浪财经，季度）。

    常用字段：'净资产收益率(%)'、'净利润增长率(%)'、'销售毛利率(%)' 等。
    返回 DataFrame(index=报告期 date, columns=指标)。
    """
    c = normalize_code(code, kind='stock')
    fp = _cache_path(f'fin_{c}_{start_year}.csv')
    if use_cache and os.path.exists(fp):
        return pd.read_csv(fp, parse_dates=['日期'], index_col='日期')

    import akshare as ak
    df = _retry(lambda: ak.stock_financial_analysis_indicator(
        symbol=_plain(c), start_year=str(start_year)))
    if df is None or len(df) == 0:
        raise RuntimeError(f'未取到 {code} 的财务数据')
    df = df.copy()
    df['日期'] = pd.to_datetime(df['日期'])
    df = df.set_index('日期').sort_index()
    if use_cache:
        df.to_csv(fp, encoding='utf-8')
    return df


def roe_series(code, start_year='2015'):
    """便捷函数：取 ROE 序列（净资产收益率 %）。"""
    df = load_financial_indicator(code, start_year=start_year)
    for col in ['净资产收益率(%)', '加权净资产收益率(%)']:
        if col in df.columns:
            return pd.to_numeric(df[col], errors='coerce').dropna()
    raise RuntimeError(f'{code} 财务数据中未找到 ROE 字段')


# ============================ 申万行业（行业轮动） ============================

def sw_industries(use_cache=True):
    """申万一级行业列表，返回 DataFrame(columns=[code, name])。"""
    fp = _cache_path('sw_l1_list.csv')
    if use_cache and _fresh(fp, 30):
        return pd.read_csv(fp, dtype=str)
    import akshare as ak
    df = _retry(lambda: ak.sw_index_first_info())
    df = df.rename(columns={df.columns[0]: 'code', df.columns[1]: 'name'})
    out = df[['code', 'name']].copy()
    out['code'] = out['code'].astype(str).str.replace('.SI', '', regex=False).str.zfill(6)
    if use_cache:
        out.to_csv(fp, index=False, encoding='utf-8')
    return out


def load_sw_index(code, start='2010-01-01', end=None, use_cache=True,
                  kind='index'):
    """申万行业指数日线（1999 年起），返回 DataFrame[open,high,low,close,volume]。"""
    num = _plain(code)
    start = str(start)[:10]
    end = str(end)[:10] if end else _today()
    fp = _cache_path(f'sw_{num}.csv')
    if use_cache and os.path.exists(fp):
        return _slice(_standardize(pd.read_csv(fp, parse_dates=['date'], index_col='date')),
                      start, end)
    import akshare as ak
    df = _retry(lambda: ak.index_hist_sw(symbol=num))
    df = df.rename(columns={'日期': 'date', '收盘': 'close', '开盘': 'open',
                            '最高': 'high', '最低': 'low', '成交量': 'volume'})
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
    out = _standardize(df)
    if use_cache:
        out.to_csv(fp, encoding='utf-8')
    return _slice(out, start, end)


def load_sw_members(code, tries=4, wait=2.0):
    """申万行业成分股，返回股票代码列表。

    注意：申万成分接口偶尔会返回异常结构（限流），这里加重试与字段兜底；
    若最终仍失败则抛出 RuntimeError，由上层（industry_map）跳过该行业。
    """
    num = _plain(code)
    fp = _cache_path(f'sw_members_{num}.csv')
    if _fresh(fp, 30):
        return pd.read_csv(fp, dtype=str)['code'].tolist()
    import akshare as ak

    def _fetch():
        df = ak.index_component_sw(symbol=num)
        cols = list(getattr(df, 'columns', []))
        if '证券代码' not in cols:
            # 异常结构（通常是限流），抛错交给 _retry 重试
            raise RuntimeError(f'申万成分返回异常结构: {cols[:6]}')
        return df

    df = _retry(_fetch, tries=tries, wait=wait)
    col = '证券代码'
    codes = [normalize_code(str(x).zfill(6), kind='stock') for x in df[col].tolist()]
    if not codes:
        raise RuntimeError(f'申万行业 {num} 成分为空')
    pd.DataFrame({'code': codes}).to_csv(fp, index=False, encoding='utf-8')
    return codes


# ============================ 指数估值（市场温度） ============================

def load_index_pe(symbol='沪深300', use_cache=True):
    """指数市盈率（乐咕乐股，月度，2005 年起）。返回 Series(index=date, 滚动市盈率)。"""
    fp = _cache_path(f'indexpe_{symbol}.csv')
    if use_cache and os.path.exists(fp):
        s = pd.read_csv(fp, parse_dates=['日期'], index_col='日期').iloc[:, 0]
        return pd.to_numeric(s, errors='coerce')
    import akshare as ak
    df = _retry(lambda: ak.stock_index_pe_lg(symbol=symbol))
    df['日期'] = pd.to_datetime(df['日期'])
    df = df.set_index('日期').sort_index()
    col = '滚动市盈率' if '滚动市盈率' in df.columns else df.columns[-1]
    s = pd.to_numeric(df[col], errors='coerce')
    if use_cache:
        s.to_csv(fp, encoding='utf-8')
    return s


# ============================ 可转债 ============================

def load_bond_universe(top=None, use_cache=True):
    """当前可转债列表（含转股价/正股价，用于计算转股溢价率）。

    返回 DataFrame，含 bond_code / bond_name / price / conv_price / premium_rate 等列。
    """
    fp = _cache_path('cb_list.csv')
    if use_cache and os.path.exists(fp):
        df = pd.read_csv(fp, dtype={'bond_code': str})
    else:
        import akshare as ak
        df = _retry(lambda: ak.bond_zh_cov())
        df.to_csv(fp, index=False, encoding='utf-8')
    return df.head(top) if top else df


def bond_symbol(code):
    """可转债代码归一化：沪市 110/111/113/118xxx→sh，深市 123/127/128xxx→sz。"""
    pre = _explicit_market(code)
    num = _plain(code)
    if pre:
        return pre + num
    return ('sh' if num.startswith(('110', '111', '113', '118', '11')) else 'sz') + num


def load_bond_daily(code, start='2018-01-01', end=None, use_cache=True):
    """可转债日线（新浪），返回 DataFrame[open,high,low,close,volume]。"""
    c = bond_symbol(code)
    start = str(start)[:10]
    end = str(end)[:10] if end else _today()
    fp = _cache_path(f'bond_{c}_{start}_{end}.csv')
    if use_cache and os.path.exists(fp):
        return _standardize(pd.read_csv(fp, parse_dates=['date'], index_col='date'))
    import akshare as ak
    df = _retry(lambda: ak.bond_zh_hs_cov_daily(symbol=c))
    if df is None or len(df) == 0 or 'date' not in getattr(df, 'columns', []):
        raise RuntimeError(f'未取到可转债 {code} 的日线（可能尚未上市或已退市）')
    df = df.copy()
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
    out = _standardize(df)
    out = out[(out.index >= pd.Timestamp(start)) & (out.index <= pd.Timestamp(end))]
    if use_cache and len(out):
        out.to_csv(fp, encoding='utf-8')
    return out


def listed_bonds(before='2019-01-01', top=None, min_size=0.0, use_cache=True):
    """筛选在 `before` 之前已上市的可转债。

    返回 DataFrame，含 bond_code / bond_name / list_date / price / conv_price /
    premium / issue_size / rating 等列（按发行规模降序）。
    注意：转股溢价率等字段是**当前时点快照**，没有历史序列，属于本数据源的已知局限。
    """
    df = load_bond_universe(use_cache=use_cache).copy()
    df['list_date'] = pd.to_datetime(df.get('上市时间'), errors='coerce')
    df['issue_size'] = pd.to_numeric(df.get('发行规模'), errors='coerce')
    df['price'] = pd.to_numeric(df.get('债现价'), errors='coerce')
    df['conv_price'] = pd.to_numeric(df.get('转股价'), errors='coerce')
    df['premium'] = pd.to_numeric(df.get('转股溢价率'), errors='coerce')
    df['bond_code'] = df['债券代码'].astype(str).str.zfill(6)
    df['bond_name'] = df['债券简称']
    df['rating'] = df.get('信用评级')
    out = df.dropna(subset=['list_date'])
    out = out[out['list_date'] <= pd.Timestamp(before)]
    out = out[out['issue_size'].fillna(0) >= min_size]
    out = out.sort_values('issue_size', ascending=False)
    out = out[['bond_code', 'bond_name', 'list_date', 'price', 'conv_price',
               'premium', 'issue_size', 'rating']]
    return out.head(top) if top else out.reset_index(drop=True)


# ============================ 估值（百度股市通，备用） ============================

def load_valuation(code, indicator='市盈率(TTM)', period='全部'):
    """个股估值序列（百度股市通，长历史但较稀疏）。

    indicator 支持：'市盈率(TTM)'、'市净率'、'市销率(TTM)'、'股息率'
    返回 Series(index=date, values=数值)。
    """
    num = _plain(code)
    safe = indicator.replace('(', '').replace(')', '').replace('率', '')
    fp = _cache_path(f'val_{num}_{safe}_{period}.csv')
    if os.path.exists(fp):
        s = pd.read_csv(fp, parse_dates=['date'], index_col='date').iloc[:, 0]
        return pd.to_numeric(s, errors='coerce')
    import akshare as ak
    df = _retry(lambda: ak.stock_zh_valuation_baidu(symbol=num, indicator=indicator,
                                                    period=period))
    if df is None or len(df) == 0:
        raise RuntimeError(f'未取到 {code} 的估值数据 {indicator}')
    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date').sort_index()
    df.to_csv(fp, encoding='utf-8')
    return pd.to_numeric(df['value'], errors='coerce')
