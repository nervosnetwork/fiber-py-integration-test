# PR #122 测试覆盖复审

评审日期：2026-11-11，本轮在本地已有草稿上继续复核。结论：**建议修改后再合并。现有测试有回归价值，但尚不足以支持“这些 Fiber PR 已获得充分专项覆盖”的整体声明。** 最需要处理的是 #1709 的判断依据、#1718 的通知完整性断言，以及 #1707 遗漏的重启场景。

本报告是评审意见，不新增或修改行为用例行。后续涉及场景、预期或优先级的实质变更，仍按仓库 `AGENTS.md` 先展示完整行集并等待用户确认。

## 当前复审结论：未通过，不能据此合并

本次同时审查 PR 已提交内容和本地暂存、未暂存改动。本地五个文件的变化是四组文件/类的功能命名，以及 `test_store_sync_writes.py` 的格式调整；相对 base 的工作区差异仍为 12 个文件、1017 行新增。格式与重命名未发现新的行为问题，可以作为中间 commit 保存，但整份 PR 的 review 结论仍是 **Request changes**。

阻止本次批准的内容没有消失：F2 的通知完整性断言、F3 的线程异常传播仍有确定缺陷；F1 的表格、Spec 和测试说明仍声称能构造专项重放窗口；F4 缺少已讨论的入池后重启变体。F5/F6 的场景和证据声明也尚未对齐。不能用“文件已改名、格式已整理、测试可收集”替代这些修复。

本次新增两项离线评审验证，均直接调用当前测试代码，退出 0；详细命令见下文。这些是测试代码的缺陷验证，不是节点或完整 pytest 执行结果：

- F2：只提供 160 个普通发票 Open 事件和 1 个 marker Open 事件，缺少全部 160 个 Preimage 事件，原测试方法仍正常返回。
- F3：16 个 worker 各自在首次模拟 RPC 调用时失败，主线程没有收到异常，辅助函数仍返回 160；实际仅发生 16 次失败尝试，不能说完成了 160 次 RPC。

重新提交后应复核最终用例与所有映射断言，并取得聚焦节点测试和新提交的格式检查结果。六个基线既有孤儿映射不作为本 PR 新增阻断，也不要求跨范围修复。

## 评审范围与证据边界

