# 动态信息图 Remotion 渲染器

此目录只负责动态信息图，不替换标准白板渲染器。

正式渲染必须先完成本地 Whisper.cpp token 级对齐，并生成独立的 `phrase-timeline.json`。内容模型随后只引用短语编号；Remotion PPT 规格先于插图生成。知识元素在对应语音帧之前不可见；对齐覆盖率不达标时任务失败，不允许退回按字数或页面时长平均估算。

清单页的 `relationshipType` 为 `none`，不会绘制箭头。只有原文明确表达步骤或因果关系时，渲染器才允许显示方向连接。

首次运行会通过 Remotion 安装器准备当前平台对应的 Whisper.cpp 1.5.5 二进制和 multilingual `medium` 模型。严格中文旁白对齐优先保证准确率；资源受限时可通过 `INFOGRAPHIC_WHISPER_MODEL=small` 改用较小模型。

项目当前固定使用 Remotion 4.0.515。macOS 15 及更高版本适合运行当前 Remotion 视频渲染链；若后续升级 Remotion，请重新验证 macOS 视频渲染。

安装与检查：

```bash
npm install
npm run build
```

正式时间约束见 [`../docs/semantic-timing-contract.md`](../docs/semantic-timing-contract.md)。所有 Remotion 包使用完全相同的固定版本，不要只升级其中一个包。
