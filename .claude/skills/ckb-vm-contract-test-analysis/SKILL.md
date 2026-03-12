---
name: ckb-vm-contract-test-analysis
description: Analyzes and designs test cases for CKB (Common Knowledge Base) smart contracts. Use this skill when working on CKB contract testing to understand transaction structures, verification rules, and test coverage requirements for Lock and Type scripts.
---
# CKB Contract Test Analysis

This skill provides guidelines for testing CKB (Common Knowledge Base) smart contracts. CKB uses a UTXO model, differing from account-based models like Ethereum. Testing focuses on transaction structure, grouping logic, and comprehensive test case design for Lock and Type scripts.

## 1. CKB Transaction Structure

A CKB transaction includes:

- **Inputs**: Cells consumed in the transaction.
  - `previous_output`: Reference to the prior output Cell.
  - `since`: Timestamp for transaction validity.
- **Outputs**: New Cells created by the transaction.
- **CellDeps**: Dependencies for validation code or other Cells.
- **Witnesses**: Additional data (e.g., signatures) associated with inputs.

### 1.1 Cell Structure

Each Cell comprises:

- **Lock Script**: Ownership verification logic.
- **Type Script** (Optional): Data validation logic.
- **Data**: Stored content.

### 1.2 Script Structure

Scripts contain:
- `code_hash`: Hash of the executable code.
- `hash_type`: Either `data` or `type`.
- `args`: Parameters for the script.

## 2. Verification Rules

### 2.1 Grouping Logic

Cells are grouped by `Hash(Script)` for execution:
- **Inputs**: Both Lock and Type scripts are grouped and executed.
- **Outputs**: Only Type scripts are executed; Lock scripts are not.

### 2.2 Execution Flow

- Scripts run in the CKB-VM by group.
- Cycles (execution costs) accumulate per group, with a limit of ~1,000M cycles.

## 3. Test Case Design

Design tests based on input/output combinations to cover validation, transformation, and edge cases.

### Expected Output Format

All test cases must be presented as a Markdown table with the following headers:

| Inputs | Outputs | Scenario | Description |
| --- | --- | --- | --- |

### 3.1 Lock Script Testing

Lock scripts execute only on inputs (outputs are not executed). Key scenarios:

| Inputs | Outputs | Scenario          | Description                          |
|--------|---------|-------------------|--------------------------------------|
| Single | None    | `inputs: [N], outputs: []` | Single-cell validation (e.g., burn). |
| Multi  | None    | `inputs: [N..N], outputs: []` | Multi-cell validation with same lock.|

### 3.2 Type Script Testing

Type scripts execute on both inputs and outputs. Cover creation, destruction, and transformation:

| Inputs | Outputs | Scenario          | Description                          |
|--------|---------|-------------------|--------------------------------------|
| Single | None    | `inputs: [N], outputs: []` | Input validation (burn).             |
| Multi  | None    | `inputs: [N..N], outputs: []` | Multi-input validation.              |
| Single | Single  | `inputs: [N], outputs: [N]` | 1-to-1 transformation.               |
| Single | Multi   | `inputs: [N], outputs: [N..N]` | Split (1-to-N).                      |
| Multi  | Single  | `inputs: [N..N], outputs: [N]` | Merge (N-to-1).                      |
| Multi  | Multi   | `inputs: [N..N], outputs: [N..N]` | Complex N-to-N.                      |
| None   | Single  | `inputs: [], outputs: [N]` | Creation (mint).                     |
| None   | Multi   | `inputs: [], outputs: [N..N]` | Batch creation.                      |

## 4. Contract API Analysis (sUDT Example)

Analyze contracts by identifying accessed data via syscalls. Treat transaction metadata as contract parameters.

### 4.1 Cell Structure Definition

Define input/output Cell structures as:

```typescript
type CellArgs {
    lock_args: Bytes,
    type_args: Bytes,
    data: Bytes,
    witness: Bytes,
}
```

### 4.2 Key Syscalls

Contracts access transaction data via syscalls:

```c
// Transaction metadata
int ckb_load_tx_hash(void* addr, uint64_t* len, size_t offset);
int ckb_load_transaction(void* addr, uint64_t* len, size_t offset);
int ckb_load_script_hash(void* addr, uint64_t* len, size_t offset);
int ckb_load_script(void* addr, uint64_t* len, size_t offset);

// Cell access
int ckb_load_cell(void* addr, uint64_t* len, size_t offset, size_t index, size_t source);
int ckb_load_cell_by_field(void* addr, uint64_t* len, size_t offset, size_t index, size_t source, size_t field);
int ckb_load_cell_data(void* addr, uint64_t* len, size_t offset, size_t index, size_t source);
int ckb_load_input(void* addr, uint64_t* len, size_t offset, size_t index, size_t source);
int ckb_load_input_by_field(void* addr, uint64_t* len, size_t offset, size_t index, size_t source, size_t field);

// Witness and Headers
int ckb_load_witness(void* addr, uint64_t* len, size_t offset, size_t index, size_t source);
int ckb_load_header(void* addr, uint64_t* len, size_t offset, size_t index, size_t source);
int ckb_load_header_by_field(void* addr, uint64_t* len, size_t offset, size_t index, size_t source, size_t field);
int ckb_load_block_extension(void* addr, uint64_t* len, size_t offset, size_t index, size_t source);
```

