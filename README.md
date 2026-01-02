# OnePass AudioClean Ingest (R6)

## 目标与范围
- 提供音频清洗流水线的输入标准化与元数据生成入口骨架。
- 仅聚焦 ingest：不做分段、不做 ASR、不做口误检测、不做剪辑，不引入任何联网或模型下载逻辑。
- 默认离线可用，依赖仅限 Python 包与本机可用的 ffmpeg/ffprobe。

## R6 范围
- 保留单文件 ingest 能力，并新增目录批处理入口，支持递归扫描、扩展名白名单与可选 dry-run。
- 批处理输出根目录下写入 `manifest.jsonl`，逐行记录成功/失败/计划状态，含 workdir、输出路径、时间戳与错误摘要。
- 固化 workdir 命名规则（安全化 stem + 稳定哈希），避免重名覆盖并兼顾可复现性。
- 新增 `--continue-on-error/--fail-fast` 控制批处理失败策略，默认不中断，遇失败整体退出码为 1。
- 默认扩展名白名单覆盖常见音频+视频（mp3/m4a/wav/flac/ogg/opus/aac/mp4/mkv/mov），可通过 `--ext` 覆盖。

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
```

行为与退出策略：

- 依赖检查：执行前调用 `check-deps`，若 ffmpeg/ffprobe 缺失或不可用，退出码 2 并尽量写出 meta.json。目录模式依然逐文件写 meta.json；最终退出码为 1 若任一失败（除非全部成功）。
- 输入缺失：记录到 meta.errors，退出码 10。目录模式下单个文件缺失记为 failed，其余继续（除非 `--fail-fast`）。
- bit depth 仅允许 16；其它值会记录错误并退出码 30。
- 默认不覆盖既有输出；如 workdir 内已有 `audio.wav`/`meta.json`/`convert.log`，需显式 `--overwrite`。
- 转换失败记录 stderr 到 meta.errors 和 convert.log，退出码 20；输出 ffprobe 失败但文件已生成时退出码 21。
- `--continue-on-error/--fail-fast`：默认 continue，遇失败仍写 manifest 并处理后续；fail-fast 时第一条失败后立即停止，退出码 1。
- `--json` 仅适用于单文件模式，打印 meta.json 内容到 stdout（仅 JSON）。
- normalize：沿用固定滤镜 `loudnorm=I=-16:LRA=11:TP=-1.5`；如未开启则不加滤镜，meta.params.normalize_mode 置为 null。

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
| `tooling` | ffmpeg/ffprobe 探测信息，Python 运行时信息 |
| `probe` | 通过 ffprobe 获取的媒体摘要，附 warnings（含音轨列表、选中音轨、是否含视频） |
| `output` | workdir 相对路径、文件名、预期输出参数（actual_audio 在 R4 填充） |
| `integrity` | meta/audio 的可选 sha256 摘要（R4+ 补全） |
| `errors` | 结构化错误列表（包含 code/message/hint/detail） |
| `stable_fields` | 列出核心与非核心字段路径及说明 |

核心字段列表和规则同时写入 `meta.json.stable_fields`，在自动化校验或回归测试时使用。

`probe.input_ffprobe`（R5）摘要字段：
- `has_video`：是否探测到视频轨道。
- `audio_streams`：音轨列表，包含 `index/codec_name/sample_rate/channels/bit_rate/channel_layout/language`。
- `video_streams`：视频轨道列表（轻量字段：index/codec/width/height/r_frame_rate）。
- `selected_audio_stream`：最终用于转码的音轨摘要，若未找到或指定无效则为 null。

## manifest.jsonl（R6）
- 目录模式下，`--out-root` 下生成 `manifest.jsonl`（dry-run 写入 `manifest.plan.jsonl`）。
- 每行一条 JSON，不包裹数组，UTF-8 换行分隔，schema_version 固定为 `manifest.v1`。
- 关键字段：
  - `input`: `{path, relpath, ext, size_bytes}`
  - `output`: `{workdir, audio_wav, meta_json, convert_log}`
  - `status`: `success` | `failed` | `planned`，`exit_code` 保留单文件退出码。
  - `error_codes` & `errors_summary`: 提取自 meta.errors 或内部错误。
  - `started_at` / `ended_at` / `duration_ms`: 处理时间戳。
  - `params_digest`: 将 IngestParams 排序序列化后的 sha256，用于复现对比。
- 样例：
  - `{"schema_version":"manifest.v1","input":{"relpath":"a.mp3",...},"output":{"workdir":"out/batch/a__1ab2c3d4e5f6",...},"status":"success","exit_code":0,...}`
  - `{"schema_version":"manifest.v1","input":{"relpath":"bad.mp3",...},"status":"failed","exit_code":20,"error_codes":["convert_failed"],...}`

## 开发规范
- 日志：使用标准库 `logging`，统一入口在 `onepass_audioclean_ingest.logging_utils.get_logger`，后续补充格式与级别配置。
- 错误码：`check-deps` 根据依赖状态返回 0/2/3/4；`ingest` 返回 R4 定义的退出码（见下文），失败也尽量写出 meta.json。
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

## 退出码

| 代码 | 说明 |
| --- | --- |
| 0 | 成功 |
| 2 | 依赖缺失或不可运行（ffmpeg/ffprobe） |
| 10 | 输入不存在或不可读取 |
| 12 | 无可用音频流（视频无音轨） |
| 13 | 音轨选择无效（指定的 index/language 不存在） |
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
onepass-ingest ingest <some_input> --out out/single_demo
onepass-ingest ingest <input_dir> --out-root out/batch_demo
pytest -q
```
