# 版本策略

本文档说明 OnePass AudioClean Ingest 的版本号策略与 schema 版本策略。

## 包版本号（Package Version）

包版本号遵循 [Semantic Versioning](https://semver.org/) 规范，格式为 `MAJOR.MINOR.PATCH`。

- **MAJOR**：不兼容的 API 变更
- **MINOR**：向后兼容的功能新增
- **PATCH**：向后兼容的问题修复

当前版本：`0.1.0`（开发中）

## Schema 版本策略

### meta.json Schema

**当前版本：`meta.v1`**

#### 兼容性原则

- **只增字段不删字段**：`meta.v1` schema 只允许添加新字段，不允许删除或修改现有字段
- **字段类型不变**：现有字段的类型不能改变（如不能将字符串改为整数）
- **可选字段可变为必需**：可选字段可以变为必需字段，但需在下一个主版本（`meta.v2`）
- **破坏性变更需升级**：任何破坏性变更（删除字段、改变类型、改变必需性）需升级到 `meta.v2`

#### 版本升级规则

- **向后兼容变更**：在 `meta.v1` 中添加新字段（可选）
- **破坏性变更**：升级到 `meta.v2`，并更新 `schemas/meta.v2.schema.json`

#### Repo2/Repo3 兼容性

Repo2 和 Repo3 依赖以下字段（`meta.v1` 稳定字段）：
- `output.audio_wav`
- `output.workdir`
- `params.sample_rate`
- `params.channels`
- `params.bit_depth`
- `params.normalize`
- `output.expected_audio.*`
- `probe.input_ffprobe.duration`（推荐）

这些字段在 `meta.v1` 中不会改变，确保 Repo2/Repo3 的兼容性。

### manifest.jsonl Schema

**当前版本：`manifest.v1`**

#### 兼容性原则

- **只增字段不删字段**：`manifest.v1` schema 只允许添加新字段，不允许删除或修改现有字段
- **字段类型不变**：现有字段的类型不能改变
- **破坏性变更需升级**：任何破坏性变更需升级到 `manifest.v2`

#### 版本升级规则

- **向后兼容变更**：在 `manifest.v1` 中添加新字段（可选）
- **破坏性变更**：升级到 `manifest.v2`，并更新 `schemas/manifest.v2.schema.json`

#### Dry-run 模式

Dry-run 模式使用独立的 schema 版本：`manifest.plan.v1`
- 与 `manifest.v1` 类似，但 `status` 固定为 `planned`
- 兼容性原则与 `manifest.v1` 相同

## Workdir 结构稳定性

### 文件结构

workdir 内的文件结构不会改变：
- `audio.wav`：标准化后的音频文件
- `meta.json`：元数据文件
- `convert.log`：转换日志文件

### 路径约定

- `audio.wav` 始终位于 workdir 根目录
- `meta.json` 始终位于 workdir 根目录
- `convert.log` 始终位于 workdir 根目录

这些路径是 Repo2/Repo3 的输入契约，不会轻易改变。

## 版本兼容性矩阵

| Repo1 版本 | meta.json schema | manifest.jsonl schema | 兼容性说明 |
| --- | --- | --- | --- |
| R1-R10 | `meta.v1` | `manifest.v1` | 当前稳定版本 |
| 未来 | `meta.v2` | `manifest.v2` | 破坏性变更时升级 |

## 迁移指南

### 从 meta.v1 迁移到 meta.v2（未来）

如果未来需要升级到 `meta.v2`：

1. **检查依赖字段**：确认 Repo2/Repo3 依赖的字段在新版本中仍然存在
2. **更新 schema 文件**：更新 `schemas/meta.v2.schema.json`
3. **更新代码**：更新生成 `meta.json` 的代码，使用新的 schema 版本
4. **更新文档**：更新 README.md 和相关文档
5. **向后兼容**：考虑同时支持 `meta.v1` 和 `meta.v2`（如果可能）

### 从 manifest.v1 迁移到 manifest.v2（未来）

类似地，如果未来需要升级到 `manifest.v2`：

1. **检查依赖字段**：确认依赖的字段在新版本中仍然存在
2. **更新 schema 文件**：更新 `schemas/manifest.v2.schema.json`
3. **更新代码**：更新生成 `manifest.jsonl` 的代码
4. **更新文档**：更新 README.md 和相关文档

## 版本检查

### 检查 meta.json schema 版本

```bash
cat <workdir>/meta.json | jq '.schema_version'
```

### 检查 manifest.jsonl schema 版本

```bash
head -n 1 <out-root>/manifest.jsonl | jq -r '.schema_version'
```

### 验证 schema 兼容性

使用 JSON Schema 验证器验证文件是否符合 schema：

```bash
# 验证 meta.json
python -c "
import json
from jsonschema import Draft202012Validator
with open('schemas/meta.v1.schema.json') as f:
    schema = json.load(f)
with open('<workdir>/meta.json') as f:
    data = json.load(f)
validator = Draft202012Validator(schema)
errors = list(validator.iter_errors(data))
if errors:
    for error in errors:
        print(error.message)
else:
    print('Valid')
"
```

## 总结

- **meta.v1** 和 **manifest.v1** 是当前稳定版本
- 只增字段不删字段，确保向后兼容
- 破坏性变更需升级到 v2
- workdir 结构不会改变
- Repo2/Repo3 依赖的字段在 v1 中保持稳定

