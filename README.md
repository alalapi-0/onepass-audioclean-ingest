# OnePass AudioClean Ingest (R8)

## 目标与范围
- 提供音频清洗流水线的输入标准化与元数据生成入口骨架。
- 仅聚焦 ingest：不做分段、不做 ASR、不做口误检测、不做剪辑，不引入任何联网或模型下载逻辑。
- 默认离线可用，依赖仅限 Python 包与本机可用的 ffmpeg/ffprobe。

## R8 范围
- 统一错误模型：新增 `errors.py` 模块，定义统一的错误码常量（ErrorCode）和退出码（ExitCode），全仓库使用同一套错误处理体系。
- 统一日志体系：支持 `--verbose`（提升到 DEBUG 级别）和 `--log-file`（输出全局日志文件），批处理默认写入 `<out-root>/ingest.log`。
- 批处理鲁棒性增强：`--continue-on-error` 默认开启，失败不影响后续文件；`--fail-fast` 遇到失败立即终止；退出码规则明确（0=全部成功，1=存在失败，2=deps_missing）。
- 错误与警告区分：meta.json 新增 `warnings` 字段，区分不影响处理的警告（如输出 probe 失败但转换成功）与阻止处理的错误。
- manifest.jsonl 增强：新增 `error_messages`、`warning_codes`、`warning_messages`、`meta_json_path` 字段，错误信息更可读。
- 错误详情控制：使用 `safe_detail()` 函数控制 meta.json 中错误详情的体积，避免大段 stderr 塞进 meta。

## R7 范围（历史）
- 保留单文件 ingest 与目录批处理，并落地 normalize 功能：默认关闭，开启后使用固定的单遍 `loudnorm` 滤镜，记录 filtergraph 与参数。
- 参数来源可追溯：meta.json 写入 `params_sources`，指明每个关键参数来自 default/config/cli；`params.normalize_config` 固定记录滤镜配置。
- dry-run 统一：单文件模式生成 meta.json（planned 状态，`execution.planned=true`），不写 audio.wav/convert.log；目录模式写 `manifest.plan.jsonl`，只输出计划。
- meta.json 可复现性增强：新增 `execution`（ffmpeg_cmd、ffmpeg_cmd_str、ffmpeg_filtergraph、cmd_digest、planned）与 `integrity.params_digest`。
- manifest 计划文件：dry-run 目录模式写入 `manifest.plan.jsonl`（schema_version=`manifest.plan.v1`），每行 status=planned 并包含 workdir 规划。

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
用途：检查本机是否具备最小可用的 ffmpeg/ffprobe，并输出版本与能力探测结果。支持 `--json`、`--verbose` 和 `--log-file`，退出码 0/2/3/4 与 R2 保持一致。

### meta（R4，生成 meta.json 不转码）
用途：仅生成 `meta.json`（不做转码），可在后续流水线中复用。

用法示例：

```bash
onepass-ingest meta <input> --out <workdir>
onepass-ingest meta input.wav --out out/input__hash --json
onepass-ingest meta input.wav --out out/input__hash --verbose --log-file meta.log
```

行为与退出策略：

- workdir 不存在会自动创建；创建失败退出码 11。
- 其它失败（如 ffprobe 缺失、输入不存在）会记录到 `meta.errors`，依然写出 meta.json 并返回 0，方便流水线继续。
- `--json` 会把生成的 meta 内容输出到 stdout，便于调试。
- `--verbose` 启用 DEBUG 级别日志。
- `--log-file` 指定日志文件路径。

### ingest（R6，单文件或目录）
用途：将输入音频或视频转换为标准 PCM s16le wav，生成 meta.json 与 convert.log；目录模式会为每个媒体生成独立 workdir 并汇总 manifest。

用法示例：

```bash
# 单文件模式：指定 --out
onepass-ingest ingest input.mp3 --out out/demo_workdir
onepass-ingest ingest input.wav --out out/demo_workdir --sample-rate 22050 --channels 1 --overwrite --json

# 目录模式：指定 --out-root（必填），默认递归扫描
onepass-ingest ingest data/raw --out-root out/batch --recursive
onepass-ingest ingest data/raw --out-root out/batch --ext mp3,wav,mp4 --fail-fast
# dry-run：只规划 workdir 和 manifest.plan.jsonl，不转码
onepass-ingest ingest data/raw --out-root out/batch --dry-run
# 指定日志文件
onepass-ingest ingest data/raw --out-root out/batch --log-file custom.log
# 启用详细日志
onepass-ingest ingest data/raw --out-root out/batch --verbose
```

行为与退出策略：

