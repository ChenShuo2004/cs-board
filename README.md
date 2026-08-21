# CS Board

> 把一段文案和你的声音，做成一支会说话的白板视频。

CS Board 是面向中文创作者的本地 AI 白板视频生成工具。上传一段参考音频、粘贴文案，选择画面风格后，它会完成音色克隆、分镜规划、插画生成、手绘笔迹、字幕与音画合成，导出 MP4 成片。

> 所有配置、参考音频和生成结果默认保存在你的电脑上，不会上传到本项目的服务器。

![CS Board 生成效果：猴子、山和香蕉的白板动画](examples/scene-01-monkey-mountain-banana-whiteboard.gif)

## 它适合谁

- 想把口播文案快速做成知识科普、观点表达或课程宣传视频的创作者
- 有固定声音与个人表达风格，希望批量制作白板动画内容的人
- 希望把 AI 视频制作流程放在本地掌控，而不是把素材交给陌生平台的团队

## 从文案到成片

```text
参考音频 + 中文文案
        ↓
克隆音色 → 拆分分镜 → 生成插画 → 绘制白板笔迹 → 合成配音与字幕
        ↓
      MP4 视频
```

## 核心能力

- 克隆参考音色：接入本地运行的 IndexTTS 服务
- 自动完成分镜：通过 GPT-5 将口播文案拆成适合视频表达的场景
- 统一视觉：内置 10 种画面风格，包括极简白板、国风、手账、拼贴、3D 黏土和赛博霓虹等
- 控制成本与节奏：可设置每张图承载的分镜数、是否烧录中文字幕，以及画笔上的账号名
- 过程可见：显示每个制作阶段、进度和耗时，成片可直接预览和下载
- 本地优先：API Key、参考音频、图片与成片只写入项目目录下的 `.webapp/`

## 画面风格

每次生成可选择一种视觉配方。它会影响插画的配色、线条、构图和整体气质；选择时优先匹配你的内容场景，而不是只看画面是否好看。

| 风格 | 预览 | 画面特征 | 推荐内容 |
| --- | --- | --- | --- |
| **极简粗线简笔白板风** | <img src="https://raw.githubusercontent.com/ChenShuo2004/cs-board/main/web/public/styles/minimal-whiteboard.webp" alt="极简粗线简笔白板风预览" width="160" /> | 粗黑线、少量橙蓝配色、留白干净 | 知识讲解、个人表达、复盘总结 |
| **极简商务涂鸦风** | <img src="https://raw.githubusercontent.com/ChenShuo2004/cs-board/main/web/public/styles/business-doodle.webp" alt="极简商务涂鸦风预览" width="160" /> | 几何图表、蓝绿配色、专业克制 | 产品介绍、商业分析、项目汇报 |
| **暖米黄素描白板风** | <img src="https://raw.githubusercontent.com/ChenShuo2004/cs-board/main/web/public/styles/warm-pencil.webp" alt="暖米黄素描白板风预览" width="160" /> | 铅笔排线、纸张质感、温暖细腻 | 人物故事、个人成长、品牌叙事 |
| **粗线扁平国风卡通** | <img src="https://raw.githubusercontent.com/ChenShuo2004/cs-board/main/web/public/styles/guofeng-flat.webp" alt="粗线扁平国风卡通预览" width="160" /> | 朱红玉绿、国风纹样、生动平涂 | 传统文化、国风品牌、中文创意内容 |
| **爆款高热吸睛风** | <img src="https://raw.githubusercontent.com/ChenShuo2004/cs-board/main/web/public/styles/viral-pop.webp" alt="爆款高热吸睛风预览" width="160" /> | 高饱和、强对比、夸张动势 | 短视频开场、强观点、热点表达 |
| **黑金科技发布会风** | <img src="https://raw.githubusercontent.com/ChenShuo2004/cs-board/main/web/public/styles/black-gold-tech.webp" alt="黑金科技发布会风预览" width="160" /> | 黑金光效、科技舞台、高级权威 | AI 与科技产品、发布会、硬核创业内容 |
| **清新治愈手账风** | <img src="https://raw.githubusercontent.com/ChenShuo2004/cs-board/main/web/public/styles/healing-journal.webp" alt="清新治愈手账风预览" width="160" /> | 柔和水彩、低饱和配色、生活手账感 | 情感、生活方式、自我成长内容 |
| **复古报纸拼贴风** | <img src="https://raw.githubusercontent.com/ChenShuo2004/cs-board/main/web/public/styles/retro-collage.webp" alt="复古报纸拼贴风预览" width="160" /> | 撕纸拼贴、半色调、编辑杂志感 | 深度观点、文化内容、案例复盘 |
| **3D黏土趣味风** | <img src="https://raw.githubusercontent.com/ChenShuo2004/cs-board/main/web/public/styles/clay-3d.webp" alt="3D黏土趣味风预览" width="160" /> | 黏土材质、玩具比例、温暖可爱 | 亲子教育、轻量品牌、趣味科普 |
| **赛博霓虹漫画风** | <img src="https://raw.githubusercontent.com/ChenShuo2004/cs-board/main/web/public/styles/cyber-neon.webp" alt="赛博霓虹漫画风预览" width="160" /> | 霓虹青紫、漫画速度线、未来感 | AI 趋势、数码科技、年轻化观点 |

