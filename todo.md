# Fiber 测试用例 Framework 适配重构清单

> **适配目标**：使所有测试用例符合 AGENTS.md 中定义的框架规范，包括：
> - 使用语义化常量（`Amount`、`Timeout`、`ChannelState`、`PaymentStatus` 等）
> - 使用断言辅助函数（`assert_payment_success`、`assert_channel_state` 等）
> - 遵循注释规范（类 docstring、方法 docstring 含 Step、行内注释）
> - 使用智能等待工具（`wait_payment_state`、`wait_for_channel_state` 等）
> - 避免硬编码魔法数字
> - 所有代码和注释使用英文

---

## 1. abandon_channel (1 个文件)

- [x] `test_cases/fiber/devnet/abandon_channel/test_abandon_channel.py`

---

## 2. accept_channel (9 个文件)

- [x] `test_cases/fiber/devnet/accept_channel/test_accepct_mutil_channels_same_time.py`
- [x] `test_cases/fiber/devnet/accept_channel/test_funding_amount.py`
- [x] `test_cases/fiber/devnet/accept_channel/test_max_tlc_number_in_flight_debug.py`
- [x] `test_cases/fiber/devnet/accept_channel/test_max_tlc_value_in_flight.py`
- [x] `test_cases/fiber/devnet/accept_channel/test_shutdown_script.py`
- [x] `test_cases/fiber/devnet/accept_channel/test_temporary_channel_id.py`
- [x] `test_cases/fiber/devnet/accept_channel/test_tlc_expiry_delta.py`
- [x] `test_cases/fiber/devnet/accept_channel/test_tlc_fee_proportional_millionths.py`
- [x] `test_cases/fiber/devnet/accept_channel/test_tlc_min_value.py`

---

## 3. add_tlc (1 个文件)

- [x] `test_cases/fiber/devnet/add_tlc/test_add_tlc.py`

---

## 4. backup (1 个文件)

- [x] `test_cases/fiber/devnet/backup/test_backup.py`

---

## 5. build_router (1 个文件)

- [x] `test_cases/fiber/devnet/build_router/test_build_router.py`

---

## 6. cancel_invoice (1 个文件)

- [x] `test_cases/fiber/devnet/cancel_invoice/test_cancel_invoice.py`

---

## 7. ckb (3 个文件)

- [x] `test_cases/fiber/devnet/ckb/test_ckb_remove_tx.py`
- [x] `test_cases/fiber/devnet/ckb/test_ckb_send_cell.py`
- [x] `test_cases/fiber/devnet/ckb/test_ckb_stop.py`

---

## 8. compatibility (2 个文件)

- [x] `test_cases/fiber/devnet/compatibility/test_data.py`
- [x] `test_cases/fiber/devnet/compatibility/test_p2p.py`

---

## 9. connect_peer (1 个文件)

- [x] `test_cases/fiber/devnet/connect_peer/test_connect_peer.py`

---

## 10. disconnect_peer (1 个文件)

- [x] `test_cases/fiber/devnet/disconnect_peer/test_disconnect_peer.py`

---

## 11. get_invoice (1 个文件)

- [x] `test_cases/fiber/devnet/get_invoice/test_get_invoice.py`

---

## 12. graph_channels (1 个文件)

- [x] `test_cases/fiber/devnet/graph_channels/test_graph_channels.py`

---

## 13. graph_nodes (1 个文件)

- [x] `test_cases/fiber/devnet/graph_nodes/test_graph_nodes.py`

---

## 14. issue (8 个文件)

- [x] `test_cases/fiber/devnet/issue/test_force_stop.py`
- [x] `test_cases/fiber/devnet/issue/test_issue_1069.py`
- [x] `test_cases/fiber/devnet/issue/test_issue_446.py`
- [x] `test_cases/fiber/devnet/issue/test_issue_478.py`
- [x] `test_cases/fiber/devnet/issue/test_issue_484.py`
- [x] `test_cases/fiber/devnet/issue/test_issue_640.py`
- [x] `test_cases/fiber/devnet/issue/test_issue_670.py`
- [x] `test_cases/fiber/devnet/issue/test_issue_675.py`

---

## 15. list_channels (1 个文件)

- [x] `test_cases/fiber/devnet/list_channels/test_list_channels.py`

---

## 16. list_peers (1 个文件)

- [x] `test_cases/fiber/devnet/list_peers/test_list_peers.py`

---