### 4.3 Example Usage (Rust)

```rust
// Load script args
let script = load_script()?;
let args: Bytes = script.args().unpack();

// Load cell data
QueryIter::new(load_cell_data, Source::GroupInput);
QueryIter::new(load_cell_data, Source::GroupOutput);
```

### 4.4 sUDT-Specific Parameters

sUDT focuses on:
- **args**: Loaded via `load_script()`, represents `owner` (bytes32) for ownership verification.
- **data**: Loaded via `load_cell_data()`, represents `balance` (u128) for token amounts.

Abstracted sUDT Cell:

```typescript
type SudtCellArgs {
    args: { owner: bytes32 },
    data: { balance: u128 }
}
```

### 4.5 Test Scenarios for sUDT

1. **Mint**: `inputs: [], outputs: [SudtCell]` (Admin-only).
2. **Burn**: `inputs: [SudtCell], outputs: []`.
3. **Transfer**: `inputs: [SudtCell], outputs: [SudtCell]` (Verify balance preservation).
4. **Split/Merge**: `inputs: [SudtCell..SudtCell], outputs: [SudtCell..SudtCell]` (Sum(inputs) >= Sum(outputs)).

### 4.6 Possible Contract API Analysis Forms

- Script args–driven: `load_script` and `args()` used for ownership/parameter checks.
- Cell data–driven: `load_cell_data` validates structure, sums, ranges, and invariants.
- Witness–driven: `load_witness` carries signatures/proofs for authorization and multi-sig.
- CellDeps–driven: read config/oracle/code via `Source::CellDep` for external parameters.
- Header–dependent: use `load_header`/block extension for time/epoch/environmental constraints.
- Transaction–wide: access `load_transaction`/`load_tx_hash` for global or anti-replay constraints.
- Field-level access: `load_*_by_field` for precise field validation without full object parsing.
- Group aggregation: iterate `GroupInput`/`GroupOutput` to compute totals and cross-cell consistency.
- Index/source driven: select indices across Input/Output/CellDep sources to target specific cells.
- Mixed strategy: combine the above patterns to build robust validation pipelines.

## 5. Testing Considerations

- **Grouping**: Validate correct grouping in multi-Cell scenarios.
- **Robustness**: Include invalid cases (e.g., non-zero return codes for failures).
- **Cycle Limits**: Monitor and optimize for the ~1,000M cycle cap.
- **Data Boundaries**: Test extremes for `args`, `witness`, and `data` sizes/values.
- **Edge Cases**: Cover zero-balance, max-capacity, and dependency failures.

## 6. Test Cases Table

| Inputs | Outputs | Scenario | Description |
|--------|---------|----------|-------------|
| [N] | [] | Lock single input | Single-cell lock validation (burn/authorization). |
| [N..N] | [] | Lock multi-input | Multi-cell lock validation with same lock. |
| [N] | [] | Type burn | Input validation for destruction. |
| [N..N] | [] | Type multi-input | Validate multiple inputs under the same type script. |
| [N] | [N] | Type transfer (1-to-1) | Transform while preserving per-cell invariants. |
| [N] | [N..N] | Type split (1-to-N) | Split amounts/data across outputs; preserve constraints. |
| [N..N] | [N] | Type merge (N-to-1) | Merge inputs; validate totals and metadata. |
| [N..N] | [N..N] | Type N-to-N | Complex transformation across groups; check sums and consistency. |
| [] | [N] | Mint | Creation under admin/owner rules; initialize data correctly. |
| [] | [N..N] | Batch mint | Batch creation; verify per-output correctness and totals. |
| [SudtCell] | [SudtCell] | sUDT transfer | Preserve total balance; verify `owner` via args. |
| [SudtCell..SudtCell] | [SudtCell..SudtCell] | sUDT split/merge | Sum(inputs) >= Sum(outputs); handle rounding/limits. |
| [Any] | [Any] | Config-dependent via CellDep | Read parameters from dep cells and enforce policies. |
| [Any] | [Any] | Header-dependent | Enforce time/epoch/chain-specific constraints from headers. |

## 7. Error Scenarios and Return Codes 

Use negative test cases to cover each error path exposed by the contract. Design inputs/witnesses to deterministically trigger the failure and assert non-zero return codes.

| Code | Cause | How to Trigger | Expected Behavior | Notes |
|------|-------|----------------|-------------------|-------|