> 预览图展示的是各风格的视觉方向。实际成片会根据你的文案和分镜生成，人物、物体与场景会随内容变化。

## 开始之前

CS Board 是本地应用，不是 GitHub Pages 网站。运行和生成视频需要以下环境：

| 依赖 | 用途 |
| --- | --- |
| Windows 10/11 | 已提供 Windows 一键启动脚本；其他系统可手动启动 |
| Python 3.11+ | 后端、白板绘制和视频合成 |
| Node.js 22.13+ | 前端开发服务器 |
| FFmpeg 与 FFprobe | 音视频处理，需加入系统 `PATH` |
| IndexTTS 2.5 服务 | 本地音色克隆，支持 Gradio（默认 `7860`）或 FastAPI（默认 `8000`）接口 |
| OpenLux API Key | 用于 GPT-5 分镜规划与 GPT Image 2 插画生成；使用会产生服务商侧费用 |

## 15 分钟本地启动

### Windows

在项目根目录执行：

```powershell
python scripts/prepare_env.py
.\.venv\Scripts\python.exe -m pip install -r webapp\requirements.txt
Push-Location web
npm ci
Pop-Location
.\start-webapp.ps1
```

脚本会启动前端和后端，并自动打开 `http://127.0.0.1:13000/`。同一局域网的设备也可以使用脚本输出的局域网地址访问。

### macOS / Linux

先按系统的方式安装 FFmpeg，再在两个终端分别运行：

```bash
# 终端 1：后端
python3 scripts/prepare_env.py
.venv/bin/python -m pip install -r webapp/requirements.txt
# 当前渲染器保留了 Windows 路径，建立兼容链接以支持视频合成
mkdir -p .venv/Scripts
ln -sf ../bin/python .venv/Scripts/python.exe
.venv/bin/python -m uvicorn webapp.server:app --host 127.0.0.1 --port 18765
```

```bash
# 终端 2：前端
cd web
npm ci
npm run dev
```

打开 `http://127.0.0.1:13000/` 即可使用。

## 首次配置

打开网页右上角的 **API 设置**，填写并保存以下内容：

1. **OpenLux API Key**：密钥只保存在本机 `.webapp/config.json` 中，网页不会回显完整密钥。
2. **文本模型**：默认 `gpt-5`，负责分析文案与生成分镜。
3. **图片模型**：默认 `gpt-image-2`，负责生成分镜插画。
4. **IndexTTS 地址与接口类型**：默认是 `http://127.0.0.1:7860` 的 Gradio 服务；如果你运行的是 FastAPI 服务，改为对应地址并选择 FastAPI。

点击“测试连接”确认文字模型、图片模型和语音服务都可用。之后只需上传一段 10–30 秒、单人且噪声较少的参考音频，粘贴至少 10 个字的文案，选择画面风格，即可开始生成。

## 常见问题

### 页面显示“后端尚未启动”

确认后端进程正在运行，并检查 `http://127.0.0.1:18765/docs` 是否能打开。Windows 用户可重新运行 `.\start-webapp.ps1`；其他系统需先启动 `uvicorn`，再启动前端。

### 合成视频时提示找不到 FFmpeg 或 FFprobe

安装 FFmpeg，并把 `ffmpeg` 和 `ffprobe` 所在目录加入系统 `PATH`。重新打开终端后执行 `ffmpeg -version` 和 `ffprobe -version`，两条命令都应能返回版本信息。

### IndexTTS 连接失败

确认 IndexTTS 服务已经启动、地址和端口与 API 设置一致。Gradio 模式通常使用 `7860`，FastAPI 模式通常使用 `8000`；本地服务若部署在其他机器，请使用该机器的局域网 IP。

### 模型调用失败或无法生成图片

在 API 设置中重新检查 OpenLux API Key、接口地址及模型名称。确认你的账户具有 `gpt-5` 与 `gpt-image-2` 的调用权限，并留意服务商的余额、额度和请求限制。

## 隐私与安全

- `.webapp/` 保存本机配置、任务文件、参考音频和生成结果，默认已被 Git 忽略。
- 不要在 Issue、日志、截图或提交记录中发布 API Key、参考音频或生成视频。
- 发现安全问题时，请不要先创建公开 Issue；详见 [SECURITY.md](SECURITY.md)。

## 项目结构

```text
├── assets/               # 画笔与视觉素材
├── examples/             # 白板动画示例
├── scripts/              # 绘制、字幕与音画合成脚本
├── web/                  # React + Vinext 前端
├── webapp/               # FastAPI 后端
├── start-webapp.ps1      # Windows 一键启动脚本
└── SKILL.md              # SRT 白板动画工作流说明
```

## 反馈

欢迎通过 [Issues](https://github.com/ChenShuo2004/cs-board/issues) 提交 Bug、使用问题与功能建议。提交前请移除 API Key、参考音频和其他私人素材。

## 许可证

本项目采用 [MIT License](LICENSE)。