## 17. mutil_sig (1 个文件)

- [x] `test_cases/fiber/devnet/mutil_sig/test_mutil_sig.py`

---

## 18. new_invoice (10 个文件)

- [x] `test_cases/fiber/devnet/new_invoice/test_amount.py`
- [x] `test_cases/fiber/devnet/new_invoice/test_currency.py`
- [x] `test_cases/fiber/devnet/new_invoice/test_description.py`
- [x] `test_cases/fiber/devnet/new_invoice/test_expiry.py`
- [x] `test_cases/fiber/devnet/new_invoice/test_fallback_address.py`
- [x] `test_cases/fiber/devnet/new_invoice/test_final_expiry_delta.py`
- [x] `test_cases/fiber/devnet/new_invoice/test_hash_algorithm.py`
- [x] `test_cases/fiber/devnet/new_invoice/test_invoice_cost.py`
- [x] `test_cases/fiber/devnet/new_invoice/test_payment_preimage.py`
- [x] `test_cases/fiber/devnet/new_invoice/test_udt_type_script.py`

---

## 19. node_info (1 个文件)

- [x] `test_cases/fiber/devnet/node_info/test_node_info.py`

---

## 20. one_way (3 个文件)

- [x] `test_cases/fiber/devnet/one_way/test_hash.py`
- [x] `test_cases/fiber/devnet/one_way/test_oneway_channel.py`
- [x] `test_cases/fiber/devnet/one_way/test_wath_tower.py`

---

## 21. open_channel (19 个文件)

- [x] `test_cases/fiber/devnet/open_channel/test_ckb_cell.py`
- [x] `test_cases/fiber/devnet/open_channel/test_commitment_delay_epoch.py`
- [x] `test_cases/fiber/devnet/open_channel/test_commitment_fee_rate.py`
- [x] `test_cases/fiber/devnet/open_channel/test_force_restart.py`
- [x] `test_cases/fiber/devnet/open_channel/test_funding_amount.py`
- [x] `test_cases/fiber/devnet/open_channel/test_funding_fee_rate.py`
- [x] `test_cases/fiber/devnet/open_channel/test_funding_timeout.py`
- [x] `test_cases/fiber/devnet/open_channel/test_funding_udt_type_script.py`
- [x] `test_cases/fiber/devnet/open_channel/test_linked.py`
- [x] `test_cases/fiber/devnet/open_channel/test_max_tlc_number_in_flight.py`
- [x] `test_cases/fiber/devnet/open_channel/test_max_tlc_value_in_flight.py`
- [x] `test_cases/fiber/devnet/open_channel/test_n_user.py`
- [x] `test_cases/fiber/devnet/open_channel/test_public.py`
- [x] `test_cases/fiber/devnet/open_channel/test_restart.py`
- [x] `test_cases/fiber/devnet/open_channel/test_shutdown_script.py`
- [x] `test_cases/fiber/devnet/open_channel/test_tlc_expiry_delta.py`
- [x] `test_cases/fiber/devnet/open_channel/test_tlc_fee_proportional_millionths.py`
- [x] `test_cases/fiber/devnet/open_channel/test_tlc_max_value.py`
- [x] `test_cases/fiber/devnet/open_channel/test_tlc_min_value.py`

---

## 22. open_channel_debug (1 个文件)

- [x] `test_cases/fiber/devnet/open_channel_debug/test_max_tlc_number_in_flight_debug.py`

---

## 23. password (1 个文件)

- [x] `test_cases/fiber/devnet/password/test_wrong_password.py`

---

## 24. remove_tlc (1 个文件)

- [x] `test_cases/fiber/devnet/remove_tlc/test_remove_tlc.py`

---

## 25. send_payment (36 个文件)

### 25.1 send_payment/atomic_mpp (6 个文件)

- [x] `test_cases/fiber/devnet/send_payment/atomic_mpp/test_dup_invoice.py`
- [x] `test_cases/fiber/devnet/send_payment/atomic_mpp/test_hash_algorithm.py`
- [x] `test_cases/fiber/devnet/send_payment/atomic_mpp/test_mutil_node_payment.py`
- [x] `test_cases/fiber/devnet/send_payment/atomic_mpp/test_mutil_path.py`
- [x] `test_cases/fiber/devnet/send_payment/atomic_mpp/test_new_invoice.py`
- [x] `test_cases/fiber/devnet/send_payment/atomic_mpp/test_watch_tower.py`