- 依赖检查：批处理开始前检查 `check-deps`，若 ffmpeg/ffprobe 缺失或不可用，退出码 2 并写入 manifest 说明 deps 错误。单文件模式若 deps 缺失，退出码 2。
- 输入缺失：记录到 meta.errors，退出码 10。目录模式下单个文件缺失记为 failed，其余继续（除非 `--fail-fast`）。
- bit depth 仅允许 16；其它值会记录错误并退出码 13。
- 默认不覆盖既有输出；如 workdir 内已有 `audio.wav`/`meta.json`/`convert.log`，需显式 `--overwrite`，否则退出码 12。
- 转换失败记录 stderr 到 meta.errors 和 convert.log，退出码 21；输出 ffprobe 失败但文件已生成时记录为 warning（不影响退出码）。
- `--continue-on-error/--fail-fast`：默认 continue-on-error，遇失败仍写 manifest 并处理后续；fail-fast 时第一条失败后立即停止，退出码 1。
- 批处理退出码：全部成功=0，存在失败=1，deps_missing=2。
- `--json` 仅适用于单文件模式，打印 meta.json 内容到 stdout（仅 JSON）。
- `--verbose` 启用 DEBUG 级别日志。
- `--log-file` 指定全局日志文件路径；批处理模式若不指定，默认写入 `<out-root>/ingest.log`。
- normalize：默认关闭，开启后使用固定单遍滤镜 `loudnorm=I=-16:LRA=11:TP=-1.5:linear=true:print_format=summary`，模式名 `loudnorm_r7_v1`，配置写入 `meta.params.normalize_config`。启用后会改变波形，可复现性依赖相同的 ffmpeg 版本与滤镜参数。

#### Dry-run 行为（R7）
- 单文件：`--dry-run` 时仅写 meta.json（status=planned），不生成 audio.wav/convert.log，`meta.output.actual_audio=null`，`meta.execution.planned=true` 仍记录计划中的 ffmpeg 命令与 filtergraph。
- 目录模式：`--dry-run` 时不创建各 workdir，不写 meta.json，`--out-root` 下写入 `manifest.plan.jsonl`（schema_version=`manifest.plan.v1`，status=planned），列出 workdir 规划与路径。

### 视频输入（R5）
- 支持 mp4/mkv/mov（及其它 ffmpeg 支持的常见容器）。
- 默认仅抽取音频轨道再转 WAV，不做分段/ASR/剪辑。
- 若视频不存在音轨，ingest 失败，依然写出 meta.json 并记录 `no_audio_stream`。

### 音轨选择策略
- CLI 增强：
  - `--audio-stream-index <int>`：指定 ffprobe 的音频 stream index。
  - `--audio-language <str>`：按 language tag 优先选择（可选）。
- 默认 auto 逻辑（固定排序，写入代码注释与本节）：
  1. 若指定 language 且存在匹配，则在匹配集合中选择质量最优音轨。
  2. 否则按质量排序：`channels` 降序、`sample_rate` 降序、`bit_rate` 降序；使用原始顺序打破并列。
  3. 选中的 stream index 写入 `probe.input_ffprobe.selected_audio_stream`，并在转码时通过 `-map 0:<index>` 指定。
  4. 未找到音轨或 index/language 无效时，记录错误并返回对应退出码（12 或 13）。

## 配置文件
- 位置：`configs/default.yaml`
- 格式选择：采用 YAML，原因是配置层级清晰、易读且便于后续扩展复杂结构。
- 默认字段：
  - `sample_rate: 16000`
  - `channels: 1`
  - `bit_depth: 16`
  - `normalize: false`
- 约定：未来 CLI 参数将覆盖配置文件中的值；配置加载将优先读取默认配置，再合并用户传入的路径。

### 参数覆盖与优先级（R6）
优先级：CLI 显式参数 > `--config` 配置文件 > `configs/default.yaml` > 内置默认。
- 目录模式下 workdir 命名不受配置影响，始终按固定规则计算。
- 覆盖项：`--sample-rate`、`--channels`、`--bit-depth`（仅 16）、`--normalize/--no-normalize`、`--audio-stream-index`、`--audio-language` 等均可覆盖配置。
- 元信息追踪：最终合并的每个参数来源写入 `meta.params_sources`（枚举 default/config/cli），便于复现与审计；normalize 的固定配置保存在 `meta.params.normalize_config`。

