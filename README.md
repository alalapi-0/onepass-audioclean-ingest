# OnePass AudioClean Ingest

## 项目简介

OnePass AudioClean Ingest（Repo1）是 onepass-audioclean 工具链的入口模块，负责将原始音频和视频文件转换为标准化的 PCM WAV 格式，并生成元数据文件供后续流水线模块使用。

### 在工具链中的位置

- **Repo1（本仓库）**：负责 ingest（输入标准化），将原始媒体文件转换为标准 WAV 并生成元数据
- **Repo2**：负责分段（segmentation）和 ASR（自动语音识别）
- **Repo3**：负责口误检测和剪辑

### 目标与非目标

**本仓库的目标：**
- 将音频/视频文件转换为标准 PCM s16le WAV 格式
- 生成结构化的元数据文件（meta.json）
- 支持批处理并生成清单文件（manifest.jsonl）
- 提供可复现的转换结果（通过固定 ffmpeg 参数）
- 默认离线可用，不依赖任何联网服务

**本仓库不做的事情：**
- 不做音频分段（segmentation）
- 不做 ASR（自动语音识别）
- 不做口误检测
- 不做剪辑操作
- 不引入任何模型下载或联网服务
- 不处理音频内容分析

## 快速开始

### 环境要求

- Python >= 3.10
- ffmpeg 和 ffprobe（需单独安装，见下方说明）
- 推荐在 macOS/Linux/Windows 环境下使用，开发以 macOS 为主

### 安装

```bash
# 创建虚拟环境（推荐）
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装包（可编辑模式）
pip install -e .
```

### 检查依赖

在开始使用前，请检查本机是否具备可用的 ffmpeg/ffprobe：

```bash
onepass-ingest check-deps
onepass-ingest check-deps --json  # JSON 格式输出
onepass-ingest check-deps --verbose  # 显示详细信息
```