### 25.2 send_payment/debug (1 个文件)

- [x] `test_cases/fiber/devnet/send_payment/debug/test_with_debug.py`

### 25.3 send_payment/mixed (1 个文件)

- [x] `test_cases/fiber/devnet/send_payment/mixed/test_ckb_with_udt.py`

### 25.4 send_payment/module (3 个文件)

- [x] `test_cases/fiber/devnet/send_payment/module/test_send_payment.py`
- [x] `test_cases/fiber/devnet/send_payment/module/test_send_payment_with_shutdown.py`
- [x] `test_cases/fiber/devnet/send_payment/module/test_send_payment_with_update_channel.py`

### 25.5 send_payment/mpp (7 个文件)

- [ ] `test_cases/fiber/devnet/send_payment/mpp/test_demo.py`
- [ ] `test_cases/fiber/devnet/send_payment/mpp/test_hold_invoice_with_shutdown.py`
- [ ] `test_cases/fiber/devnet/send_payment/mpp/test_mpp_bench.py`
- [ ] `test_cases/fiber/devnet/send_payment/mpp/test_mpp_force_shutdown.py`
- [ ] `test_cases/fiber/devnet/send_payment/mpp/test_mpp_with_hash_algorithm.py`
- [ ] `test_cases/fiber/devnet/send_payment/mpp/test_mpp_with_watch_tower.py`
- [ ] `test_cases/fiber/devnet/send_payment/mpp/test_mutil_path.py`

### 25.6 send_payment/offline (6 个文件)

- [ ] `test_cases/fiber/devnet/send_payment/offline/test_disconnect.py`
- [ ] `test_cases/fiber/devnet/send_payment/offline/test_disconnect1.py`
- [ ] `test_cases/fiber/devnet/send_payment/offline/test_force_restart.py`
- [ ] `test_cases/fiber/devnet/send_payment/offline/test_restart.py`
- [ ] `test_cases/fiber/devnet/send_payment/offline/test_send_payment_with_stop.py`
- [ ] `test_cases/fiber/devnet/send_payment/offline/test_stop_mid_node.py`

### 25.7 send_payment/other_tlc (1 个文件)

- [ ] `test_cases/fiber/devnet/send_payment/other_tlc/test_other_tlc.py`

### 25.8 send_payment/params (14 个文件)

- [ ] `test_cases/fiber/devnet/send_payment/params/test_allow_self_payment.py`
- [ ] `test_cases/fiber/devnet/send_payment/params/test_amount.py`
- [ ] `test_cases/fiber/devnet/send_payment/params/test_custom_records.py`
- [ ] `test_cases/fiber/devnet/send_payment/params/test_dry_run.py`
- [ ] `test_cases/fiber/devnet/send_payment/params/test_fee.py`
- [ ] `test_cases/fiber/devnet/send_payment/params/test_final_tlc_expiry_delta.py`
- [ ] `test_cases/fiber/devnet/send_payment/params/test_hophint.py`
- [ ] `test_cases/fiber/devnet/send_payment/params/test_max_fee_amount.py`
- [ ] `test_cases/fiber/devnet/send_payment/params/test_max_parts.py`
- [ ] `test_cases/fiber/devnet/send_payment/params/test_payment_hash.py`
- [ ] `test_cases/fiber/devnet/send_payment/params/test_timeout.py`
- [ ] `test_cases/fiber/devnet/send_payment/params/test_tlc_expiry_limit.py`
- [ ] `test_cases/fiber/devnet/send_payment/params/test_tlc_fee.py`
- [ ] `test_cases/fiber/devnet/send_payment/params/test_used_preimage.py`

### 25.9 send_payment/path (4 个文件)

- [ ] `test_cases/fiber/devnet/send_payment/path/test_find_path.py`
- [ ] `test_cases/fiber/devnet/send_payment/path/test_long_router.py`
- [ ] `test_cases/fiber/devnet/send_payment/path/test_mutil_channel.py`
- [ ] `test_cases/fiber/devnet/send_payment/path/test_private_channel.py`

### 25.10 send_payment (根目录, 1 个文件)

- [ ] `test_cases/fiber/devnet/send_payment/test_01.py`

---

## 26. send_payment_with_router (1 个文件)

- [ ] `test_cases/fiber/devnet/send_payment_with_router/test_send_payment_with_router.py`

---

## 27. settle_invoice (3 个文件)

