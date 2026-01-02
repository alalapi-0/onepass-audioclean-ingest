# OnePass AudioClean Ingest (R3)

## 目标与范围
- 提供音频清洗流水线的输入标准化与元数据生成入口骨架。
- 仅聚焦 ingest：不做分段、不做 ASR、不做口误检测、不做剪辑，不引入任何联网或模型下载逻辑。
- 默认离线可用，依赖仅限 Python 包与本机可用的 ffmpeg/ffprobe。

## R3 范围
- 固化 meta.json 规范 v1，并提供 JSON Schema（`schemas/meta.v1.schema.json`）。
- 实现 Meta 数据结构、写入逻辑、稳定性（核心/非核心字段）规则。
- 新增 `onepass-ingest meta` 子命令，生成符合 schema 的 meta.json（不做音频转码）。
- 尝试使用 ffprobe 采集输入媒体信息；缺失时生成 errors/warnings 但仍输出 meta.json。

## 环境要求
- Python >= 3.10。
- 推荐在 macOS/Linux/Windows 环境下使用，开发以 macOS 为主。

## 安装（可编辑模式）
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## CLI 入口
安装后提供命令 `onepass-ingest`。

```bash
onepass-ingest --help
onepass-ingest check-deps --help
onepass-ingest meta --help
```

### check-deps（R2）
用途：检查本机是否具备最小可用的 ffmpeg/ffprobe，并输出版本与能力探测结果。支持 `--json` 和 `--verbose`，退出码 0/2/3/4 与 R2 保持一致。

### meta（R3）
用途：仅生成 `meta.json`（不做转码），可在后续流水线中复用。

用法示例：

```bash
onepass-ingest meta <input> --out <workdir>
onepass-ingest meta input.wav --out out/input__hash --json
```

行为与退出策略：

- workdir 不存在会自动创建；创建失败退出码 1。
- 其它失败（如 ffprobe 缺失、输入不存在）会记录到 `meta.errors`，依然写出 meta.json 并返回 0，方便流水线继续。
- `--json` 会把生成的 meta 内容输出到 stdout，便于调试。

## 配置文件
- 位置：`configs/default.yaml`
- 格式选择：采用 YAML，原因是配置层级清晰、易读且便于后续扩展复杂结构。
- 默认字段：
  - `sample_rate: 16000`
  - `channels: 1`
  - `bit_depth: 16`
  - `normalize: false`
- 约定：未来 CLI 参数将覆盖配置文件中的值；配置加载将优先读取默认配置，再合并用户传入的路径。

## 输出目录约定（workdir）
- 默认输出根目录：`./out`。
- 单输入文件生成一个 workdir，命名规则：`out/<input_stem>__<short_hash>/`（哈希策略将在后续版本固化）。
- workdir 内文件约定：
  - `audio.wav`：标准化后的音频（R4 才会生成）。
  - `meta.json`：元数据（R3 已落地 schema）。
  - `convert.log`：ffmpeg 调用日志（R4 将写入，R3 可为空占位）。
- 批量处理：每个输入文件对应独立 workdir，便于幂等执行与缓存。

## meta.json 规范 v1

- Schema 路径：`schemas/meta.v1.schema.json`（JSON Schema 2020-12）。
- 核心字段：决定输出一致性的字段，例如 `params.*`、`output.workdir`、`output.expected_audio.*`、`input.size_bytes`。同一输入与参数组合应保持稳定。
- 可变字段：`created_at`、绝对路径（`input.abspath`）、`mtime_epoch`、平台信息、`probe.warnings` 等，跨机器或跨时间可能不同。
- 路径策略：同时记录用户传入的 `input.path`（原样保留，核心字段）与 `input.abspath`（解析后的绝对路径，非核心），便于可追踪又避免跨机器不稳定。

顶层字段摘要：

| 字段 | 说明 |
| --- | --- |
| `schema_version` | 固定为 `meta.v1` |
| `created_at` | ISO8601 创建时间（非核心） |
| `pipeline.repo` / `repo_version` | 仓库标识与版本（版本可能为空） |
| `input` | 路径、大小、扩展名、可选 mtime/sha256 |
| `params` | 采样率、通道、位深、normalize、额外 ffmpeg 参数 |
| `tooling` | ffmpeg/ffprobe 探测信息，Python 运行时信息 |
| `probe` | 通过 ffprobe 获取的媒体摘要，附 warnings |
| `output` | workdir 相对路径、文件名、预期输出参数（actual_audio 在 R4 填充） |
| `integrity` | meta/audio 的可选 sha256 摘要（R4+ 补全） |
| `errors` | 结构化错误列表（包含 code/message/hint/detail） |
| `stable_fields` | 列出核心与非核心字段路径及说明 |

核心字段列表和规则同时写入 `meta.json.stable_fields`，在自动化校验或回归测试时使用。

## 开发规范
- 日志：使用标准库 `logging`，统一入口在 `onepass_audioclean_ingest.logging_utils.get_logger`，后续补充格式与级别配置。
- 错误码：`check-deps` 根据依赖状态返回 0/2/3/4，其余子命令除非出现无法写盘等硬错误，一律返回 0 并在 meta.json 中记录错误。
- Schema：meta.json v1 的 schema 固化在 `schemas/meta.v1.schema.json`，CLI 可使用该文件进行验证或回归测试。

## 路线图（摘要）
- R3：meta.json schema v1、稳定字段与 probe 逻辑、`meta` 子命令。
- R4：补齐真实转码与 actual_audio 填充、日志与校验完善。
- R5+：性能优化、批量处理、更多平台兼容测试。

## 验收命令
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
onepass-ingest --help
onepass-ingest check-deps --json
onepass-ingest meta <some_input> --out out/test_workdir
pytest -q
```
