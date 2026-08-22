# 有温度出品｜白板声画工坊

> 把你的表达，画成一支会说话的白板视频。

**白板声画工坊**是一个本地运行的 AI 视频制作工作台。上传一段参考音频、粘贴中文文案，选择画面风格或提供人物与风格参考，系统会自动完成音色克隆、分镜、插画、手绘笔迹、字幕和音画合成，并导出 MP4。

![白板动画成片示例](examples/scene-01-monkey-mountain-banana-whiteboard.gif)

## 为什么做它

短视频创作里，真正耗时的往往不是写文案，而是把表达稳定地做成画面。本项目把这条链路收进一台电脑：素材、密钥、任务历史和成片默认都留在本地；同一局域网内的团队也能共用一条生产队列。

```text
参考音频 + 中文文案 +（可选）视觉/人物参考
                    ↓
音色克隆 → 文案分镜 → 统一插画 → 流式手绘 → 字幕与音画合成
                    ↓
                 MP4 成片
```

## 核心能力

| 能力 | 你得到什么 |
| --- | --- |
| 本地音色克隆 | 接入自己的 IndexTTS Gradio 或 FastAPI 服务，参考音频不离开本机目录。 |
| 11 种视觉风格 | 从极简白板、国风、手账到赛博霓虹；新增「纸感隐喻拼贴风」。 |
| 纸感隐喻拼贴 | 根据文案识别流程、因果、对比等结构，从本地 10 张视觉参考中选择 1–3 张辅助构图，而不是机械堆图标。 |
| 自定义参考 | 上传 1 张风格图，以及最多 5 个角色、每人 1–3 张参考图，让人物与画风贯穿全片。 |
| 准确中文重点词 | 每个分镜可本地叠加 4–10 字重点短语，避开图片模型生成中文时常见的乱码；可一键关闭。 |
| 可控成片节奏 | 支持 1–4 个分镜合并为一张图、字幕开关、笔身账号名及 4 档线条绘制量。 |
| 任务历史与复用 | 可命名任务、查看耗时和历史；成片可基于现有配音与分镜重新渲染，不重复调用模型与 TTS。 |
| 断点恢复 | 配音、分镜、图片、分段视频与最终合成都有检查点；重启服务或临时失败后可继续。 |
| 局域网协作 | 多台电脑共用队列、进度和历史；个人制作偏好保存在各自浏览器，不会互相覆盖。 |

## 画面风格

选择风格会同时影响配色、线条、材质与构图。预览图展示视觉方向，实际人物和场景仍会随文案生成。

| 风格 | 预览 | 适合内容 |
| --- | --- | --- |
| 极简粗线简笔白板风 | <img src="web/public/styles/minimal-whiteboard.webp" alt="极简粗线简笔白板风" width="120" /> | 知识讲解、个人表达、复盘总结 |
| 极简商务涂鸦风 | <img src="web/public/styles/business-doodle.webp" alt="极简商务涂鸦风" width="120" /> | 产品介绍、商业分析、项目汇报 |
| 暖米黄素描白板风 | <img src="web/public/styles/warm-pencil.webp" alt="暖米黄素描白板风" width="120" /> | 人物故事、个人成长、品牌叙事 |
| 粗线扁平国风卡通 | <img src="web/public/styles/guofeng-flat.webp" alt="粗线扁平国风卡通" width="120" /> | 传统文化、国风品牌、中文创意 |
| 爆款高热吸睛风 | <img src="web/public/styles/viral-pop.webp" alt="爆款高热吸睛风" width="120" /> | 短视频开场、强观点、热点表达 |
| 黑金科技发布会风 | <img src="web/public/styles/black-gold-tech.webp" alt="黑金科技发布会风" width="120" /> | AI、科技产品、发布会 |
| 清新治愈手账风 | <img src="web/public/styles/healing-journal.webp" alt="清新治愈手账风" width="120" /> | 情感、生活方式、自我成长 |
| 复古报纸拼贴风 | <img src="web/public/styles/retro-collage.webp" alt="复古报纸拼贴风" width="120" /> | 深度观点、文化内容、案例复盘 |
| **纸感隐喻拼贴风（新增）** | <img src="web/public/styles/paper-metaphor.png" alt="纸感隐喻拼贴风" width="120" /> | 价值观、关系、流程、复杂观点 |
| 3D 黏土趣味风 | <img src="web/public/styles/clay-3d.webp" alt="3D 黏土趣味风" width="120" /> | 亲子教育、轻量品牌、趣味科普 |
| 赛博霓虹漫画风 | <img src="web/public/styles/cyber-neon.webp" alt="赛博霓虹漫画风" width="120" /> | AI 趋势、数码科技、年轻化观点 |

