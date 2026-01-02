# Examples 目录说明

本目录包含 OnePass AudioClean Ingest 的使用示例和配置文件。

## 文件说明

- `README.md`：本文件，说明 examples 目录内容
- `commands.md`：常用命令组合，可直接复制粘贴使用
- `config.custom.yaml`：自定义配置示例
- `manifest_sample.jsonl`：manifest.jsonl 样例（精简版）

## 注意事项

- 所有示例文件均为纯文本，不包含真实音频文件
- 示例命令中的路径和文件名需根据实际情况调整
- 示例配置文件可直接使用，或根据需求修改

## 使用示例

### 1. 查看常用命令

```bash
cat examples/commands.md
```

### 2. 使用自定义配置

```bash
onepass-ingest ingest input.mp3 --out out/demo \
  --config examples/config.custom.yaml
```

### 3. 查看 manifest 样例

```bash
cat examples/manifest_sample.jsonl
```

## 更多信息

完整文档请参考项目根目录的 `README.md`。