## 输出目录约定（workdir）
- 默认输出根目录：`./out`（目录模式需要显式 `--out-root`）。
- 单输入文件：用户指定 `--out`，仍生成 `audio.wav`/`meta.json`/`convert.log`。
- 目录模式：每个输入文件对应独立 workdir，命名规则固定且不可被配置覆盖：
  - 形如 `<safe_stem>__<id>`，safe_stem 为文件名去扩展名后仅保留 `[a-zA-Z0-9._-]`，超长截断至 60 字符。
  - `<id>` = `sha256(relpath + "\n" + size_bytes)[:12]`，其中 relpath 为相对输入根目录的 POSIX 路径，size_bytes 来自当前文件大小。
  - 同一机器、同一输入根目录与文件大小下，workdir 名称稳定，不会因重新运行而覆盖；移动文件到其他目录时 id 会改变，这是为避免跨目录冲突的取舍。
  - meta.json 增补 `output.work_id`、`output.work_key` 记录上述规划依据，manifest 中也携带 workdir。
- workdir 内容固定：
  - `audio.wav`：标准化后的音频（PCM s16le，固定 `-fflags +bitexact -flags:a +bitexact`）。
  - `meta.json`：元数据，`output.actual_audio` 由 ffprobe 实测填充。
  - `convert.log`：包含时间戳、输入/输出路径、完整 ffmpeg 命令、stdout/stderr。

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
| `params_sources` | 记录每个参数的来源：`default` / `config` / `cli` |
| `tooling` | ffmpeg/ffprobe 探测信息，Python 运行时信息 |
| `probe` | 通过 ffprobe 获取的媒体摘要，附 warnings（含音轨列表、选中音轨、是否含视频） |
| `output` | workdir 相对路径、文件名、预期输出参数（actual_audio 在 R4 填充） |
| `execution` | ffmpeg 命令记录：结构化命令数组、可复制命令行、filtergraph（如有）、cmd_digest、planned 标记 |
| `integrity` | meta/audio 的可选 sha256 摘要（R4+ 补全），并包含 `params_digest` 便于对比参数一致性 |
| `errors` | 结构化错误列表（包含 code/message/hint/detail） |
| `warnings` | 结构化警告列表（R8 新增，格式与 errors 相同） |
| `stable_fields` | 列出核心与非核心字段路径及说明 |

核心字段列表和规则同时写入 `meta.json.stable_fields`，在自动化校验或回归测试时使用。

命令记录与摘要：
- `execution.ffmpeg_cmd` / `ffmpeg_cmd_str`：结构化与可直接复制的 ffmpeg 命令，dry-run 也会生成计划命令。
- `execution.ffmpeg_filtergraph`：若启用 normalize 则记录固定 loudnorm filtergraph，否则为 null。
- `execution.cmd_digest`：对命令列表与 filtergraph 的 sha256 摘要，便于比对复现。
- `integrity.params_digest`：对合并后的参数（含 normalize_config 与 ffmpeg_extra_args）的 sha256 摘要。

`probe.input_ffprobe`（R5）摘要字段：
- `has_video`：是否探测到视频轨道。
- `audio_streams`：音轨列表，包含 `index/codec_name/sample_rate/channels/bit_rate/channel_layout/language`。
- `video_streams`：视频轨道列表（轻量字段：index/codec/width/height/r_frame_rate）。
- `selected_audio_stream`：最终用于转码的音轨摘要，若未找到或指定无效则为 null。

## manifest.jsonl（R8）
- 目录模式下，`--out-root` 下生成 `manifest.jsonl`；dry-run 模式写入 `manifest.plan.jsonl`（schema_version=`manifest.plan.v1`，status 固定为 planned，不落盘 workdir）。
- 每行一条 JSON，不包裹数组，UTF-8 换行分隔，schema_version 固定为 `manifest.v1` 或 `manifest.plan.v1`。
- 关键字段：
  - `input`: `{path, relpath, ext, size_bytes}`
  - `output`: `{workdir, audio_wav, meta_json, convert_log, work_id, work_key}`
  - `status`: `success` | `failed` | `planned`，`exit_code` 保留单文件退出码。
  - `error_codes`: 数组，错误码列表（如 `["convert_failed", "probe_failed"]`）。
  - `error_messages`: 数组，简短错误消息列表（每条最多 200 字符）。
  - `warning_codes`: 数组，警告码列表（R8 新增）。
  - `warning_messages`: 数组，简短警告消息列表（R8 新增）。
  - `errors_summary`: 字符串，所有错误消息的摘要（分号分隔）。
  - `meta_json_path`: 字符串或 null，meta.json 的绝对路径（若存在，R8 新增）。
  - `log_file`: 字符串或 null，全局日志文件路径（可选，R8 新增）。
  - `started_at` / `ended_at` / `duration_ms`: 处理时间戳。
  - `params_digest`: 将 IngestParams 排序序列化后的 sha256，用于复现对比。
