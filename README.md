# OnePass AudioClean Ingest (R1)

## 目标与范围
- 提供音频清洗流水线的输入标准化与元数据生成入口骨架。
- 仅聚焦 ingest：不做分段、不做 ASR、不做口误检测、不做剪辑，不引入任何联网或模型下载逻辑。
- 默认离线可用，依赖仅限 Python 包与本机可用的 ffmpeg/ffprobe（R1 不调用 ffmpeg，只预留结构）。

## 非目标（R1）
- 不处理音频内容，不进行格式转换或标准化。
- 不生成 meta.json 内容，仅预留文件与路径约定。
- 不检查或下载外部依赖，不触发网络访问。

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
onepass-ingest ingest --help
```

R1 行为：
- `onepass-ingest check-deps` 输出 `check-deps: Not implemented in R1`，退出码 0。
- `onepass-ingest ingest` 输出 `ingest: Not implemented in R1`，退出码 0。

未来版本将扩展为真实的依赖检查（本机 ffmpeg/ffprobe）与 ingest 处理逻辑。

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
- 单输入文件生成一个 workdir，命名规则：`out/<input_stem>__<short_hash>/`。
  - `input_stem`：输入文件名去除扩展名。
  - `short_hash`：建议使用输入文件的绝对路径、文件大小、mtime 的稳定哈希，确保跨机器尽量可复现；如仅取绝对路径哈希，则同一文件在不同位置会生成不同 workdir，但能避免读取文件内容。R1 未实现哈希计算，未来版本定稿时需在 README 更新决定。
- workdir 内文件约定：
  - `audio.wav`：标准化后的音频（单声道、16 kHz、16-bit PCM 等，未来实现）。
  - `meta.json`：元数据（采样率、通道、转换摘要、后续 schema 将定义）。
  - `convert.log`：ffmpeg 调用日志（stdout/stderr 聚合）。
- 批量处理：每个输入文件对应独立 workdir，便于幂等执行与缓存。

## 开发规范（R1 占位）
- 日志：使用标准库 `logging`，统一入口在 `onepass_audioclean_ingest.logging_utils.get_logger`，后续补充格式与级别配置。
- 错误码：R1 所有子命令返回 0。未来在 `onepass_audioclean_ingest.constants` 中维护错误码枚举与文档。
- Schema：未来的 meta/schema 定义路径约定为 `onepass_audioclean_ingest/schemas/`（当前未创建），在 `constants.py` 中占位。

## 路线图（摘要）
- R2：实现依赖检查（ffmpeg/ffprobe）、基础音频探测与元数据收集。
- R3：实现音频标准化（采样率/通道/位深转换）、生成 `audio.wav` 与 `convert.log`。
- R4：完善 `meta.json` schema、错误码与日志格式；增加 CLI 参数覆盖配置。
- R5+：性能优化、批量处理、更多平台兼容测试。

## 验收命令
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
onepass-ingest --help
onepass-ingest check-deps
onepass-ingest ingest
pytest -q
```
