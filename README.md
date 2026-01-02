# OnePass AudioClean Ingest (R4)

## 目标与范围
- 提供音频清洗流水线的输入标准化与元数据生成入口骨架。
- 仅聚焦 ingest：不做分段、不做 ASR、不做口误检测、不做剪辑，不引入任何联网或模型下载逻辑。
- 默认离线可用，依赖仅限 Python 包与本机可用的 ffmpeg/ffprobe。

## R4 范围
- 实现单文件音频输入的 ingest：使用 ffmpeg 转为标准 `audio.wav`（PCM s16le）。
- 生成 `convert.log`，记录 ffmpeg 命令、stdout/stderr，便于排障。
- meta.json 填充 `output.actual_audio`（ffprobe 读取转换结果）并可选打印到 stdout。
- CLI 覆盖常用参数：sample-rate/channels/bit-depth（仅 16）/normalize/overwrite/json。
- 新增错误码和退出码约定，失败时尽量写出 meta.json。

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
onepass-ingest ingest --help
```

### check-deps（R2）
用途：检查本机是否具备最小可用的 ffmpeg/ffprobe，并输出版本与能力探测结果。支持 `--json` 和 `--verbose`，退出码 0/2/3/4 与 R2 保持一致。

### meta（R4，生成 meta.json 不转码）
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

### ingest（R4，单文件转 WAV）
用途：将输入音频（wav/mp3/m4a/aac/flac/ogg/opus 等常见格式）转换为标准 PCM s16le wav，生成 meta.json 与 convert.log。

用法示例：

```bash
onepass-ingest ingest input.mp3 --out out/demo_workdir
onepass-ingest ingest input.wav --out out/demo_workdir --sample-rate 22050 --channels 1 --overwrite --json
```

行为与退出策略：

- 依赖检查：执行前调用 `check-deps`，若 ffmpeg/ffprobe 缺失或不可用，退出码 2 并尽量写出 meta.json。
- 输入缺失：记录到 meta.errors，退出码 10。
- bit depth 仅允许 16；其它值会记录错误并退出码 30。
- 默认不覆盖既有输出；如 workdir 内已有 `audio.wav`/`meta.json`/`convert.log`，需显式 `--overwrite`。
- 转换失败记录 stderr 到 meta.errors 和 convert.log，退出码 20。
- 输出 ffprobe 失败但文件已生成时退出码 21。
- `--json` 会把最终 meta.json 打印到 stdout（仅 JSON 内容，不混杂日志）。

normalize 说明：R4 采用固定滤镜 `loudnorm=I=-16:LRA=11:TP=-1.5`；如未开启则不加滤镜，meta.params.normalize_mode 置为 null。

## 配置文件
- 位置：`configs/default.yaml`
- 格式选择：采用 YAML，原因是配置层级清晰、易读且便于后续扩展复杂结构。
- 默认字段：
  - `sample_rate: 16000`
  - `channels: 1`
  - `bit_depth: 16`
  - `normalize: false`
- 约定：未来 CLI 参数将覆盖配置文件中的值；配置加载将优先读取默认配置，再合并用户传入的路径。

### 参数覆盖（R4）
CLI 优先级高于配置文件；目前支持：`--sample-rate`、`--channels`、`--bit-depth`（仅 16）、`--normalize/--no-normalize`、`--config`。

## 输出目录约定（workdir）
- 默认输出根目录：`./out`。
- 单输入文件生成一个 workdir，命名规则后续版本再固化；本轮只要求用户显式指定 `--out`。
- workdir 内文件：
  - `audio.wav`：标准化后的音频（PCM s16le，固定 `-fflags +bitexact -flags:a +bitexact`）。
  - `meta.json`：元数据，`output.actual_audio` 由 ffprobe 实测填充。
  - `convert.log`：包含时间戳、输入/输出路径、完整 ffmpeg 命令、stdout/stderr。
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
- 错误码：`check-deps` 根据依赖状态返回 0/2/3/4；`ingest` 返回 R4 定义的退出码（见下文），失败也尽量写出 meta.json。
- Schema：meta.json v1 的 schema 固化在 `schemas/meta.v1.schema.json`，CLI 可使用该文件进行验证或回归测试。

## 输出结构
给定 `--out <workdir>`：

- `<workdir>/audio.wav`：转码后的标准化音频（PCM s16le，采样率/声道由参数决定）。
- `<workdir>/meta.json`：完整元数据，包含输入/输出探测信息、参数、errors/warnings。
- `<workdir>/convert.log`：ffmpeg 命令与 stdout/stderr，结尾带换行，便于审计和排错。

## 可复现性策略（R4）
- ffmpeg 输出使用 `-fflags +bitexact -flags:a +bitexact`，并移除元数据 `-map_metadata -1`，减少平台差异。
- 输出编码固定 `-c:a pcm_s16le`，仅允许 bit depth 16。
- 采样率/声道由参数固定，默认 16kHz/单声道。
- normalize 开启时使用固定滤镜 `loudnorm=I=-16:LRA=11:TP=-1.5`，filtergraph 记录在 `params.normalize_mode`。
- convert.log 记录完整命令与 stderr，方便复现与对比。

## 退出码

| 代码 | 说明 |
| --- | --- |
| 0 | 成功 |
| 2 | 依赖缺失或不可运行（ffmpeg/ffprobe） |
| 10 | 输入不存在或不可读取 |
| 11 | 输出目录不可写或存在冲突且未指定 `--overwrite` |
| 20 | ffmpeg 转换失败 |
| 21 | 输出 ffprobe 失败（转换已完成） |
| 30 | 参数无效（如 bit depth 非 16） |

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
