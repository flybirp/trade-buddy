#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trade-buddy 富途数据源适配层（futu-api / OpenD）

用途：补齐 westock-data 在港美股上的能力缺口——卖空数据、逐笔、买卖盘、
      实时快照（市值/每手股数）、机构持仓、内部人交易、财报多口径。

前提：本地必须运行富途 OpenD 客户端并已登录（默认 127.0.0.1:11111）。
      没有 OpenD 时本脚本会立即返回 UNAVAILABLE，绝不阻塞（futu-api 默认
      无限重连，必须先探测端口再构造连接）。

依赖：pip install futu-api

用法：
    python3 futu_quote.py probe
    python3 futu_quote.py snapshot HK.03888
    python3 futu_quote.py basic HK 03888
    python3 futu_quote.py shortvol HK.03888 30
    python3 futu_quote.py shortinterest HK.03888
    python3 futu_quote.py capitalflow HK.03888
    python3 futu_quote.py capitaldist HK.03888
    python3 futu_quote.py kline HK.03888 60 K_DAY
    python3 futu_quote.py holder HK.03888
    python3 futu_quote.py insider HK.03888
    python3 futu_quote.py earnings HK.03888
    python3 futu_quote.py plates HK.03888
    python3 futu_quote.py shortselling HK

代码格式：港股 HK.03888 / 美股 US.AAPL / A股 SH.600000
输出：Markdown 表格（与 westock-data 输出风格一致，便于统一解析）
退出码：0=成功  3=OpenD 不可用  4=参数错误  5=查询失败
"""

import socket
import sys

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 11111
PROBE_TIMEOUT = 1.0


def probe(host=DEFAULT_HOST, port=DEFAULT_PORT, timeout=PROBE_TIMEOUT):
    """探测 OpenD 端口。返回 (bool, detail)。必须先探测——futu-api 会无限重连。"""
    s = socket.socket()
    s.settimeout(timeout)
    try:
        rc = s.connect_ex((host, port))
    except Exception as e:
        return False, str(e)
    finally:
        s.close()
    return rc == 0, "port {} {}".format(port, "open" if rc == 0 else "closed(errno=%d)" % rc)


def _ctx(host, port):
    """仅在探测通过后调用。构造 OpenQuoteContext。"""
    from futu import OpenQuoteContext, SysConfig
    # 关闭无限重连，失败立即返回
    try:
        SysConfig.set_init_rsa_file("")
    except Exception:
        pass
    return OpenQuoteContext(host=host, port=port)


def _emit_md(df, title=""):
    """把 DataFrame 输出为 Markdown 表格。"""
    if df is None or (hasattr(df, "empty") and df.empty):
        print("(无数据)")
        return
    if title:
        print("\n**%s**\n" % title)
    try:
        print(df.to_markdown(index=False))
    except Exception:
        cols = list(df.columns)
        print("| " + " | ".join(cols) + " |")
        print("|" + "|".join(["---"] * len(cols)) + "|")
        for _, row in df.iterrows():
            print("| " + " | ".join(str(row[c]) for c in cols) + " |")


def _run(fn, host, port):
    """统一的 探测 → 连接 → 执行 → 关闭 流程。"""
    ok, detail = probe(host, port)
    if not ok:
        print("UNAVAILABLE: OpenD 未运行 (%s)" % detail)
        print("---")
        print("启用方式：启动富途 OpenD 客户端并登录账户，确认监听 %s:%d 后重试。" % (host, port))
        print("未启用 OpenD 时，trade-buddy 应回退到 westock-data，并在数据缺口中标注卖空/盘口数据缺失。")
        return 3
    from futu import RET_OK
    ctx = None
    try:
        ctx = _ctx(host, port)
        ret, data = fn(ctx)
        if ret != RET_OK:
            print("QUERY_FAILED: %s" % data)
            return 5
        if isinstance(data, tuple):
            for part in data:
                _emit_md(part)
        else:
            _emit_md(data)
        return 0
    except Exception as e:
        print("ERROR: %s: %s" % (type(e).__name__, str(e)[:300]))
        return 5
    finally:
        if ctx is not None:
            try:
                ctx.close()
            except Exception:
                pass


def main():
    argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        return 4

    cmd = argv[0].lower()
    args = argv[1:]
    host, port = DEFAULT_HOST, DEFAULT_PORT

    # 支持 --host/--port
    parsed = []
    i = 0
    while i < len(args):
        if args[i] == "--host" and i + 1 < len(args):
            host = args[i + 1]; i += 2
        elif args[i] == "--port" and i + 1 < len(args):
            port = int(args[i + 1]); i += 2
        else:
            parsed.append(args[i]); i += 1
    args = parsed

    if cmd == "probe":
        ok, detail = probe(host, port)
        print("OpenD: %s (%s)" % ("AVAILABLE" if ok else "UNAVAILABLE", detail))
        return 0 if ok else 3

    if not args:
        print("缺少标的代码\n" + __doc__)
        return 4

    code = args[0]

    if cmd == "snapshot":
        return _run(lambda c: c.get_market_snapshot([code]), host, port)
    if cmd == "basic":
        market = args[0]
        codes = args[1:] or None
        return _run(lambda c: c.get_stock_basicinfo(market, code_list=codes), host, port)
    if cmd == "shortvol":
        num = int(args[1]) if len(args) > 1 else 30
        return _run(lambda c: c.get_daily_short_volume(code, num=num), host, port)
    if cmd == "shortinterest":
        from futu import SHORT_INTEREST_SORT_COL
        return _run(lambda c: c.get_short_interest(code), host, port)
    if cmd == "capitalflow":
        return _run(lambda c: c.get_capital_flow(code), host, port)
    if cmd == "capitaldist":
        return _run(lambda c: c.get_capital_distribution(code), host, port)
    if cmd == "kline":
        num = int(args[1]) if len(args) > 1 else 60
        ktype = args[2] if len(args) > 2 else "K_DAY"
        return _run(lambda c: c.get_cur_kline(code, num, ktype=ktype), host, port)
    if cmd == "holder":
        return _run(lambda c: c.get_shareholders_institutional(code), host, port)
    if cmd == "insider":
        return _run(lambda c: c.get_insider_trade_list(code), host, port)
    if cmd == "earnings":
        return _run(lambda c: c.get_financials_statements(code), host, port)
    if cmd == "plates":
        return _run(lambda c: c.get_owner_plate([code]), host, port)
    if cmd == "shortselling":
        return _run(lambda c: c.get_short_selling_rank(market=code), host, port)

    print("未知命令: %s\n%s" % (cmd, __doc__))
    return 4


if __name__ == "__main__":
    sys.exit(main())