- [ ] `test_cases/fiber/devnet/settle_invoice/test_batch_settle.py`
- [ ] `test_cases/fiber/devnet/settle_invoice/test_mpp.py`
- [ ] `test_cases/fiber/devnet/settle_invoice/test_settle_invoice.py`

---

## 28. shutdown_channel (10 个文件)

- [ ] `test_cases/fiber/devnet/shutdown_channel/test_channel_id.py`
- [ ] `test_cases/fiber/devnet/shutdown_channel/test_close_script.py`
- [ ] `test_cases/fiber/devnet/shutdown_channel/test_fee_rate.py`
- [ ] `test_cases/fiber/devnet/shutdown_channel/test_force.py`
- [ ] `test_cases/fiber/devnet/shutdown_channel/test_force_restart.py`
- [ ] `test_cases/fiber/devnet/shutdown_channel/test_mutil_to_one.py`
- [ ] `test_cases/fiber/devnet/shutdown_channel/test_node_state.py`
- [ ] `test_cases/fiber/devnet/shutdown_channel/test_pending_tlc.py`
- [ ] `test_cases/fiber/devnet/shutdown_channel/test_restart.py`
- [ ] `test_cases/fiber/devnet/shutdown_channel/test_shutdown_channel.py`

---

## 29. spike_stress (1 个文件)

- [ ] `test_cases/fiber/devnet/spike_stress/test_spike_impact.py`

---

## 30. stable (1 个文件)

- [ ] `test_cases/fiber/devnet/stable/test_stable.py`

---

## 31. tlc_timeout (1 个文件)

- [ ] `test_cases/fiber/devnet/tlc_timeout/test_tlc_timeout.py`

---

## 32. trampoline_routing (13 个文件)

- [ ] `test_cases/fiber/devnet/trampoline_routing/test_allowTramponlieRouting.py`
- [ ] `test_cases/fiber/devnet/trampoline_routing/test_boundary_values.py`
- [ ] `test_cases/fiber/devnet/trampoline_routing/test_complex_routing.py`
- [ ] `test_cases/fiber/devnet/trampoline_routing/test_concurrent_payments.py`
- [ ] `test_cases/fiber/devnet/trampoline_routing/test_error_scenarios.py`
- [ ] `test_cases/fiber/devnet/trampoline_routing/test_fee_rate.py`
- [ ] `test_cases/fiber/devnet/trampoline_routing/test_hash_algorithm.py`
- [ ] `test_cases/fiber/devnet/trampoline_routing/test_mid_node_one_way.py`
- [ ] `test_cases/fiber/devnet/trampoline_routing/test_mpp.py`
- [ ] `test_cases/fiber/devnet/trampoline_routing/test_multi_hop.py`
- [ ] `test_cases/fiber/devnet/trampoline_routing/test_new_invoice.py`
- [ ] `test_cases/fiber/devnet/trampoline_routing/test_private_channel.py`
- [ ] `test_cases/fiber/devnet/trampoline_routing/test_router.py`

---

## 33. update_channel (7 个文件)

- [ ] `test_cases/fiber/devnet/update_channel/test_chain_status.py`
- [ ] `test_cases/fiber/devnet/update_channel/test_channel_id.py`
- [ ] `test_cases/fiber/devnet/update_channel/test_enabled.py`
- [ ] `test_cases/fiber/devnet/update_channel/test_tlc_expiry_delta.py`
- [ ] `test_cases/fiber/devnet/update_channel/test_tlc_fee_proportional_millionths.py`
- [ ] `test_cases/fiber/devnet/update_channel/test_tlc_minimum_value.py`
- [ ] `test_cases/fiber/devnet/update_channel/test_update_channel.py`

---

## 34. wasm (8 个文件)

- [ ] `test_cases/fiber/devnet/wasm/test_connect_peer.py`
- [ ] `test_cases/fiber/devnet/wasm/test_one_way_and_trampoline_routing.py`
- [ ] `test_cases/fiber/devnet/wasm/test_wasm.py`
- [ ] `test_cases/fiber/devnet/wasm/test_wasm_bench.py`
- [ ] `test_cases/fiber/devnet/wasm/test_wasm_demo.py`
- [ ] `test_cases/fiber/devnet/wasm/test_wasm_mutil.py`
- [ ] `test_cases/fiber/devnet/wasm/test_wasm_rpc.py`
- [ ] `test_cases/fiber/devnet/wasm/test_wasm_watch_tower.py`

---

## 35. watch_tower (6 个文件)

