# 常用命令组合

本文档列出 OnePass AudioClean Ingest 的常用命令组合，可直接复制粘贴使用。

## 依赖检查

```bash
# 基本检查
onepass-ingest check-deps

# JSON 格式输出
onepass-ingest check-deps --json

# 详细输出
onepass-ingest check-deps --verbose
```

## 单文件 ingest

### 音频文件

```bash
# 基本用法（默认参数：16kHz 单声道）
onepass-ingest ingest input.mp3 --out out/demo_workdir

# 指定采样率和声道
onepass-ingest ingest input.wav --out out/demo_workdir \
  --sample-rate 22050 --channels 1

# 启用响度归一化
onepass-ingest ingest input.mp3 --out out/norm_workdir \
  --normalize

# 覆盖已存在输出
onepass-ingest ingest input.mp3 --out out/demo_workdir \
  --overwrite

# 输出 meta.json 到 stdout
onepass-ingest ingest input.mp3 --out out/demo_workdir \
  --json

# Dry-run（仅生成 meta.json，不转码）
onepass-ingest ingest input.mp3 --out out/dry_workdir \
  --dry-run
```

### 视频文件

```bash
# 从视频中提取音频
onepass-ingest ingest input.mp4 --out out/video_workdir

# 指定音轨索引
onepass-ingest ingest input.mkv --out out/video_workdir \
  --audio-stream-index 1

# 按语言选择音轨
onepass-ingest ingest input.mkv --out out/video_workdir \
  --audio-language eng

# 组合使用
onepass-ingest ingest input.mkv --out out/video_workdir \
  --audio-language jpn --sample-rate 44100 --channels 2
```

## 目录批处理

### 基本批处理

```bash
# 递归扫描所有支持的媒体文件
onepass-ingest ingest data/raw --out-root out/batch

# 非递归扫描（仅当前目录）
onepass-ingest ingest data/raw --out-root out/batch \
  --no-recursive

# 指定扩展名过滤
onepass-ingest ingest data/raw --out-root out/batch \
  --ext mp3,wav

# 仅处理视频文件
onepass-ingest ingest data/raw --out-root out/batch \
  --ext mp4,mkv,mov
```

### 错误处理策略

```bash
# 默认：遇到失败继续处理（推荐）
onepass-ingest ingest data/raw --out-root out/batch \
  --continue-on-error

# 遇到失败立即停止
onepass-ingest ingest data/raw --out-root out/batch \
  --fail-fast
```

### 日志与调试

```bash
# 启用详细日志
onepass-ingest ingest data/raw --out-root out/batch \
  --verbose

# 指定日志文件
onepass-ingest ingest data/raw --out-root out/batch \
  --log-file custom.log

# 组合使用
onepass-ingest ingest data/raw --out-root out/batch \
  --verbose --log-file debug.log
```

### Dry-run 批处理

```bash
# 仅生成 manifest.plan.jsonl，不创建 workdir
onepass-ingest ingest data/raw --out-root out/dry_batch \
  --dry-run

# 查看计划
cat out/dry_batch/manifest.plan.jsonl
```

## 使用配置文件

```bash
# 使用默认配置
onepass-ingest ingest input.mp3 --out out/demo

# 使用自定义配置
onepass-ingest ingest input.mp3 --out out/demo \
  --config examples/config.custom.yaml

# CLI 参数覆盖配置文件
onepass-ingest ingest input.mp3 --out out/demo \
  --config examples/config.custom.yaml \
  --sample-rate 44100
```

## 查看输出

```bash
# 查看 manifest.jsonl
cat out/batch/manifest.jsonl

# 查看前几行
head -n 5 out/batch/manifest.jsonl

# 查看成功记录
grep '"status":"success"' out/batch/manifest.jsonl

# 查看失败记录
grep '"status":"failed"' out/batch/manifest.jsonl

# 查看 meta.json
cat out/demo_workdir/meta.json

# 查看转换日志
cat out/demo_workdir/convert.log

# 查看批处理日志
cat out/batch/ingest.log
```

## 组合示例

### 完整批处理流程

```bash
# 1. 检查依赖
onepass-ingest check-deps

# 2. Dry-run 查看计划
onepass-ingest ingest data/raw --out-root out/batch \
  --dry-run --ext mp3,wav,mp4

# 3. 实际处理
onepass-ingest ingest data/raw --out-root out/batch \
  --ext mp3,wav,mp4 --verbose --log-file out/batch/ingest.log

# 4. 查看结果
cat out/batch/manifest.jsonl | grep '"status":"success"' | wc -l
```

### 高质量音频处理

```bash
# 44.1kHz 立体声，启用归一化
onepass-ingest ingest input.wav --out out/hq_workdir \
  --sample-rate 44100 --channels 2 --normalize
```

### 视频批量提取音频

```bash
# 从视频目录提取音频，选择英文音轨
onepass-ingest ingest videos/ --out-root out/video_audio \
  --ext mp4,mkv,mov --audio-language eng --recursive
```

## 故障排查命令

```bash
# 检查依赖
onepass-ingest check-deps --verbose

# 查看错误详情
cat out/demo_workdir/meta.json | jq '.errors'

# 查看转换日志
cat out/demo_workdir/convert.log

# 验证输出音频
ffprobe out/demo_workdir/audio.wav
```

## 注意事项

- 所有路径需根据实际情况调整
- 确保输入文件存在且可读
- 确保输出目录可写
- 批处理模式建议先使用 `--dry-run` 查看计划
- 大文件处理可能需要较长时间，建议使用 `--verbose` 查看进度

