# CKB 合约测试指南

[Design Test Cases](https://www.notion.so/Design-Test-Cases-2388f0d3781e80e6b51bdbc07f1424e4?pvs=21) 

Nervos CKB（Common Knowledge Base）是一个基于 UTXO 模型的区块链，支持智能合约开发。由于其交易结构和验证机制与账户模型（如以太坊）不同，合约测试需要特别关注交易结构、分组逻辑和测试用例设计。本指南详细介绍了 CKB 合约测试的关键点，帮助开发者构建鲁棒的测试用例。

---

## 1. CKB 交易结构

CKB 的交易由以下核心部分组成：

- **Inputs**：一组输入 Cell，表示交易消耗的资源。
  -- Input中除了Cell 后，还有previous_output，用于引用上一个交易的输出Cell和since字段，用于验证交易提交时间。
- **Outputs**：一组输出 Cell，表示交易生成的新资源。
- **CellDeps**：引用的验证代码或依赖 Cell，用于执行合约逻辑。
- **Witnesses**：为每个 Input 提供解锁数据（如签名或解锁脚本）。
- ~~…~~

此处仅关注与合约执行相关的字段。如需了解 CKB 的完整交易结构构或其他字段，请参考：https://github.com/nervosnetwork/rfcs/blob/master/rfcs/0022-transaction-structure/0022-transaction-structure.md
since字段：用于验证交易提交时间https://github.com/nervosnetwork/rfcs/blob/master/rfcs/0017-tx-valid-since/0017-tx-valid-since.md 。

### 1.1 Cell 结构

每个 [Cell](https://docs.nervos.org/docs/tech-explanation/cell) 是 CKB 的基本数据单元，包含以下字段：

- **Lock Script**：定义 Cell 的所有权验证逻辑（类似“锁”）。
- **Type Script**（可选）：定义 Cell 的数据验证逻辑（类似“类型约束”）。
- **Data**：存储 Cell 的实际数据。
- **Script 结构**：
    - `code_hash`：指向验证代码的哈希。
    - `hash_type`：指定代码引用方式（`data` 或 `type`）。
    - `args`：传递给合约的参数。

**类比**：交易是将输入 Cell（如 100 元钞票）转化为输出 Cell（如两张 50 元钞票），通过 CellDep 中的验证代码执行逻辑。

**示例**：

```solidity
Inputs: [Cell(100)]
Outputs: [Cell(50), Cell(50)]
CellDeps: [Validation Code]

```

## 2. CKB 交易验证规则

CKB 的交易验证基于 Lock 和 Type 脚本，遵循以下流程：

### 2.1 分组逻辑

- 根据脚本的 `Hash(Script)`，将交易中的 Cell 分组。
- **Inputs** 中的 Lock 和 Type 脚本会被分组并执行。
- **Outputs** 中的 Lock 脚本不执行，仅 Type 脚本可能被验证

### 2.2 执行流程

- CKB-VM 按组运行脚本，累加每组脚本的 Cycle 消耗，计算交易总 Cycle。
- 分组只考虑：
    - Inputs 中的 Lock 和 Type 脚本。
    - Outputs 中的 Type 脚本（Outputs 的 Lock 脚本不执行）。

**示例**：

```solidity
Transaction {
    Inputs: [
        Cell_1 {lock: A, type: B},
        Cell_2 {lock: A, type: B},
        Cell_3 {lock: C, type: None}
    ]
    Outputs: [
        Cell_4 {lock: D, type: B},
        Cell_5 {lock: C, type: B},
        Cell_6 {lock: G, type: None},
        Cell_7 {lock: A, type: F}
    ]
}

```

**分组结果**：

```solidity
[
    Lock A: inputs:[0, 1], outputs:[],
    Lock C: inputs:[2], outputs:[],
    Type B: inputs:[0, 1], outputs:[0, 1],
    Type F: inputs:[], outputs:[3]
]

```

**执行过程**：

- CKB-VM 依次运行脚本 A、C、B、F，计算总 Cycle 消耗。
- Outputs 中的 Lock 脚本（D、C、G、A）不执行。

---

## 3. CKB 合约测试用例设计

根据 Lock 和 Type 脚本的特点，测试用例需要覆盖以下场景：

### 3.1 Lock 合约测试

Output 中的 Lock 脚本不执行，因此测试重点关注 Inputs 中的 Lock 脚本：

- **单输入**：`inputs: [N], outputs: []`
    - 测试单个 Cell 的 Lock 脚本验证逻辑。
- **多输入**：`inputs: [N..N], outputs: []`
    - 测试多个 Cell 使用相同 Lock 脚本的验证行为。
- **注意**：除非合约明确要求验证 Outputs 的 Lock 脚本（如通过 Type 脚本逻辑），否则无需测试 Outputs 的 Lock。

### 3.2 Type 合约测试

Type 脚本可能在 Inputs 和 Outputs 中执行，测试用例需覆盖以下组合：

| 输入 | 输出 | example | 场景 |
| --- | --- | --- | --- |
| 单 | 无 | `inputs: [N], outputs: []` | 测试 Type 脚本在仅有输入时的验证逻辑。 |
| 多 | 无 | `inputs: [N..N], outputs: []` | 测试多个输入 Cell 使用相同 Type 脚本的场景。 |
| 单 | 单 | `inputs: [N], outputs: [N]` | 测试 Type 脚本在输入到输出的转化逻辑 |
| 单 | 多 | `inputs: [N], outputs: [N..N]` | 测试 Type 脚本在输入拆分为多个输出的场景。 |
| 多 | 单 | `inputs: [N..N], outputs: [N]` | 测试多个输入合并为单个输出的场景。 |
| 多 | 多 | `inputs: [N..N], outputs: [N..N]` | 测试复杂的输入输出组合。 |
| 无 | 单 | `inputs: [], outputs: [N]` | 测试创建新 Cell 的场景。 |
| 无 | 多 | `inputs: [], outputs: [N..N]` | 测试批量创建 Cell 的场景 |
- 原内容（用上面的表格表示）
    - **单输入，无输出**：`inputs: [N], outputs: []`
        - 测试 Type 脚本在仅有输入时的验证逻辑。
    - **多输入，无输出**：`inputs: [N..N], outputs: []`
        - 测试多个输入 Cell 使用相同 Type 脚本的场景。
    - **单输入，单输出**：`inputs: [N], outputs: [N]`
        - 测试 Type 脚本在输入到输出的转化逻辑。
    - **单输入，多输出**：`inputs: [N], outputs: [N..N]`
        - 测试 Type 脚本在输入拆分为多个输出的场景。
    - **多输入，单输出**：`inputs: [N..N], outputs: [N]`
        - 测试多个输入合并为单个输出的场景。
    - **多输入，多输出**：`inputs: [N..N], outputs: [N..N]`
        - 测试复杂的输入输出组合。
    - **无输入，单输出**：`inputs: [], outputs: [N]`
        - 测试创建新 Cell 的场景。
    - **无输入，多输出**：`inputs: [], outputs: [N..N]`
        - 测试批量创建 Cell 的场景。
    

---

## 4. 梳理合约 API 并设计测试用例

在测试之前，需梳理合约的交易构建 API，以明确测试范围。与以太坊的简单函数调用不同，CKB 的 UTXO 模型使交易 API 较为复杂。以下以 [sUDT（Simple User Defined Token](https://docs.nervos.org/docs/tech-explanation/glossary#simple-udt)）合约为例，说明如何梳理 API 和设计测试用例。

### 4.1 sUDT 合约示例

以下是 sUDT 合约的核心代码（Rust），用于验证代币的输入输出平衡：

```rust
use ckb_std::{
    entry,
    default_alloc,
    high_level::{load_script, load_cell_lock_hash, load_cell_data, QueryIter},
    ckb_constants::Source,
    error::SysError,
    ckb_types::{bytes::Bytes, prelude::*},
};

entry!(entry);
default_alloc!();

#[repr(i8)]
enum Error {
    IndexOutOfBound = 1,
    ItemMissing,
    LengthNotEnough,
    Encoding,
    Amount,
}

const UDT_LEN: usize = 16;

fn check_owner_mode(args: &Bytes) -> Result<bool, Error> {
    let is_owner_mode = QueryIter::new(load_cell_lock_hash, Source::Input)
        .find(|lock_hash| args[..] == lock_hash[..]).is_some();
    Ok(is_owner_mode)
}

fn collect_inputs_amount() -> Result<u128, Error> {
    let mut buf = [0u8; UDT_LEN];
    let udt_list = QueryIter::new(load_cell_data, Source::GroupInput)
        .map(|data| {
            if data.len() == UDT_LEN {
                buf.copy_from_slice(&data);
                Ok(u128::from_le_bytes(buf))
            } else {
                Err(Error::Encoding)
            }
        }).collect::<Result<Vec<_>, Error>>()?;
    Ok(udt_list.into_iter().sum::<u128>())
}

fn collect_outputs_amount() -> Result<u128, Error> {
    let mut buf = [0u8; UDT_LEN];
    let udt_list = QueryIter::new(load_cell_data, Source::GroupOutput)
        .map(|data| {
            if data.len() == UDT_LEN {
                buf.copy_from_slice(&data);
                Ok(u128::from_le_bytes(buf))
            } else {
                Err(Error::Encoding)
            }
        }).collect::<Result<Vec<_>, Error>>()?;
    Ok(udt_list.into_iter().sum::<u128>())
}

fn main() -> Result<(), Error> {
    let script = load_script()?;
    let args: Bytes = script.args().unpack();

    if check_owner_mode(&args)? {
        return Ok(());
    }

    let inputs_amount = collect_inputs_amount()?;
    let outputs_amount = collect_outputs_amount()?;

    if inputs_amount < outputs_amount {
        return Err(Error::Amount);
    }

    Ok(())
}

```

### 4.2 合约 API 分析

```solidity
// args
let script = load_script()?;
let args: Bytes = script.args().unpack();

// data
QueryIter::new(load_cell_data, Source::GroupInput)
QueryIter::new(load_cell_data, Source::GroupOutput)
```

sUDT 合约主要关注以下数据：

- **args**：load_script 时会去读取args ，用于验证所有权用`owner` 表示。
- **data**：load_cell_data 时会读取data，表示代币余额用`balance` 表示。

基于此，sUDT 的交易 API 可抽象为以下 Cell 结构：

```solidity
type SudtCell {
    args: { owner: bytes32 }
    data: { balance: u128 }
    
}
```

### 4.3 测试用例设计

根据 type 合约的特点，测试用例应覆盖以下交易场景：

| 输入数 | 输出数 | 示例 |  场景 |  |
| --- | --- | --- | --- | --- |
| 0 | 1 | `inputs: [], outputs: [SudtCell]` | 1. 管理员可以创建一个 SUDT
2. 非管理员创建sudt，预期报错
3. 管理员可以创建不符合data不为16的cell |  |
| 0 | N | `inputs: [], outputs: [SudtCell..N]` | 
1. 管理员批量创建 sUDT
2. 管理员可以创建多个cell 总量超过u128::max |  |
| 1 | 0 | `inputs: [SudtCell], outputs: []` | 1. 销毀一个 SUDT |  |
| 1 | 1 | `inputs: [SudtCell], outputs: [SudtCell]` | 
1. 非管理员 转移一个 sUDT，input的sudtCell.balace>= output 的sudtCell.balance
2. 非管理员 转移一个 sUDT，input的sudtCell.balace < output 的sudtCell.balance,预期报错
3. 非管理员，无法转移data不为16的cell |  |
| 1 | N | `inputs: [SudtCell], outputs: [SudtCell..N]` | 1. 非管理员 转移一个 sUDT，input的sudtCell.balace 的总和 >= output 的sudtCell.balance的总和 |  |
| N | 0 | `inputs: [SudtCell..N], outputs: []` | 1. 批量销毁sudt
2. 无法批量销毁input的sudtCell.balace 的总和 > u128::max  |  |
| N | 1 | `inputs: [SudtCell..N], outputs: [SudtCell]` | 1. 非管理员 转移N个 sUDT，input的sudtCell.balace 的总和 > output 的sudtCell.balance
2. 非管理员 转移N个 sUDT，input的sudtCell.balace 的总和 < output 的sudtCell.balance,预期报错
 |  |
| N | N | `inputs: [SudtCell..N], outputs: [SudtCell..N]` | 1. 非管理员 转移N个 sUDT，input的sudtCell.balace 的总和 > output 的sudtCell.balance
2. 非管理员 转移N个 sUDT，input的sudtCell.balace 的总和 < output 的sudtCell.balance,预期报错
 |  |
- 原内容（转为上面表格）
    - **0 -> 1**：`inputs: [], outputs: [SudtCell]`
    - **0 -> N**：`inputs: [], outputs: [SudtCell..N]`
    - **1→0**:  `inputs: [SudtCell], outputs: []`
    - **1 -> 1**：`inputs: [SudtCell], outputs: [SudtCell]`
    - **1 -> N**：`inputs: [SudtCell], outputs: [SudtCell..N]`
    - **N → 0**:  `inputs: [SudtCell..N], outputs: []`
    - **N→1**:  `inputs: [SudtCell..N], outputs: [SudtCell]`
    - **N -> N**：`inputs: [SudtCell..N], outputs: [SudtCell..N]`
    

具体代码见：https://github.com/sunchengzhu/ckb-contract-minitest/blob/main/tests/sudt.rs

基于上述api ，我们可以像接口测试一样，完善合约测试用例。

## 5. 测试注意事项

为确保测试覆盖全面且有效，需注意以下事项：

### 5.1 分组逻辑

- 覆盖所有可能的脚本分组组合，特别是多输入、多输出的复杂场景。
- 确保测试用例不误测 Outputs 中的 Lock 脚本（因其不执行）。

### 5.2 错误场景

- 构造非法交易（如执行返回结果非0交易）以测试合约的鲁棒性。
- 测试异常情况，如 Cycle 超限（CKB-VM 限制约为 1000M Cycles）或脚本执行错误。

### 5.3 数据大小验证

CKB-VM 有内存大小限制，按需测试以下数据的边界：

- **script.args**：如果合约里有获取args数据，可以测试args数据的上限值。
- **witness**：如果合约里有获取witness数据，可以测试witness数据的上限值。
- **data**：如果合约里有获取data数据，可以测试data数据的上限值。

## 6. 总结

CKB 合约测试需要深入理解其 UTXO 模型和交易验证机制。通过梳理交易结构、验证规则和合约 API，开发者可以设计全面的测试用例，覆盖 Lock 和 Type 脚本的各种场景。特别注意分组逻辑、Cycle 消耗和数据大小限制，以确保合约在各种边界条件下都能稳定运行。