**安装 ffmpeg/ffprobe：**
- macOS: `brew install ffmpeg`
- Ubuntu/Debian: `sudo apt-get install ffmpeg`
- Windows: 从 [ffmpeg.org](https://ffmpeg.org/download.html) 下载并添加到 PATH

### 单文件 ingest 示例

**音频文件：**
```bash
# 基本用法
onepass-ingest ingest input.mp3 --out out/demo_workdir

# 指定参数
onepass-ingest ingest input.wav --out out/demo_workdir \
  --sample-rate 22050 --channels 1 --overwrite

# 输出 meta.json 到 stdout（仅 JSON）
onepass-ingest ingest input.mp3 --out out/demo_workdir --json
```

**视频文件：**
```bash
# 从视频中提取音频
onepass-ingest ingest input.mp4 --out out/video_workdir

# 指定音轨索引或语言
onepass-ingest ingest input.mkv --out out/video_workdir \
  --audio-stream-index 1
onepass-ingest ingest input.mkv --out out/video_workdir \
  --audio-language eng
```

### 目录批处理 ingest 示例

```bash
# 基本批处理（递归扫描）
onepass-ingest ingest data/raw --out-root out/batch

# 指定扩展名过滤
onepass-ingest ingest data/raw --out-root out/batch \
  --ext mp3,wav,mp4

# 非递归扫描
onepass-ingest ingest data/raw --out-root out/batch \
  --no-recursive

# 遇到失败立即停止
onepass-ingest ingest data/raw --out-root out/batch \
  --fail-fast

# 指定日志文件
onepass-ingest ingest data/raw --out-root out/batch \
  --log-file custom.log

# 启用详细日志
onepass-ingest ingest data/raw --out-root out/batch \
  --verbose
```

### Dry-run 示例

**单文件 dry-run：**
```bash
# 只生成 meta.json，不转码
onepass-ingest ingest input.mp3 --out out/dry_single --dry-run
```

**目录批处理 dry-run：**
```bash
# 只生成 manifest.plan.jsonl，不创建 workdir
onepass-ingest ingest data/raw --out-root out/dry_batch --dry-run
```

### Normalize 示例

**注意：normalize 默认关闭，开启后会改变波形，可复现性依赖相同的 ffmpeg 版本。**

```bash
# 启用响度归一化
onepass-ingest ingest input.mp3 --out out/norm_on --normalize

# 显式关闭（默认行为）
onepass-ingest ingest input.mp3 --out out/norm_off --no-normalize
```

更多示例命令请参考 `examples/commands.md`。

## 输出产物与目录结构（接口契约）

### Workdir 结构

每个输入文件对应一个独立的 workdir，包含以下三个文件：

```
<workdir>/
├── audio.wav      # 标准化后的音频（PCM s16le）
├── meta.json      # 元数据文件
└── convert.log    # ffmpeg 转换日志
```

**重要：这些路径和字段是后续 Repo2/Repo3 的输入契约，不会轻易改变。**

### meta.json 位置与 schema

- **位置**：`<workdir>/meta.json`
- **Schema 文件**：`schemas/meta.v1.schema.json`
- **Schema 版本**：`meta.v1`（固定值）
- **版本策略**：见 `VERSIONING.md`

### manifest.jsonl 位置与 schema

- **位置**：`<out-root>/manifest.jsonl`（批处理模式）
- **Schema 文件**：`schemas/manifest.v1.schema.json`
- **Schema 版本**：`manifest.v1`（固定值）
- **Dry-run 模式**：生成 `manifest.plan.jsonl`（schema_version=`manifest.plan.v1`）

### 与 Repo2/Repo3 的接口契约

Repo2 和 Repo3 依赖以下字段和路径：

**必需字段（meta.json）：**
- `output.audio_wav`：音频文件相对路径（固定为 `audio.wav`）
- `output.workdir`：workdir 路径
- `params.sample_rate`：采样率
- `params.channels`：声道数
- `params.bit_depth`：位深（固定为 16）
- `params.normalize`：是否启用归一化
- `output.expected_audio`：预期音频参数（codec/sample_rate/channels/bit_depth）
- `probe.input_ffprobe.duration`：输入文件时长（秒）

**可选但推荐字段：**
- `output.actual_audio`：实际输出音频参数（用于验证）
- `execution.ffmpeg_cmd_str`：ffmpeg 命令（用于调试）
- `errors`：错误列表（用于判断处理是否成功）

**manifest.jsonl 字段：**
- `input.relpath`：输入文件相对路径
- `output.workdir`：workdir 路径
- `status`：处理状态（`success`/`failed`/`planned`）
- `exit_code`：退出码
- `error_codes`：错误码列表
- `meta_json_path`：meta.json 绝对路径

**兼容性承诺：**
- `meta.v1` schema 只增字段不删字段
- 破坏性变更需升级到 `meta.v2`
- `manifest.v1` 同理
- workdir 内文件结构（audio.wav/meta.json/convert.log）保持不变

## meta.json 字段说明

### 核心字段（Core Fields）

核心字段决定输出一致性，同一输入与参数组合应保持稳定：

- `schema_version`：固定为 `meta.v1`
- `input.path`：用户传入的输入路径（原样保留）
- `input.size_bytes`：输入文件大小（字节）
- `input.ext`：文件扩展名
- `params.*`：所有参数（sample_rate/channels/bit_depth/normalize 等）
- `params_sources.*`：参数来源（default/config/cli）
- `output.workdir`：workdir 路径
- `output.work_id`：workdir ID（批处理模式）
- `output.work_key`：workdir 键（批处理模式）
- `output.audio_wav`：音频文件名（固定为 `audio.wav`）
- `output.expected_audio.*`：预期音频参数

### 非核心字段（Non-core Fields）

非核心字段可能在不同运行或机器间变化：

- `created_at`：创建时间戳
- `input.abspath`：绝对路径
- `input.mtime_epoch`：文件修改时间
- `tooling.*`：工具版本信息
- `probe.warnings`：探测警告
- `output.actual_audio`：实际音频参数（由 ffprobe 实测）
- `errors`：错误列表
- `warnings`：警告列表
- `execution.*`：执行信息（命令、filtergraph 等）

### Repo2/Repo3 依赖的最小字段集

**必须字段：**
- `output.audio_wav`：音频文件相对路径
- `output.workdir`：workdir 路径
- `params.sample_rate`：采样率
- `params.channels`：声道数
- `params.bit_depth`：位深
- `params.normalize`：是否归一化
- `output.expected_audio.codec`：编解码器（固定为 `pcm_s16le`）
- `output.expected_audio.sample_rate`：预期采样率
- `output.expected_audio.channels`：预期声道数
- `output.expected_audio.bit_depth`：预期位深

**推荐字段：**
- `probe.input_ffprobe.duration`：输入时长（秒）
- `output.actual_audio.*`：实际输出参数（用于验证）
- `errors`：错误列表（用于判断处理是否成功）

完整字段列表和说明见 `meta.json` 中的 `stable_fields` 字段。

## manifest.jsonl 字段说明

### 基本结构

每行一条 JSON 记录，UTF-8 换行分隔，不包裹数组。

### 关键字段

- `schema_version`：固定为 `manifest.v1` 或 `manifest.plan.v1`（dry-run）
- `input.relpath`：输入文件相对路径（相对于输入根目录）
- `input.path`：输入文件绝对路径
- `input.ext`：文件扩展名
- `input.size_bytes`：文件大小（字节）
- `output.workdir`：workdir 路径
- `output.work_id`：workdir ID
- `output.work_key`：workdir 键
- `output.audio_wav`：音频文件路径
- `output.meta_json`：meta.json 路径
- `output.convert_log`：convert.log 路径
- `status`：处理状态（`success`/`failed`/`planned`）
- `exit_code`：退出码（整数或 null）
- `error_codes`：错误码列表（字符串数组）
- `error_messages`：错误消息列表（字符串数组，每条最多 200 字符）
- `warning_codes`：警告码列表（字符串数组）
- `warning_messages`：警告消息列表（字符串数组）
- `errors_summary`：错误摘要（分号分隔）
- `meta_json_path`：meta.json 绝对路径（若存在）
- `log_file`：全局日志文件路径（可选）
- `started_at`：处理开始时间（ISO8601）
- `ended_at`：处理结束时间（ISO8601）
- `duration_ms`：处理时长（毫秒）
- `params_digest`：参数摘要（SHA256）

### Dry-run 模式差异

在 `--dry-run` 模式下：
- 生成 `manifest.plan.jsonl`（而非 `manifest.jsonl`）
- `schema_version` 为 `manifest.plan.v1`
- `status` 固定为 `planned`
- `exit_code` 为 `null`
- 不创建 workdir，不生成 audio.wav/meta.json/convert.log

示例见 `examples/manifest_sample.jsonl`。

## 配置与参数优先级

### 配置文件位置

- 默认配置：`configs/default.yaml`
- 自定义配置：通过 `--config` 指定路径

### 参数优先级

优先级从高到低：
1. **CLI 显式参数**（`--sample-rate`、`--channels` 等）
2. **`--config` 指定的配置文件**
3. **`configs/default.yaml`**
4. **内置默认值**

### 示例配置

创建 `examples/config.custom.yaml`：

```yaml
sample_rate: 22050
channels: 2
bit_depth: 16
normalize: false
```

使用自定义配置：

```bash
onepass-ingest ingest input.mp3 --out out/demo \
  --config examples/config.custom.yaml
```

### 可覆盖参数

以下参数可通过 CLI 或配置文件覆盖：
- `sample_rate`：采样率（整数）
- `channels`：声道数（整数）
- `bit_depth`：位深（仅支持 16）
- `normalize`：是否启用响度归一化（布尔值）
- `audio_stream_index`：音轨索引（整数，可选）
- `audio_language`：音轨语言标签（字符串，可选）

参数来源会记录在 `meta.params_sources` 中，便于复现与审计。

## 可复现性策略

### ffmpeg 参数

为确保可复现性，使用以下固定参数：

- `-fflags +bitexact`：启用精确位模式
- `-flags:a +bitexact`：音频流精确位模式
- `-map_metadata -1`：移除元数据
- `-c:a pcm_s16le`：固定编码为 PCM s16le
- 采样率和声道由参数固定

### Normalize 可复现性

启用 `--normalize` 后：
- 使用固定滤镜：`loudnorm=I=-16:LRA=11:TP=-1.5:linear=true:print_format=summary`
- 模式名：`loudnorm_r7_v1`
- 配置记录在 `meta.params.normalize_config`
- **可复现性前提**：相同的 ffmpeg 版本和滤镜参数

### Workdir 命名稳定性

批处理模式下，workdir 命名基于：
- 输入文件相对路径（相对于输入根目录）
- 文件大小（字节）

同一输入根目录和文件大小下，workdir 名称稳定，不会因重新运行而改变。

### 参数摘要

- `meta.integrity.params_digest`：参数摘要（SHA256）
- `meta.execution.cmd_digest`：命令摘要（SHA256）
- `manifest.params_digest`：参数摘要（SHA256）

这些摘要可用于对比不同运行间的参数一致性。

## 错误码与退出码

### 错误码（ErrorCode，字符串常量）

| 错误码 | 说明 |
| --- | --- |
| `deps_missing` | 依赖缺失（ffmpeg/ffprobe 未找到） |
| `deps_broken` | 依赖损坏（ffmpeg/ffprobe 无法运行） |
| `deps_insufficient` | 依赖能力不足（缺少必需的编码器/解码器） |
| `input_not_found` | 输入文件不存在 |
| `input_invalid` | 输入文件无效 |
| `input_unsupported` | 输入格式不支持 |
| `output_not_writable` | 输出目录不可写 |
| `overwrite_conflict` | 输出已存在且未指定 `--overwrite` |
| `invalid_params` | 参数无效（如 bit depth 非 16） |
| `probe_failed` | ffprobe 探测失败 |
| `convert_failed` | ffmpeg 转换失败 |
| `no_audio_stream` | 无可用音频流（视频无音轨） |
| `invalid_stream_selection` | 音轨选择无效（指定的 index/language 不存在） |
| `internal_error` | 内部错误（未预期的异常） |

### 退出码（ExitCode，整数）

| 退出码 | 说明 | 适用场景 |
| --- | --- | --- |
| 0 | 成功 | 全部成功 |
| 1 | 部分失败（批处理）或一般失败（单文件） | 批处理存在失败文件；单文件处理失败 |
| 2 | 依赖缺失 | ffmpeg/ffprobe 缺失或不可用 |
| 10 | 输入不存在 | 输入文件不存在 |
| 11 | 输出不可写 | 输出目录不可写 |
| 12 | 覆盖冲突 | 输出已存在且未指定 `--overwrite` |
| 13 | 参数无效 | 参数值不合法（如 bit depth 非 16） |
| 20 | 探测失败 | ffprobe 失败且无法继续（仅当必需时） |
| 21 | 转换失败 | ffmpeg 转换失败 |
| 22 | 无音频流或音轨选择无效 | 视频无音轨或指定音轨不存在 |
| 99 | 内部错误 | 未预期的异常 |

### 批处理退出码规则

- **0**：全部成功
- **1**：存在失败（部分或全部失败）
- **2**：依赖缺失（批处理开始前检查，直接退出）

## 离线策略

### 不联网承诺

Repo1 严格遵循离线可用原则：
- **不联网**：不调用任何外部 API
- **不下载**：不自动下载任何文件（包括模型、权重、配置文件等）
- **不缓存**：不维护任何在线缓存

### 依赖安装

所有依赖需用户自行安装：
- **Python 包**：通过 `pip install -e .` 安装
- **ffmpeg/ffprobe**：需单独安装（见"快速开始"章节）

### 后续模块说明

Repo2 和 Repo3 可能涉及模型下载，但 Repo1 不负责这些操作。

## 故障排查

### ffmpeg/ffprobe 缺失

**症状：**
- `check-deps` 失败
- 错误码：`deps_missing`
- 退出码：2

**解决方法：**
1. 安装 ffmpeg（见"快速开始"章节）
2. 确保 `ffmpeg` 和 `ffprobe` 在 PATH 中
3. 运行 `onepass-ingest check-deps` 验证

### 视频无音轨

**症状：**
- 错误码：`no_audio_stream`
- 退出码：22
- meta.json 中 `errors` 包含 `no_audio_stream`

**解决方法：**
1. 检查视频文件是否包含音轨：`ffprobe input.mp4`
2. 如果视频确实无音轨，需要先提取或添加音轨
3. 如果视频有多个音轨，使用 `--audio-stream-index` 或 `--audio-language` 指定

### 目标目录无写权限

**症状：**
- 错误码：`output_not_writable`
- 退出码：11

**解决方法：**
1. 检查目标目录权限：`ls -ld <out-root>`
2. 确保有写权限：`chmod u+w <out-root>`
3. 或选择其他可写目录

### 转换失败

**症状：**
- 错误码：`convert_failed`
- 退出码：21
- meta.json 中 `errors` 包含详细错误信息

**解决方法：**
1. 查看 `convert.log`：`cat <workdir>/convert.log`
2. 查看全局日志：`cat <out-root>/ingest.log`（批处理模式）
3. 检查输入文件是否损坏：`ffprobe input.mp3`
4. 检查 ffmpeg 版本是否支持所需编解码器：`ffmpeg -codecs`

### 编码问题

**症状：**
- 转换成功但输出音频异常
- `output.actual_audio` 与 `output.expected_audio` 不一致

**解决方法：**
1. 检查 `convert.log` 中的警告信息
2. 验证 ffmpeg 版本：`ffmpeg -version`
3. 检查输入文件编码：`ffprobe input.mp3`

### 覆盖冲突

**症状：**
- 错误码：`overwrite_conflict`
- 退出码：12

**解决方法：**
1. 使用 `--overwrite` 允许覆盖：`onepass-ingest ingest input.mp3 --out out/demo --overwrite`
2. 或选择不同的输出目录

### 参数无效

**症状：**
- 错误码：`invalid_params`
- 退出码：13

**解决方法：**
1. 检查参数值是否合法（如 bit_depth 必须为 16）
2. 查看 CLI help：`onepass-ingest ingest --help`
3. 检查配置文件格式是否正确（YAML）

## 开发与测试

### 运行测试

```bash
# 运行所有测试
pytest -q

# 运行特定测试文件
pytest tests/test_schema_meta_valid.py

# 显示详细输出
pytest -v

# 使用 Makefile
make test
```

### 测试工具

测试使用 `tests/conftest.py` 提供的工具函数：
- `require_ffmpeg_ffprobe()`：自动跳过需要 ffmpeg/ffprobe 的测试
- `gen_sine_audio()`：生成测试音频文件
- `gen_video_with_audio()`：生成测试视频文件
- `ffprobe_summary()`：读取媒体文件摘要

### 快速验证

使用 `scripts/dev_smoke.py` 进行快速验证：

```bash
python scripts/dev_smoke.py
```

该脚本会：
1. 检查依赖（check-deps）
2. 生成 1 秒测试音频（使用 ffmpeg）
3. 运行 ingest 到 `out/smoke_workdir`
4. 打印输出文件列表和 meta.json 摘要

### Makefile 任务

```bash
# 运行测试
make test

# 检查依赖和 CLI
make check

# 创建虚拟环境（可选）
make venv
```

### Schema 校验

测试包含 schema 校验：
- `test_schema_meta_valid.py`：验证 meta.json 结构
- `test_schema_manifest_lines_valid.py`：验证 manifest.jsonl 结构

Schema 文件位于 `schemas/` 目录：
- `meta.v1.schema.json`：meta.json 的 JSON Schema
- `manifest.v1.schema.json`：manifest.jsonl 的 JSON Schema
- `manifest.plan.v1.schema.json`：manifest.plan.jsonl 的 JSON Schema

## 路线图

### 已完成（R1-R10）

- R1-R3：基础 ingest 功能、meta.json schema v1、稳定字段与 probe 逻辑
- R4：真实转码与 actual_audio 填充、日志与校验完善
- R5：视频输入支持、音轨选择策略
- R6：批处理、参数优先级、可复现性增强
- R7：normalize 功能、dry-run 统一、执行信息记录
- R8：统一错误模型、日志体系、批处理鲁棒性
- R9：测试体系完善、schema 校验、可复现性测试
- R10：文档完善、示例、版本策略、接口稳定性声明

### 未来可能扩展点

- 更丰富的 normalize 策略（多遍处理、不同目标响度等）
- 更严格的 schema 校验（运行时验证）
- 与上层总控仓库的集成方式（统一配置、统一日志等）
- 性能优化（并行处理、增量更新等）

**注意：这些扩展点仅为可能方向，不构成承诺。**

## CLI 命令参考

### check-deps

检查本地依赖（ffmpeg/ffprobe）。

```bash
onepass-ingest check-deps [--json] [--verbose] [--log-file <path>]
```

### ingest

单文件或目录批处理 ingest。

```bash
# 单文件模式
onepass-ingest ingest <input> --out <workdir> [options]

# 目录模式
onepass-ingest ingest <input_dir> --out-root <out_root> [options]
```

**常用选项：**
- `--sample-rate <int>`：采样率
- `--channels <int>`：声道数
- `--bit-depth <int>`：位深（仅支持 16）
- `--normalize/--no-normalize`：启用/禁用响度归一化
- `--audio-stream-index <int>`：指定音轨索引
- `--audio-language <str>`：指定音轨语言
- `--overwrite`：允许覆盖已存在输出
- `--recursive/--no-recursive`：递归/非递归扫描目录
- `--ext <exts>`：扩展名过滤（逗号分隔）
- `--continue-on-error/--fail-fast`：错误处理策略
- `--dry-run`：仅规划不转码
- `--json`：输出 meta.json 到 stdout（仅单文件模式）
- `--verbose`：启用详细日志
- `--log-file <path>`：指定日志文件路径
- `--config <path>`：指定配置文件路径

### meta

仅生成 meta.json，不进行转码。

```bash
onepass-ingest meta <input> --out <workdir> [--json] [--verbose] [--log-file <path>]
```

完整帮助信息请运行：`onepass-ingest <command> --help`

## 验收命令

以下命令可用于验证安装和功能：

```bash
# 环境准备
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# 检查依赖
onepass-ingest check-deps --json

# 单文件 ingest（需要准备测试文件）
onepass-ingest ingest <some_input> --out out/test_workdir
onepass-ingest ingest <some_input> --out out/norm_off --no-normalize
onepass-ingest ingest <some_input> --out out/norm_on --normalize
onepass-ingest ingest <some_input> --out out/dry_single --dry-run

# 目录批处理（需要准备测试目录）
onepass-ingest ingest <input_dir> --out-root out/dry_batch --dry-run
onepass-ingest ingest <input_dir> --out-root out/batch_demo

# 查看输出
cat out/batch_demo/manifest.jsonl | head
ls out/batch_demo/ingest.log

# 运行测试
pytest -q
make test
python scripts/dev_smoke.py
```

## 相关文档

- `examples/README.md`：示例文件说明
- `examples/commands.md`：常用命令组合
- `CHANGELOG.md`：变更记录
- `VERSIONING.md`：版本策略说明
- `schemas/`：Schema 文件目录
