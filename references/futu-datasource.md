# 富途数据源（futu-api / OpenD）· 增强层

**定位**：`westock-data` 的增强层，**不是替代**。默认仍以 westock 为主；富途只用于补齐 westock 拿不到的字段。

---

## 1. 为什么需要它（westock 的真实缺口）

| 缺口 | 影响 | 富途接口 |
|---|---|---|
| **港股/美股卖空数据** | 无法判断空头压力，港股尤其关键（做空是合法且常见的力量） | `get_daily_short_volume` / `get_short_interest` / `get_short_selling_rank` |
| **市值与每手股数** | 港股 `profile` 无 `regCapital`，市值要靠财报反推；每手股数查不到，无法算最小建仓金额 | `get_market_snapshot` / `get_stock_basicinfo` |
| **实时快照**（PE/PB/换手/振幅/成交额） | westock `quote` 不可用，只能用日K收盘价代替 | `get_market_snapshot` |
| **逐笔成交 / 买卖盘 / 经纪队列** | 无法看盘中真实攻防，只能靠日K猜 | `get_rt_ticker` / `get_order_book` / `get_broker_queue` |
| **资金分布（主力/散户拆分）** | westock `asfund`/`hkfund` 口径与富途不同，无法交叉验证 | `get_capital_distribution` / `get_capital_flow` |
| **机构持仓 / 内部人交易** | westock 港股只给前几大股东 | `get_shareholders_institutional` / `get_insider_trade_list` |
| **财报多口径** | 见 hk-connect 第 8 节：港股需区分归母/经营溢利/Non-IFRS | `get_financials_statements` / `get_financials_revenue_breakdown` |
| **板块归属** | westock 中文板块名搜索无效 | `get_owner_plate` / `get_plate_stock` |

---

## 2. 启用前提（硬性）

富途 OpenAPI **不是纯 HTTP 接口**，必须本地常驻运行 **OpenD 网关客户端**：

1. 下载安装 OpenD（富途官网 openapi.futunn.com）
2. 用富途牛牛 / moomoo **实盘账户登录**
3. 在 OpenD 设置里启用 API 监听（默认 `127.0.0.1:11111`）
4. 部分高级数据（LV2 行情、深度买卖盘、期权链）需满足资产门槛或付费订阅

**没有 OpenD 时本层不可用**，trade-buddy 必须回退到 westock 并在数据缺口中标注。

安装依赖：

```bash
pip install futu-api
```

---

## 3. 用法

```bash
PY=python3                          # 已执行 pip install futu-api 的解释器
S=scripts/futu_quote.py             # 相对本 skill 根目录

$PY $S probe                        # 探测 OpenD（必须先跑，退出码 0=可用 3=不可用）
$PY $S snapshot HK.03888            # 实时快照：市值/每手/PE/PB/换手/振幅
$PY $S basic HK 03888               # 基础信息：每手股数、证券类型
$PY $S shortvol HK.03888 30         # 每日卖空成交量（近 30 日）
$PY $S shortinterest HK.03888       # 空头持仓（淡仓）
$PY $S shortselling HK              # 全市场卖空排行
$PY $S capitalflow HK.03888         # 资金流向
$PY $S capitaldist HK.03888         # 资金分布（主力/散户）
$PY $S kline HK.03888 60 K_DAY      # K线
$PY $S holder HK.03888              # 机构持仓
$PY $S insider HK.03888             # 内部人交易
$PY $S earnings HK.03888            # 财报
$PY $S plates HK.03888              # 所属板块
```

支持 `--host` / `--port` 覆盖默认地址。

### 代码格式转换（易错）

| 市场 | westock | 富途 |
|---|---|---|
| 港股 | `hk03888` | `HK.03888` |
| 沪市 | `sh600000` | `SH.600000` |
| 深市 | `sz000001` | `SZ.000001` |
| 美股 | `usAAPL` | `US.AAPL` |

规则：市场前缀大写 + 点号 + 代码（代码部分原样保留）。

---

## 4. 降级策略（强制）

调用顺序：

1. **先跑 `probe`**。退出码 3 → 直接跳过整个富途层，不要重试。
2. probe 通过 → 按需要取 sell-side 数据。
3. 取数失败 → 用 westock 对应字段替代；拿不到就在「数据缺口」写明，并下调置信度。
4. **禁止**因为富途不可用而中断整个分析流程。

**永远不要让 futu-api 默认重连**：它失败时会无限重试（实测连续重连 19 次以上仍未退出）。`futu_quote.py` 已在构造连接前用 socket 探测端口，不可用时 0.04 秒内返回。

---

## 5. 证据等级

富途数据经 OpenD 直连交易所行情源，口径上属 **L1**（结构化行情接口）。但注意：

- 引用时写清「富途 OpenAPI 接口 `get_xxx`，取数时点 YYYY-MM-DD HH:MM」，与 westock 一样需要接口名 + 时点
- 卖空数据是**交易所披露口径**，不是富途的推断，可信度高
- 财报数据来自富途整理的标准化报表，**与港交所披露易原文不一致时以原文为准**（原文 L1 优先）

---

## 6. 为什么不装第三方 futu skill

已排查（2026-09-01）clawhub 与 skills.sh：

| 候选 | 安装量 | 结论 |
|---|---|---|
| `futu-trading-bot` | 1 | 第三方个人作品，交易机器人非数据源，**不装** |
| `futu-flash` | 0 | 同上，**不装** |
| `opend`（OpenD CLI for MooMoo） | 0 | 只是 OpenD 的命令行封装，不提供额外能力，**不装** |
| `moomoo-trading` | 0 | 第三方交易脚本，**不装** |

**富途官方没有发布 skill**，但发布了**官方 Python SDK `futu-api`**（PyPI 可装，当前 10.10.7008）。用官方 SDK 自建适配层比装 0 安装的第三方作品更可控：无供应链风险、接口可审计、降级行为自己掌握。

---

## References

[1] FutuAPI（富途官方）. (2026). 《futu-api Python SDK》. 官方行情/交易 SDK，PyPI 包名 futu-api，当前版本 10.10.7008；核心模块 `futu.quote`（行情）、`futu.trade`（交易）；主要接口含 `get_market_snapshot`、`get_daily_short_volume`、`get_short_interest`、`get_short_selling_rank`、`get_capital_distribution`、`get_capital_flow`、`get_rt_ticker`、`get_order_book`、`get_stock_basicinfo`、`get_shareholders_institutional`、`get_insider_trade_list`、`get_financials_statements`、`get_owner_plate`. https://pypi.org/project/futu-api/ · L1

[2] 富途开放接口. (2026). 《OpenD 接入说明》. OpenAPI 需本地常驻运行 OpenD 网关客户端并登录实盘账户，默认监听 127.0.0.1:11111；高级行情（LV2、深度盘口、期权链）需资产门槛或订阅. https://openapi.futunn.com/ · L1

[3] 本地实测. (2026-09-01). futu-api 10.10.7008 安装与连接测试：`pip install futu-api` 成功；未运行 OpenD 时 `OpenQuoteContext` 会无限重连（实测 19 次以上不退出），故 `scripts/futu_quote.py` 在构造连接前先做 1 秒 socket 端口探测，不可用时 0.039 秒返回退出码 3. · L1