- [x] `test_cases/fiber/devnet/watch_tower/test_hash_algorithm.py`
- [x] `test_cases/fiber/devnet/watch_tower/test_htlc_mutil.py`
- [x] `test_cases/fiber/devnet/watch_tower/test_mutil_shutdown.py`
- [x] `test_cases/fiber/devnet/watch_tower/test_revert_tx.py`
- [x] `test_cases/fiber/devnet/watch_tower/test_watch_tower.py`
- [x] `test_cases/fiber/devnet/watch_tower/test_watch_tower_udt.py`

---

## 36. watch_tower_debug (1 个文件)

- [ ] `test_cases/fiber/devnet/watch_tower_debug/test_htlc_expired.py`

---

## 37. watch_tower_wit_tlc (6 个文件)

- [ ] `test_cases/fiber/devnet/watch_tower_wit_tlc/test_discard.py`
- [ ] `test_cases/fiber/devnet/watch_tower_wit_tlc/test_mutil_to_one.py`
- [ ] `test_cases/fiber/devnet/watch_tower_wit_tlc/test_one_to_one.py`
- [ ] `test_cases/fiber/devnet/watch_tower_wit_tlc/test_pending_tlc_handle.py`
- [ ] `test_cases/fiber/devnet/watch_tower_wit_tlc/test_pending_tlc_handle_udt.py`
- [ ] `test_cases/fiber/devnet/watch_tower_wit_tlc/test_shutdown_mid_node.py`

---

## 38. 根目录文件 (2 个文件)

- [ ] `test_cases/fiber/devnet/test_deploy.py`
- [ ] `test_cases/fiber/devnet/test_fiber_demo.py`

---

## 统计信息

| 分类 | 文件数 |
|------|--------|
| abandon_channel | 1 |
| accept_channel | 9 |
| add_tlc | 1 |
| backup | 1 |
| build_router | 1 |
| cancel_invoice | 1 |
| ckb | 3 |
| compatibility | 2 |
| connect_peer | 1 |
| disconnect_peer | 1 |
| get_invoice | 1 |
| graph_channels | 1 |
| graph_nodes | 1 |
| issue | 8 |
| list_channels | 1 |
| list_peers | 1 |
| mutil_sig | 1 |
| new_invoice | 10 |
| node_info | 1 |
| one_way | 3 |
| open_channel | 19 |
| open_channel_debug | 1 |
| password | 1 |
| remove_tlc | 1 |
| send_payment | 36 |
| send_payment_with_router | 1 |
| settle_invoice | 3 |
| shutdown_channel | 10 |
| spike_stress | 1 |
| stable | 1 |
| tlc_timeout | 1 |
| trampoline_routing | 13 |
| update_channel | 7 |
| wasm | 8 |
| watch_tower | 6 |
| watch_tower_debug | 1 |
| watch_tower_wit_tlc | 6 |
| 根目录 | 2 |
| **总计** | **163** |

---

## 适配检查清单（每个文件适配时参照）

适配每个测试文件时，请确认以下事项：

### 1. 常量使用
- [ ] 金额使用 `Amount.ckb()` / `Amount.udt()` 而非硬编码
- [ ] 超时使用 `Timeout.XXX` 常量
- [ ] 通道状态使用 `ChannelState.XXX`
- [ ] 支付状态使用 `PaymentStatus.XXX`
- [ ] 发票状态使用 `InvoiceStatus.XXX`
- [ ] 费率使用 `FeeRate.XXX` / `TLCFeeRate.XXX` / `PaymentFeeRate.XXX`

### 2. 注释规范
- [ ] 类有 docstring（说明测试目标、需求来源）
- [ ] 方法有 docstring（含 Step 1、Step 2...）
- [ ] 代码按 Step 分段，每段有 `# Step N:` 注释
- [ ] 关键逻辑有行内注释
- [ ] 所有注释使用英文

### 3. 等待与断言
- [ ] 使用 `wait_payment_state()` 而非 `time.sleep()`
- [ ] 使用 `wait_for_channel_state()` 等待通道状态
- [ ] 使用断言辅助函数（如 `assert_payment_success()`）

### 4. 基类选择
- [ ] 简单用例继承 `FiberTest`
- [ ] 共享拓扑用例继承 `SharedFiberTest`

---

## 进度追踪

- 总文件数: 163
- 已适配: 0
- 进度: 0%

> 最后更新: 2026-01-28