## 新版本重点

这次版本把原先的单任务生成流程，升级为更适合稳定生产的本地工作台：

- **三级流水线队列**：最多 2 路独立语音节点、4 路模型调用；本地渲染在模型阶段结束后立即开始。
- **可靠的继续机制**：模型超时、限流、5xx、空图片或无效分镜会自动重试 3 次；仍失败时可以从断点继续。
- **重新渲染不重复花钱**：调整笔身文字、重点词、字幕或线条绘制量时，仅执行本地画线与合成。
- **更适合多人使用**：网页会显示共享任务和队列状态；任务上限为 20 个，避免机器被意外压垮。

## 环境要求

- Windows 10/11（当前一键启动与渲染路径面向 Windows）
- Python 3.11+
- Node.js 22.13+
- FFmpeg 与 **FFprobe** 已加入系统 `PATH`
- 可访问的 IndexTTS 2.5 服务（Gradio 或 FastAPI）
- OpenLux API Key，且有 GPT-5 与 GPT Image 2 的调用权限

确认音视频依赖可用：

```powershell
ffmpeg -version
ffprobe -version
```

> 当前渲染命令使用 Windows 虚拟环境路径；macOS / Linux 用户可自行适配 Python 路径后运行后端，暂不属于开箱即用支持范围。

## 5 分钟启动

在项目根目录执行一次安装：

```powershell
python scripts/prepare_env.py
.\.venv\Scripts\python.exe -m pip install -r webapp\requirements.txt
Push-Location web
npm ci
Pop-Location
```

然后任选一种方式启动：

```powershell
# 方式一：双击项目根目录的「启动白板工坊.bat」

# 方式二：PowerShell
.\start-webapp.ps1
```

脚本会启动前后端并打开 `http://127.0.0.1:13000/`，同时输出可供同一局域网设备访问的地址。

首次打开后，进入 **API 设置**，填写：

1. OpenLux API Key
2. 文本模型（默认 `gpt-5`）
3. 图片模型（默认 `gpt-image-2`）
4. 语音节点 1 地址与接口类型；如需并发克隆，可再填写语音节点 2

默认 Gradio 语音服务地址为 `http://127.0.0.1:7860`；FastAPI 服务通常使用 `8000` 端口。先点击“测试连接”，再提交任务。

## 使用方式

### 标准制作

1. 上传 10–30 秒、单人且噪声较少的参考音频。
2. 粘贴至少 10 个字的中文文案。
3. 选择风格与成片设置，点击“开始生成视频”。
4. 在制作进度区查看任务；完成后在线预览或下载 MP4。

### 自定义参考

适合固定 IP、故事角色或品牌化视觉：

1. 切换至“自定义参考”。
2. 上传一张风格参考图（控制配色、线条、材质和构图）。
3. 添加 1–5 个角色；每人填写名称与可选描述，并上传 1–3 张不同角度的参考图。
4. 系统会依据文案与角色名称安排每幕人物，不会直接复制风格参考图中的人物。

### 重新渲染与恢复

- **从断点继续**：用于调用失败或服务中断后的原任务恢复。
- **按当前设置重新渲染**：复用已生成的配音、分镜和原图，适合修改笔身文字、字幕、重点词或线条密度；不会再次请求 GPT-5、GPT Image 2 或 IndexTTS。

## 运行与数据

所有运行时文件都在 `.webapp/`：

```text
.webapp/
├── config.json          # 本机 API 与语音配置
├── preferences.json     # 旧版兼容偏好
└── jobs/<任务 ID>/       # 音频、分镜、图片、检查点、成片与任务元数据
```

密钥、参考音频、图片与成片不应提交到 Git。`.webapp/`、`.env*`、虚拟环境、`node_modules` 和构建产物均已被忽略。若曾误提交 API Key，请立即在服务商后台撤销并重新生成；只删除文件无法清除 Git 历史。

## 开发验证

```powershell
# 前端构建与页面验证
Push-Location web
npm test
Pop-Location

# 后端任务队列与恢复逻辑测试（依赖 ffprobe）
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## 项目结构

```text
├── assets/               # 画笔、视觉风格与参考素材
├── examples/             # 成片与场景示例
├── scripts/              # 白板渲染、重点文字和维护脚本
├── tests/                # 后端队列与断点恢复测试
├── web/                  # React + Vinext 前端
├── webapp/               # FastAPI 后端
├── start-webapp.ps1      # Windows 一键启动
└── SKILL.md              # SRT 白板动画工作流说明
```

## 许可证

本项目采用 [MIT License](LICENSE)。发现安全问题请不要先公开提交 Issue，详见 [SECURITY.md](SECURITY.md)。