- 样例：
  - `{"schema_version":"manifest.v1","input":{"relpath":"a.mp3",...},"output":{"workdir":"out/batch/a__1ab2c3d4e5f6",...},"status":"success","exit_code":0,"error_codes":[],"error_messages":[],"warning_codes":[],"warning_messages":[],...}`
  - `{"schema_version":"manifest.v1","input":{"relpath":"bad.mp3",...},"status":"failed","exit_code":21,"error_codes":["convert_failed"],"error_messages":["ffmpeg conversion failed (code=1)"],...}`
  - `{"schema_version":"manifest.plan.v1","input":{"relpath":"a.wav",...},"status":"planned","exit_code":null,...}`

## 日志体系（R8）

### Console 日志
- 默认级别：INFO
- `--verbose`：提升到 DEBUG 级别
- 格式：`%(asctime)s [%(levelname)s] %(name)s: %(message)s`

### 文件日志
- `--log-file <path>`：指定全局日志文件路径
- 批处理模式：若不指定 `--log-file`，默认写入 `<out-root>/ingest.log`
- 文件日志级别：始终为 DEBUG（包含所有信息）
- 格式：与 console 相同

### convert.log
- 每个 workdir 一份，记录该文件的 ffmpeg 命令与 stderr/stdout
- 位置：`<workdir>/convert.log`
- 用途：用于调试单个文件的转换问题

### ingest.log（批处理）
- 全局日志文件，记录整个批处理过程的日志
- 位置：`<out-root>/ingest.log`（默认）或 `--log-file` 指定
- 用途：用于追踪批处理整体进度和错误

## 开发规范
- 日志：使用标准库 `logging`，统一入口在 `onepass_audioclean_ingest.logging_utils.setup_logging` 和 `get_logger`。
- 错误码：统一使用 `errors.ErrorCode` 和 `errors.ExitCode`，全仓库保持一致。
- Schema：meta.json v1 的 schema 固化在 `schemas/meta.v1.schema.json`，CLI 可使用该文件进行验证或回归测试。

## 输出结构
给定 `--out <workdir>`：

- `<workdir>/audio.wav`：转码后的标准化音频（PCM s16le，采样率/声道由参数决定）。
- `<workdir>/meta.json`：完整元数据，包含输入/输出探测信息、参数、errors/warnings。
- `<workdir>/convert.log`：ffmpeg 命令与 stdout/stderr，结尾带换行，便于审计和排错。

## 可复现性策略（R6）
- ffmpeg 输出使用 `-fflags +bitexact -flags:a +bitexact`，并移除元数据 `-map_metadata -1`，减少平台差异。
- 输出编码固定 `-c:a pcm_s16le`，仅允许 bit depth 16。
- 采样率/声道由参数固定，默认 16kHz/单声道。
- normalize 开启时使用固定滤镜 `loudnorm=I=-16:LRA=11:TP=-1.5`，filtergraph 记录在 `params.normalize_mode`。
- convert.log 记录完整命令与 stderr，方便复现与对比。
- 目录批处理的 workdir 命名依赖 `relpath + size_bytes` 的 sha256 哈希；在同一输入根目录下重复执行可稳定复现输出路径，跨目录移动会改变哈希以避免覆盖。

## 错误码与退出码（R8）

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

### 退出码兼容性说明（R4-R7 迁移）

R8 对部分退出码进行了调整以保持一致性：

- `NO_SUPPORTED_STREAM`：从 12 调整为 22
- `INVALID_STREAM_SELECTION`：从 13 调整为 22（与 no_audio_stream 合并）
- `CONVERT_FAILED`：从 20 调整为 21
- `PROBE_FAILED`：保持 20（仅当必需且无法继续时）
- `INVALID_PARAMS`：从 30 调整为 13
- `OVERWRITE_CONFLICT`：新增 12（之前为 11 的一部分）

## 批处理失败策略（R8）

### continue-on-error（默认）
- 遇到失败时继续处理后续文件
- 每个文件的处理结果都写入 manifest.jsonl
- 最终退出码：0（全部成功）或 1（存在失败）

### fail-fast
- 遇到第一个失败立即停止
- 已处理的文件结果仍写入 manifest.jsonl
- 退出码：1

### 批处理退出码规则
- 0：全部成功
- 1：存在失败（部分或全部失败）
- 2：依赖缺失（批处理开始前检查，直接退出）

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
onepass-ingest ingest <some_input> --out out/norm_off --no-normalize
onepass-ingest ingest <some_input> --out out/norm_on --normalize
onepass-ingest ingest <some_input> --out out/dry_single --dry-run
onepass-ingest ingest <input_dir> --out-root out/dry_batch --dry-run
onepass-ingest ingest <input_dir> --out-root out/batch_demo
cat out/batch_demo/manifest.jsonl | head
ls out/batch_demo/ingest.log
pytest -q
```