- 测试 PR：[nervosnetwork/fiber-py-integration-test #122](https://github.com/nervosnetwork/fiber-py-integration-test/pull/122)。GitHub 与本地 HEAD 均为 `0712733a41fa3cac5e60bf118457c26ddfaf7fb2`；目标分支 `v0.10.0`，基准及本地 merge-base 为 `1c484fea7e2e55d91946fcc9247ff0a7bd3f4e5e`。变更为 12 个文件、1019 行新增，包含 10 条新增测试。
- 逐一核对了五份行为评审、全部 10 条新增测试、相关框架方法、映射、已有反馈及 CI 入口；本轮另由三个独立复核代理分别检查 hold-set、store 订阅及 funding/config。对 #1707、#1708、#1709、#1718 的关键证据重新从 GitHub 固定提交读取，未将无版本来源的本地临时源码当作唯一依据。
- 上游源码按固定提交阅读：[#1703](https://github.com/nervosnetwork/fiber/pull/1703) `043b83a5655e2629321d80fc2ed58dd271ca69e4`；[#1707](https://github.com/nervosnetwork/fiber/pull/1707) `2a2b7ee453907cdf530b4edb59c5aea8fb075f72`；[#1708](https://github.com/nervosnetwork/fiber/pull/1708) `d6b63fcd27e4fad1504d3b209e7fbe8bd1152573`；[#1709](https://github.com/nervosnetwork/fiber/pull/1709) `913f4e5af438418756f124bc1a8be5c96695e149`；[#1718](https://github.com/nervosnetwork/fiber/pull/1718) `ba178249186b5afde606c813aa854f1b952525b7`；[#1719](https://github.com/nervosnetwork/fiber/pull/1719) `5044ef33b083d367eeda8d0dc1c7ce44e7cdba66`。
- 本轮重新读取 GitHub PR 元数据，确认本地与远端 head/base 一致，再核对源码与测试、收集、映射和 diff；未启动节点，未重新执行 rc1/rc2 对照。PR 和已有评审中的运行结果属于作者已有记录，本报告不将其记作本轮执行通过。源码推导的漏检路径也不冒充已运行的反例。原稿记录的 CI 日志与本轮读取的 check 状态分别标注。

## 各 PR 当前能证明什么

| Fiber PR | 当前测试的价值 | 覆盖判断与处理 |
| --- | --- | --- |
| #1703 | yml、默认值、env 三个入口的日志声明；开启后开通道、付款、重启与余额保持 | 在已人工确认的黑盒功能范围内合理。不能证明真实断电耐久；这是已接受的边界，不作为阻断缺陷。 |
| #1707 | 真实旧承诺攻击、Watchtower 交易在池中时发起 funding；比较输入、确认两笔交易及通道 Ready | 核心事故场景有价值；最终合并版本涉及的“池内交易跨节点重启”场景遗漏，见 F4。 |
| #1708 | 两端 CKB RPC 边界注入 -1111，检查有界失败与失败后重新开通道 | 对 funding 错误处理的判断直接，作者已有旧版失败/新版通过记录；代理注入与真实池竞争的证明层次需写清。 |
| #1709 | MPP hold 发票在收款方崩溃、付款方停机或断连后的恢复 | 可保留为恢复回归；当前构造和终态判断不能证明能拒绝 #1709 的已知回归，见 F1。 |
| #1718 | 并发开发票后订阅仍能收到标记事件；另一客户端断开后的存活 | 可保留一般订阅回归；完整性、异常传播与覆盖声明需要修正，见 F2、F3、F5、F6。 |
| #1719 | 没有新增性能测试，计划复用既有 Watchtower 功能套件 | 符合本工程功能回归定位；无需为本次强加规模压测。功能套件不能证明性能收益，且本 PR 当前没有该套件的运行结果。 |

## 需要处理的评审意见

### F1 · P1：#1709 的终态判断不能验证实际修复，SIGKILL 也未保证构造目标窗口

位置：[测试第 44 行](/Users/sunchengzhu/project/fiber-py-integration-test/test_cases/fiber/devnet/settle_invoice/test_mpp_hold_settle_replay_after_crash.py:44)、[第 53 行](/Users/sunchengzhu/project/fiber-py-integration-test/test_cases/fiber/devnet/settle_invoice/test_mpp_hold_settle_replay_after_crash.py:53)；第二条测试的第 88、96 行存在相同问题。涉及 `PR1709-01/02`。

上游回归测试通过内部状态设置构造等待 ack，在 durable fulfill 已排队、hold 已清空后，手工重新插入 hold 记录并重放结算；其失败点与判断依据是 hold 存储及时清空、队列不重复。它并没有证明付款最终一定失败；后续还手工将发票设为 Paid。[上游原始回归](https://github.com/nervosnetwork/fiber/blob/913f4e5af438418756f124bc1a8be5c96695e149/crates/fiber-lib/src/fiber/tests/mpp.rs#L4022)

源码存在以下漏检路径：两条 fulfill 已持久化入队、hold 记录尚未清理；旧谓词导致这一轮重放找不到上下文；恢复连接后，原 durable queue 仍直接调用 `handle_remove_tlc_command` 继续结算，不经过本 PR 修改的谓词。该处理会自行删除 hold，之后兑现又会把发票设为 Paid。因此当前 `Success + Paid + TLC 余额归零` 仍可能全部成立。[队列执行](https://github.com/nervosnetwork/fiber/blob/913f4e5af438418756f124bc1a8be5c96695e149/crates/fiber-lib/src/fiber/channel.rs#L2537)、[remove 清理 hold](https://github.com/nervosnetwork/fiber/blob/913f4e5af438418756f124bc1a8be5c96695e149/crates/fiber-lib/src/fiber/channel.rs#L2198)、[兑现更新 Paid](https://github.com/nervosnetwork/fiber/blob/913f4e5af438418756f124bc1a8be5c96695e149/crates/fiber-lib/src/fiber/channel.rs#L1929)

构造本身还有第二层不确定性：`settle_invoice` 写入原像并投递异步结算命令后即可返回。紧接着调用 `force_stop()`，不能保证崩溃恰好落在“fulfill 已入队、hold 未删”之间；Received 只证明款项到齐。已有日志能证明某一次运行触发过重放，不能替代持续回归所需的稳定前提和有效判断。[异步结算入口](https://github.com/nervosnetwork/fiber/blob/913f4e5af438418756f124bc1a8be5c96695e149/crates/fiber-lib/src/fiber/network.rs#L4461)

**处理要求：**先修正“旧版一定永远卡住、当前已专项覆盖 #1709”的结论。可以将这两条保留为 MPP hold 崩溃恢复回归。若继续声明专项覆盖，需先给出公开接口和运维操作可稳定构造、且能拒绝有效 buggy baseline 的外部判断；做不到就明确专项交接行为由上游测试负责。不要通过内部 DB 修改、内部钩子或精确控制 actor 时序强行构造。

当前[用例行](/Users/sunchengzhu/project/fiber-py-integration-test/reviews/pr1709-hold-set-replay.md:30)仍把 SIGKILL 说成“打断交接”、把重启说成必然“触发重放”。表外收窄时也应同步这些行内前提、Spec 和测试说明；保持公开操作与 Success/Paid/pending TLC 归零的终态断言即可。仅修改标题无法关闭 F1。

这里证明的是静态上存在漏检路径，本轮没有运行 buggy 二进制证明当前两条必然通过；也不能将所有 hold 记录残留一概解释成用户资金永久卡死。

### F2 · P1：#1718 的总数断言会放过整类通知丢失，也未检查唯一性或顺序

位置：[测试第 110 行](/Users/sunchengzhu/project/fiber-py-integration-test/test_cases/fiber/devnet/issue/test_store_change_subscription_burst.py:110)、[第 131 行](/Users/sunchengzhu/project/fiber-py-integration-test/test_cases/fiber/devnet/issue/test_store_change_subscription_burst.py:131)。涉及 `PR1718-01/02`。

普通突发发票未传 hash/preimage，节点会自动生成原像，并发出 `PutCkbInvoiceStatus(Open)` 和 `PutPreimage` 两条通知；hash-only marker 只发出状态通知。本批相关通知应为 `160 × 2 + 1 = 321` 条，当前却只要求总数至少 161，且任意一条包含 marker hash。[默认生成原像](https://github.com/nervosnetwork/fiber/blob/ba178249186b5afde606c813aa854f1b952525b7/crates/fiber-lib/src/rpc/invoice.rs#L187)、[通知生成](https://github.com/nervosnetwork/fiber/blob/ba178249186b5afde606c813aa854f1b952525b7/crates/fiber-lib/src/store/store_impl/mod.rs#L1360)

例如全部 160 条 `PutPreimage` 丢失，仅剩 160 个 Open 和 1 个 marker，当前断言仍能接受。本次通过下文离线探针直接调用原测试方法，已复现这个判断缺陷；未运行节点或完整 pytest。重复事件也能抵消缺失，当前代码完全不检查顺序。这与 SPEC 的“每条变更都按序到达”不一致。

**处理要求：**保存每次成功 RPC 的 payment_hash，解析事件类型及 hash，核对完整集合和唯一性；校验每张发票的 Open 先于其自身 Preimage，本批突发事件先于事后 marker。16 个线程之间没有独立可观测的全局提交顺序，不要按线程编号或 HTTP 返回顺序强加全局排序。断言应针对本批相关事件，避免后台无关通知污染计数。

### F3 · P1：#1718 的工作线程失败不会可靠地使测试失败

位置：[测试第 64 行](/Users/sunchengzhu/project/fiber-py-integration-test/test_cases/fiber/devnet/issue/test_store_change_subscription_burst.py:64)。涉及 `PR1718-01/02`。

线程中执行 RPC，主线程只 `join()`，随后固定返回 160。它没有收集成功结果，也不传播线程异常；仓库配置未将未处理线程异常警告设为错误。结合每张普通发票会发出两条通知的事实，只有 80 张成功、其余请求失败时，也可能凑够当前 161 条门槛。

本次离线调用该辅助函数：16 个 worker 各自的首次模拟 RPC 全部报错，结果为 `reported_invoice_count=160; successful_rpc_calls=0; worker_failures=16; main_thread_exception=False`。这证明辅助函数隐藏错误；不声称没有通知时完整测试也会通过。

**处理要求：**使用 `ThreadPoolExecutor` 并读取所有 `future.result()`，或显式收集异常；把所有预期请求成功、成功 hash 数量正确作为前提。仅修改总数门槛不足以解决生成过程失败被隐藏的问题。

### F4 · P1：#1707 遗漏最终合并版本涉及的“交易在池时节点重启”场景

位置：[测试第 73 行](/Users/sunchengzhu/project/fiber-py-integration-test/test_cases/fiber/devnet/watch_tower/test_funding_skips_watchtower_pool_cells.py:73)。当前 `PR1707-01` 在 Watchtower 交易入池之前启动 fiber2，入池后直接开新通道。

上游最终合并版本不只增加进程内 held-cells，还为内存预留在重启后丢失、以及同密钥其他进程已发送交易的情况，增加 `get_live_cell(include_tx_pool=true)` 检查。这是实际部署差异；当前用例没有覆盖入池之后的重启。[上游修复说明](https://github.com/nervosnetwork/fiber/pull/1707#issuecomment-6531870232)

**建议补充的行为：**停矿使 Watchtower 交易保持 pending；交易入池后停启 fiber2；重新确认原交易仍 pending；从同一账户向健康的 fiber3 开新通道；检查输入无交集、两交易上链、新通道 Ready。这个变体只依赖公开查询、进程启停和挖矿控制，不需要精确竞态。先形成新增评审行，确认后再实现。

现有用例能证明池内冲突得到规避，不能单独证明进程内预留与池占用检查两套机制都正确；两者是不同部署条件下的保护，不必为了区分机制引入内部测试。

### F5 · P2：#1718 第二条的操作与评审行不一致，且不能覆盖停止 actor 清理

位置：[测试第 126 行](/Users/sunchengzhu/project/fiber-py-integration-test/test_cases/fiber/devnet/issue/test_store_change_subscription_burst.py:126)；[评审第 29 行](/Users/sunchengzhu/project/fiber-py-integration-test/reviews/pr1718-store-change-burst.md:29)。

代码等全部突发请求结束后才关闭 A，之后只产生一个 marker；虽然仍可能有通知在途，但没有保证关闭发生在评审所写的“突发期间”。两个 WS 客户端还是同一个 `PubSubServerActor` 的两个 sink，关闭 A 不会停止该共享 actor。PR 新增 `StoreChangePort` 清理针对停止的 actor，因此客户端关闭测试不能证明这条内部清理路径。[共享 actor 与 sinks](https://github.com/nervosnetwork/fiber/blob/ba178249186b5afde606c813aa854f1b952525b7/crates/fiber-lib/src/rpc/pubsub.rs#L76)、[actor 投递与清理](https://github.com/nervosnetwork/fiber/blob/ba178249186b5afde606c813aa854f1b952525b7/crates/fiber-lib/src/store/store_impl/mod.rs#L532)

**处理要求：**保留有用户价值的“一个客户端断开后，另一个客户端继续完整收通知”行为；可用断开前后两批操作明确边界。将 actor 清理留给上游单元测试，修正对应 Spec 和防止的问题。若改变评审行，先走人工确认。

### F6 · P2：#1718 文档对数量、旧版表现和 actor 测试范围的声明不准确

位置：[评审第 12 行](/Users/sunchengzhu/project/fiber-py-integration-test/reviews/pr1718-store-change-burst.md:12)、[第 19 行](/Users/sunchengzhu/project/fiber-py-integration-test/reviews/pr1718-store-change-burst.md:19)、[第 28 行](/Users/sunchengzhu/project/fiber-py-integration-test/reviews/pr1718-store-change-burst.md:28)、[第 66 行](/Users/sunchengzhu/project/fiber-py-integration-test/reviews/pr1718-store-change-burst.md:66)。

文档已经记录 rc1 也通过、黑盒无法稳定触发 Lagged，接受一般契约回归定位；其他段落仍称“旧版必死”“30 条突发后订阅死亡”。公共约定和测试树写 30，场景写 160，预期写至少 31，代码要求至少 161；普通发票还不止一条通知。

文档第 13、41、67 行还把上游“101 条全收”说成 CCH actor 路径已覆盖；实际新增测试使用 `Recorder` actor，证明向 actor 投递的完整性与顺序，不能据此宣称真实 CCH 端到端链路已验证。已有 CCH actor 测试改用新 port，与这条 101 事件回归应分别说明。[上游 Recorder 测试](https://github.com/nervosnetwork/fiber/blob/ba178249186b5afde606c813aa854f1b952525b7/crates/fiber-lib/src/rpc/pubsub.rs#L105)

**处理要求：**统一实际场景与证明边界。上游进程内连续发送 101 条的结果，不能直接套到 HTTP 并发调用。无需通过不断加大线程数或请求量追逐内部调度窗口；修复 F2/F3 后，这些测试仍有一般订阅回归价值，但不应声称稳定拒绝旧版。修正 Recorder/CCH 的证据归属即可，本次不追加 CCH 压测。

## 合并前验证与非阻断建议

1. **取得新提交的格式检查结果。** 本地已经调整 `test_store_sync_writes.py` 的格式，用户报告全仓 Black 通过，本次未独立复验 Black。当前远端仍是 `0712733`，两次 `lint_and_format` 均失败；这只反映旧提交，不能据此断言本地修正仍失败。上一轮已读取的[运行日志](https://github.com/nervosnetwork/fiber-py-integration-test/actions/runs/42988844556/job/130416463691)记录需要重排该文件。提交本地修正后应取得新提交的检查结果。
2. **补足实际运行证据，准确描述 CI。** [fiber.yml 第 10 行](/Users/sunchengzhu/project/fiber-py-integration-test/.github/workflows/fiber.yml:10)只自动处理目标为 main 的 PR，而本 PR 目标为 v0.10.0。open_channel、config、settle_invoice、两个 Watchtower 目录已经有 CI 入口；问题是本 PR 没触发它们。可以对本分支手动运行相关任务或提交实际聚焦测试结果，无需仅为本次复审扩大所有 CI。不要将“已有 job 定义”写成“本 HEAD 已通过”。
3. **不要把 `make fiber_test` 当作这批 10 条测试的完整执行。** [Makefile 显式列表](/Users/sunchengzhu/project/fiber-py-integration-test/Makefile:59)不含 config 和 settle_invoice，而 CI 分别有这些入口。使用明确文件列表或对应 job；是否补齐通用 Makefile 列表应按仓库长期入口约定处理。
4. **#1707 的资金断言可补齐评审承诺。** [测试末尾](/Users/sunchengzhu/project/fiber-py-integration-test/test_cases/fiber/devnet/watch_tower/test_funding_skips_watchtower_pool_cells.py:100)没有核对维权输出归属和金额。两笔 committed 与新通道 Ready 已证明此次 cell 冲突的核心结果，因此此项降为完整性建议，优先级低于重启变体。可复用既有 `test_revert_tx.py` 的输出检查。
5. **修正过强的“无法构造”声明。** #1707 当前步骤关闭了反方向窗口，不等于证明所有公开操作都无法构造；#1708 已接受 RPC 代理，就不能再笼统称 closing/-1107 从外部无法制造。可写“当前方案未构造出稳定真实冲突”，保留范围边界；不要求为复刻上游单元测试添加新用例。
6. **保持长期回归风格。** 本地已完成四组文件/类按功能命名，稳定 Case ID 保留。补齐 skill 要求的中文步骤说明，在评审中注明耗时及有界等待，并同步行为评审里引用的旧文件路径。不要另加覆盖台账或版本专用包装。
7. **清理 #1708 的旧阶段记录。** [评审第 56 行](/Users/sunchengzhu/project/fiber-py-integration-test/reviews/pr1708-funding-pool-conflict.md:56)仍写“竞争交易已确认”，但当前代理场景没有真实竞争交易；第 66 行称 `PR1708-02` 未映射，与下一行及实际代码冲突。按最终实现整理文字即可，不需要增加真实池竞争场景。

## 本轮验证记录

| 实际命令或检查 | 关键输出 | 退出码与解释 |
| --- | --- | --- |
| `git diff origin/v0.10.0 --check` | 无输出 | 0，包含当前工作区的 diff 空白检查通过。 |
| `git diff --no-index --check /dev/null reviews/pr122-test-coverage-review.md` | 无空白错误输出 | 1，`--no-index` 比较与空文件有内容差异；不解释成格式失败，也不当作退出 0。 |
| 下列 `venv/bin/python -m pytest ... --collect-only` 命令 | `10 tests collected in 0.05s` | 0，使用重命名后的当前路径；仅收集成功，不是执行通过。 |
| `python3 scripts/check_test_map.py` | `review cases: 88`；`automated cases: 84`；`orphan mappings: PMP-01, PMP-02, PMP-03, PMP-04, PMP-05, SETTLE-01` | 1；这 6 个映射在 base 中已存在，base 的评审也没有相应行，属于基线既有问题。PR 声明 exit 0 与当前实际不符，应注明，勿跨范围修其他模块。 |
| `gh pr view 122 --repo nervosnetwork/fiber-py-integration-test --json headRefOid,baseRefOid,state,statusCheckRollup,url` | head `0712733`、base `1c484fe`；两次 `lint_and_format` 均 `FAILURE`；无 Fiber 功能测试 check | 0，读取状态成功；这些是远端旧提交的结果。 |
| 下文 F2 离线断言探针 | `existing_test_assertions_returned_normally=True; supplied_open_events=161; supplied_preimage_events=0; missing_preimage_events=160` | 0，复现现有断言接受不完整事件集；没有节点或 pytest fixture。 |
| 下文 F3 离线线程探针 | `reported_invoice_count=160; successful_rpc_calls=0; worker_failures=16; main_thread_exception=False` | 0，复现辅助函数隐藏错误；不是完整产品回归通过。 |
| 基准映射核对（命令见下） | 前者找到全部六处映射；后者无匹配行 | 分别为 0、1；核实这些孤儿关系在 base 已存在。 |

上一轮保留的记录：本地 `venv/bin/python -m black --check` 返回 `No module named black`、退出 1；属于环境依赖缺失，未实际完成格式检查。`gh run view 42988844556 --repo nervosnetwork/fiber-py-integration-test --log-failed` 返回 `1 file would be reformatted, 407 files would be left unchanged`、CI step `exit code 1`；日志读取命令本身退出 0。上一轮诊断连接器要求连接 GitHub，本次未重新读取该日志；当前远端失败状态已通过上表 PR 元数据核实。

```bash
venv/bin/python -m pytest -o addopts='' --collect-only -q \
  test_cases/fiber/config/test_store_sync_writes.py \
  test_cases/fiber/devnet/issue/test_store_change_subscription_burst.py \
  test_cases/fiber/devnet/open_channel/test_funding_pool_conflict_fails_fast.py \
  test_cases/fiber/devnet/settle_invoice/test_mpp_hold_settle_replay_after_crash.py \
  test_cases/fiber/devnet/watch_tower/test_funding_skips_watchtower_pool_cells.py
```

F2 离线断言探针（仅替换传输和准备步骤，直接执行现有测试方法的断言）：

```bash
venv/bin/python - <<'PY'
from types import SimpleNamespace
import test_cases.fiber.devnet.issue.test_store_change_subscription_burst as reviewed

marker_hash = 'review_marker_hash'
payloads = [f'PutCkbInvoiceStatus(Open): hash_{index}' for index in range(160)]
payloads.append(f'PutCkbInvoiceStatus(Open): {marker_hash}')
ws = SimpleNamespace(close=lambda: None)
reviewed.subscribe_store_changes = lambda port: (ws, 'review_subscription')
reviewed.count_notifications = lambda socket, seconds: (len(payloads), payloads)
fixture = SimpleNamespace(
    fiber1=SimpleNamespace(rpc_port=0),
    _burst_invoices=lambda: 160,
    _marker_invoice=lambda: marker_hash,
)
reviewed.TestStoreChangeSubscriptionBurst.test_subscription_survives_store_change_burst(fixture)
print('existing_test_assertions_returned_normally=True; supplied_open_events=161; supplied_preimage_events=0; missing_preimage_events=160')
print('scope=offline assertion probe with fake transport; no node or pytest fixture executed')
PY
```

F3 离线线程探针（worker 每个仅尝试一次并报错）：

```bash
venv/bin/python - <<'PY'
import threading
from types import SimpleNamespace
from test_cases.fiber.devnet.issue.test_store_change_subscription_burst import TestStoreChangeSubscriptionBurst

failures = []
def rejected_rpc(description):
    raise RuntimeError('review probe: invoice RPC failed')

fixture = SimpleNamespace(BURST_THREADS=16, BURST_PER_THREAD=10, _new_invoice=rejected_rpc)
previous_hook = threading.excepthook
threading.excepthook = lambda args: failures.append(str(args.exc_value))
try:
    reported = TestStoreChangeSubscriptionBurst._burst_invoices(fixture)
finally:
    threading.excepthook = previous_hook
print(f'reported_invoice_count={reported}; successful_rpc_calls=0; worker_failures={len(failures)}; main_thread_exception=False')
assert reported == 160 and len(failures) == 16
PY
```

```bash
git grep -n -E 'TEST-MAP: (PMP-0[1-5]|SETTLE-01)' \
  1c484fea7e2e55d91946fcc9247ff0a7bd3f4e5e -- test_cases
git grep -n -E '^\| `(PMP-0[1-5]|SETTLE-01)` \|' \
  1c484fea7e2e55d91946fcc9247ff0a7bd3f4e5e -- reviews
```

本轮仅更新原有的本报告，未修改测试或五份行为评审行，未操作现有节点。工作区原有未跟踪的 `report/`、`source/ckb-cli` 保留。本批 10 个用例 ID 均有映射；映射存在不表示断言完整或本轮执行通过。

## 对上一轮判断的修正

- 保留 #1718 计数漏检和 actor/sink 层次不一致的判断；补充了每批实际 321 条事件及线程异常问题。
- #1709 进一步发现终态判断本身不足。撤回“旧版必定资金永久卡死”的过强表述；源码可证明存在漏检路径，本轮没有有效 buggy 二进制的实测反例。
- #1707 的到账断言调整为完整性建议；把最终合并版本涉及、且可稳定黑盒构造的重启变体列为主要缺口。
- #1703 日志与功能回归范围已有人工接受，#1719 不强加性能压测；两者的证明边界应保留。
- CI 结论为“已有测试入口，本 PR 当前未触发”，并非“测试没有接入任何 CI”。

## 可直接发给 Kimi 的任务说明

```text
请基于 reviews/pr122-test-coverage-review.md 处理 PR #122。先读 AGENTS.md、reviews/review-feedback.md 和 ai-test-agent，逐条核实 F1～F6，说明接受或不接受的依据。

本次重点：
1. #1709 不能再用一次重放日志加最终 Success/Paid/TLC=0 声称专项回归已覆盖。先修正这一结论；若没有稳定的公开操作和外部判断，将现有两条定位为 MPP hold 崩溃恢复回归，说明专项交接由上游测试覆盖。请给出有效源码或旧版对照依据。
2. #1718 传播所有工作线程异常，收集所有成功发票 hash；按事件类型和 hash 检查通知完整性、唯一性，以及每张发票的局部顺序和事后 marker。普通160张加hash-only marker是321条相关事件，不能只看总数161。
3. #1718 第二条改成有明确断开前后边界的客户端互不影响场景，修正 actor 清理的覆盖声明；统一文档里的30/160/31/161及“旧版必死”等矛盾表述。上游101条全收使用Recorder actor，不能写成CCH端到端已覆盖。保留黑盒无法稳定触发 Lagged 的边界，不要靠盲目增加并发数凑反例。
4. #1707 补充 Watchtower交易已入池→停启同一节点→确认原交易仍pending→同账户开通道的稳定重启变体，验证输入不相交、两交易确认和新通道Ready。到账输出检查作为现有用例的补强。
5. 本地Black格式调整与四组功能命名已核对，可以保留；同步文档的旧路径并取得新提交的格式检查结果。清理#1708里不存在的“竞争交易已确认”和02未映射的旧阶段描述。报告当前分支实际执行的聚焦测试、映射检查和CI结果，区分基线既有孤儿映射。已有CI入口不代表本PR已经运行；make fiber_test也不包含本批所有目录。

涉及新增、删除或实质修改的用例行，先完成并展示本批完整行集，等待我明确确认后再改对应自动化；契约不变的异常传播、格式及命名等修复按现有授权推进。不要修改被测产品来让测试通过。#1703保持已接受的日志+功能范围，#1719复用功能回归，不增加本次不需要的耐久或性能压测。

最后按F1～F6逐项交接：改了什么、哪些声明被收窄、实际命令/关键输出/退出码、还存在什么覆盖边界。更新本PR的描述，使其与最终证据一致。
```
