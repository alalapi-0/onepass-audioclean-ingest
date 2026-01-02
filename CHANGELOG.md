# 变更记录

本文档记录 OnePass AudioClean Ingest 的主要变更。

## R10 (2024-01-XX)

### 文档与接口稳定性

- **文档完善**：重构 README.md，增加完整的使用说明、故障排查、接口契约等章节
- **示例目录**：新增 `examples/` 目录，包含常用命令、配置文件示例、manifest 样例
- **版本策略**：新增 `VERSIONING.md`，明确 schema 版本策略与兼容性承诺
- **变更记录**：新增 `CHANGELOG.md`，记录 R1-R10 的主要变化
- **接口契约**：明确 Repo2/Repo3 依赖的字段和路径，承诺 workdir 结构不轻易改变

### 代码清理

- CLI help 文案优化，统一术语（input_file vs input_dir, out vs out_root）

## R9 (2024-01-XX)

### 测试体系完善

- 新增 `tests/conftest.py` 提供统一的测试工具函数（音频/视频生成、ffprobe 读取等）
- 所有测试自动检测并跳过缺失 ffmpeg/ffprobe 的情况
- 新增 `test_schema_meta_valid.py` 和 `test_schema_manifest_lines_valid.py`，验证 meta.json 和 manifest.jsonl 的结构与必需字段
- 新增 `test_dry_run_manifest_order_stable.py` 和 `test_workdir_id_stable_for_same_relpath_and_size.py`，确保批处理输出顺序稳定、workdir 命名稳定
- 新增 `test_video_ingest_records_selected_stream.py` 和 `test_error_codes_are_strings_and_known.py`，覆盖视频处理与错误码校验

### 开发者体验

- 新增 `Makefile` 提供常用命令（test/check）
- 新增 `scripts/dev_smoke.py` 用于快速验证安装
- 新增 `schemas/manifest.v1.schema.json` 用于 manifest.jsonl 校验

## R8 (2024-01-XX)

### 统一错误模型

- 新增 `errors.py` 模块，定义统一的错误码常量（ErrorCode）和退出码（ExitCode）
- 全仓库使用同一套错误处理体系
- 错误与警告区分：meta.json 新增 `warnings` 字段

### 统一日志体系

- 支持 `--verbose`（提升到 DEBUG 级别）和 `--log-file`（输出全局日志文件）
- 批处理默认写入 `<out-root>/ingest.log`

### 批处理鲁棒性增强

- `--continue-on-error` 默认开启，失败不影响后续文件
- `--fail-fast` 遇到失败立即终止
- 退出码规则明确（0=全部成功，1=存在失败，2=deps_missing）

### manifest.jsonl 增强

- 新增 `error_messages`、`warning_codes`、`warning_messages`、`meta_json_path` 字段
- 错误信息更可读
- 使用 `safe_detail()` 函数控制 meta.json 中错误详情的体积

## R7 (2024-01-XX)

### Normalize 功能

- 默认关闭，开启后使用固定的单遍 `loudnorm` 滤镜
- 记录 filtergraph 与参数到 `meta.params.normalize_config`
- 模式名 `loudnorm_r7_v1`

### 参数来源可追溯

- meta.json 写入 `params_sources`，指明每个关键参数来自 default/config/cli
- `params.normalize_config` 固定记录滤镜配置

### Dry-run 统一

- 单文件模式生成 meta.json（planned 状态，`execution.planned=true`），不写 audio.wav/convert.log
- 目录模式写 `manifest.plan.jsonl`，只输出计划
- meta.json 可复现性增强：新增 `execution`（ffmpeg_cmd、ffmpeg_cmd_str、ffmpeg_filtergraph、cmd_digest、planned）与 `integrity.params_digest`

## R6 (2024-01-XX)

### 批处理功能

- 支持目录批处理，为每个输入文件生成独立 workdir
- 生成 manifest.jsonl 汇总处理结果
- workdir 命名规则固定：`<safe_stem>__<id>`，基于 relpath + size_bytes 的 sha256

### 参数优先级

- CLI 显式参数 > `--config` 配置文件 > `configs/default.yaml` > 内置默认
- 参数来源记录在 `meta.params_sources`

### 可复现性增强

- ffmpeg 输出使用 `-fflags +bitexact -flags:a +bitexact`，并移除元数据 `-map_metadata -1`
- 输出编码固定 `-c:a pcm_s16le`，仅允许 bit depth 16
- convert.log 记录完整命令与 stderr

## R5 (2024-01-XX)

### 视频输入支持

- 支持 mp4/mkv/mov 及其它 ffmpeg 支持的常见容器
- 默认仅抽取音频轨道再转 WAV
- 若视频不存在音轨，ingest 失败，依然写出 meta.json 并记录 `no_audio_stream`

### 音轨选择策略

- `--audio-stream-index <int>`：指定 ffprobe 的音频 stream index
- `--audio-language <str>`：按 language tag 优先选择
- 默认 auto 逻辑：按质量排序（channels 降序、sample_rate 降序、bit_rate 降序）
- 选中的 stream index 写入 `probe.input_ffprobe.selected_audio_stream`

## R4 (2024-01-XX)

### 真实转码

- 补齐真实转码与 actual_audio 填充
- 日志与校验完善

## R3 (2024-01-XX)

### meta.json schema v1

- 定义 meta.json schema v1
- 稳定字段与 probe 逻辑
- `meta` 子命令：仅生成 meta.json，不转码

## R2 (2024-01-XX)

### 依赖检查

- `check-deps` 子命令：检查本机是否具备最小可用的 ffmpeg/ffprobe
- 支持 `--json`、`--verbose` 和 `--log-file`
- 退出码 0/2/3/4

## R1 (2024-01-XX)

### 初始版本

- 基础 ingest 功能骨架
- 配置文件支持（YAML）
- 基础 CLI 接口

