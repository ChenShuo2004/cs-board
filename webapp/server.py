from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from gradio_client import Client, handle_file


ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / ".webapp"
JOBS_DIR = STATE_DIR / "jobs"
CONFIG_PATH = STATE_DIR / "config.json"
PREFERENCES_PATH = STATE_DIR / "preferences.json"
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
HAND = ROOT / "assets" / "drawing-hand-clean.png"

DEFAULT_CONFIG = {
    "api_key": "",
    "base_url": "https://api.openlux.ai/v1",
    "text_model": "gpt-5",
    "image_model": "gpt-image-2",
    "tts_url": "http://127.0.0.1:7860",
    "tts_mode": "gradio",
}

DEFAULT_STYLE = "极简粗线简笔白板风"
STYLE_PRESETS = {
    "极简粗线简笔白板风": (
        "暖白色纯净背景，圆润有亲和力的粗黑马克笔轮廓，人物和物体高度概括，"
        "只使用橙色与钴蓝色做少量平涂点缀；几乎没有阴影、纹理和细碎结构，留白充足，"
        "像现场快速画出的清爽白板简笔画。"
    ),
    "极简商务涂鸦风": (
        "冷白至极浅灰背景，深海军蓝的精准几何轮廓，钴蓝与青绿色作为强调色；"
        "用整齐的卡片、流程箭头、图表和图标组织信息，线条克制利落、间距规整，"
        "呈现专业的商业演示和科技产品解说感，禁止暖黄纸张与随意手绘笔触。"
    ),
    "暖米黄素描白板风": (
        "温暖米黄色纸张底色，真实石墨铅笔线条，轻柔排线、交叉线和深浅笔压，"
        "辅以低饱和赭石色与灰蓝色；保留手工速写的纸张颗粒和结构细节，"
        "像一本质感细腻的编辑手账，不能画成粗线扁平图标。"
    ),
    "粗线扁平国风卡通": (
        "温暖宣纸色背景，深棕色粗轮廓，朱红、玉绿与靛青的饱和平涂色块；"
        "人物比例生动简化，少量使用祥云、笔触和中式构图节奏，"
        "形成现代国风科普动画效果，禁止写实素描和欧美商务信息图观感。"
    ),
    "爆款高热吸睛风": (
        "明亮黄色高能背景，超粗黑色外轮廓，热烈橙红与电光钴蓝的大色块，"
        "夸张但友好的人物表情和动作，配合放射爆炸形、速度线与强烈斜向构图；"
        "主体要大、对比要强、第一眼就能看懂，具有热门短视频封面般的冲击力，"
        "但保持轮廓干净，不能堆满琐碎元素。"
    ),
    "黑金科技发布会风": (
        "深黑与炭灰背景，金属金色作为主轮廓和高光，少量电光青色点缀；"
        "使用精致的环形界面、几何数据结构和舞台式光影，主体高级、权威、科技感强，"
        "像高端科技产品发布会，禁止暖白纸张和可爱手绘效果。"
    ),
    "清新治愈手账风": (
        "奶油白纸张背景，圆润轻柔的手绘线条，鼠尾草绿、蜜桃粉、奶油黄和天蓝色的低饱和水彩；"
        "少量加入胶带、贴纸与植物点缀，整体通透、温暖、治愈、生活化，"
        "保持留白，禁止强烈黑线和高对比商务图表。"
    ),
    "复古报纸拼贴风": (
        "暖灰新闻纸底色，黑色油墨主体、复古红色强调块、半色调网点、丝网印刷颗粒与撕纸边缘；"
        "人物和物体像剪下后重新拼贴的编辑视觉，层次大胆、粗粝、有文化杂志感，"
        "禁止光滑渐变和现代扁平信息图。"
    ),
    "3D黏土趣味风": (
        "可爱的三维黏土动画场景，圆润玩具化比例，可见细微手作指纹，"
        "珊瑚橙、青绿色、亮黄色和奶油色的柔和配色，温暖棚拍光与轻柔投影，"
        "像精致的定格动画小剧场，主体清楚，禁止二维线稿和写实摄影材质。"
    ),
    "赛博霓虹漫画风": (
        "深靛蓝至黑色背景，青色与洋红色霓虹边缘光，紫色渐变和粗黑漫画轮廓；"
        "加入克制的速度线、全息几何形与未来创作者工作室氛围，构图动感、戏剧性强，"
        "同时确保人物面部和关键物体清楚可读。"
    ),
}


def style_recipe(style: str) -> str:
    return STYLE_PRESETS.get(style, STYLE_PRESETS[DEFAULT_STYLE])

app = FastAPI(title="白板声画工坊", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:13000", "http://127.0.0.1:13000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

JOBS: dict[str, dict[str, Any]] = {}
LOCK = threading.Lock()


def load_config() -> dict[str, Any]:
    STATE_DIR.mkdir(exist_ok=True)
    if not CONFIG_PATH.exists():
        return DEFAULT_CONFIG.copy()
    data = DEFAULT_CONFIG.copy()
    stored = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    # Do not migrate the former Volcengine credential into OpenLux. A key must
    # only ever be sent to the provider it was entered for.
    for key in DEFAULT_CONFIG:
        if key in stored:
            data[key] = stored[key]
    if str(data.get("text_model", "")).startswith("doubao-"):
        data["text_model"] = DEFAULT_CONFIG["text_model"]
    if str(data.get("image_model", "")).startswith("doubao-"):
        data["image_model"] = DEFAULT_CONFIG["image_model"]
    return data


def safe_config(data: dict[str, Any]) -> dict[str, Any]:
    result = data.copy()
    key = result.get("api_key", "")
    result["api_key"] = "" if not key else f"{key[:4]}••••{key[-4:]}"
    result["has_api_key"] = bool(key)
    return result


def update_job(job_id: str, **values: Any) -> None:
    with LOCK:
        JOBS[job_id].update(values)


def begin_phase(job_id: str, key: str, label: str, stage: str, progress: int) -> None:
    now = time.time()
    with LOCK:
        job = JOBS[job_id]
        previous = job.get("current_phase")
        previous_started = job.get("phase_started_at")
        timings = job.setdefault("timings", {})
        if previous and previous_started:
            entry = timings.setdefault(previous, {"label": previous, "seconds": 0.0})
            entry["seconds"] = float(entry.get("seconds", 0.0)) + max(0.0, now - float(previous_started))
        timings.setdefault(key, {"label": label, "seconds": 0.0})["label"] = label
        job.update(
            status="running", stage=stage, progress=progress,
            current_phase=key, phase_started_at=now,
        )


def finish_timing(job_id: str) -> None:
    now = time.time()
    with LOCK:
        job = JOBS[job_id]
        current = job.get("current_phase")
        started = job.get("phase_started_at")
        if current and started:
            entry = job.setdefault("timings", {}).setdefault(current, {"label": current, "seconds": 0.0})
            entry["seconds"] = float(entry.get("seconds", 0.0)) + max(0.0, now - float(started))
        job["current_phase"] = None
        job["phase_started_at"] = None
        job["finished_at"] = now
        job["total_elapsed"] = max(0.0, now - float(job.get("started_at", now)))


def job_snapshot(job_id: str) -> dict[str, Any]:
    now = time.time()
    with LOCK:
        source = JOBS[job_id]
        result = source.copy()
        timings = {key: value.copy() for key, value in source.get("timings", {}).items()}
        current = source.get("current_phase")
        phase_started = source.get("phase_started_at")
        if current and phase_started and current in timings:
            timings[current]["seconds"] = float(timings[current].get("seconds", 0.0)) + max(0.0, now - float(phase_started))
            timings[current]["running"] = True
            result["current_elapsed"] = max(0.0, now - float(phase_started))
        else:
            result["current_elapsed"] = 0.0
        result["timings"] = timings
        end = source.get("finished_at") or now
        result["total_elapsed"] = max(0.0, float(end) - float(source.get("started_at", end)))
        return result


def run(cmd: list[str], cwd: Path = ROOT) -> None:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout)[-3000:])


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nk=1:nw=1", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def extract_response_text(payload: dict[str, Any]) -> str:
    if payload.get("output_text"):
        return payload["output_text"]
    pieces = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"}:
                pieces.append(content.get("text", ""))
    for choice in payload.get("choices", []):
        message = choice.get("message", {})
        content = message.get("content", choice.get("text", ""))
        if isinstance(content, str):
            pieces.append(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") in {"text", "output_text"}:
                    pieces.append(str(part.get("text", "")))
    return "\n".join(pieces)


def parse_json_block(text: str) -> Any:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    start = min([p for p in (text.find("["), text.find("{")) if p >= 0], default=0)
    end = max(text.rfind("]"), text.rfind("}"))
    return json.loads(text[start : end + 1])


class ProviderHTTPError(RuntimeError):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


def provider_post(config: dict[str, Any], endpoint: str, payload: dict[str, Any], timeout: float = 1800) -> dict[str, Any]:
    if not config.get("api_key"):
        raise RuntimeError("请先在 API 设置中填写 OpenLux API Key")
    with httpx.Client(timeout=timeout) as client:
        response = client.post(
            f"{config['base_url'].rstrip('/')}/{endpoint.lstrip('/')}",
            headers={"Authorization": f"Bearer {config['api_key']}", "Content-Type": "application/json"},
            json=payload,
        )
        if response.is_error:
            raise ProviderHTTPError(response.status_code, f"OpenLux 调用失败：{response.status_code} {response.text[:800]}")
        return response.json()


def provider_models(config: dict[str, Any], timeout: float = 30) -> set[str]:
    if not config.get("api_key"):
        raise RuntimeError("请先在 API 设置中填写 OpenLux API Key")
    with httpx.Client(timeout=timeout) as client:
        response = client.get(
            f"{config['base_url'].rstrip('/')}/models",
            headers={"Authorization": f"Bearer {config['api_key']}"},
        )
        if response.is_error:
            raise ProviderHTTPError(response.status_code, f"OpenLux 模型列表读取失败：{response.status_code} {response.text[:800]}")
        payload = response.json()
    return {str(item.get("id")) for item in payload.get("data", []) if isinstance(item, dict) and item.get("id")}


def split_script(copy: str, target_count: int) -> list[str]:
    # Prefer complete sentences so a scene never ends on a dangling comma.
    units = [x for x in re.findall(r"[^。！？!?；;]+[。！？!?；;]?", copy) if x.strip()]
    if not units:
        return [copy]
    target_count = max(1, min(target_count, len(units)))
    groups: list[str] = []
    cursor = 0
    for group_index in range(target_count):
        remaining_groups = target_count - group_index
        remaining_units = len(units) - cursor
        if remaining_groups == 1:
            groups.append("".join(units[cursor:]).strip())
            break
        remaining_chars = sum(len(x) for x in units[cursor:])
        target_chars = remaining_chars / remaining_groups
        take = 0
        length = 0
        while take < remaining_units - (remaining_groups - 1):
            unit_len = len(units[cursor + take])
            if take and length + unit_len > target_chars * 1.18:
                break
            length += unit_len
            take += 1
            if length >= target_chars * 0.82:
                break
        take = max(1, take)
        groups.append("".join(units[cursor:cursor + take]).strip())
        cursor += take
    return groups


def make_plan(config: dict[str, Any], copy: str, duration: float, style: str) -> list[dict[str, Any]]:
    requested_count = max(3, min(12, round(duration / 8)))
    segments = split_script(copy, requested_count)
    scene_count = len(segments)
    fixed_segments = "\n".join(f"第{i + 1}幕原文：{text}" for i, text in enumerate(segments))
    prompt = f"""你是中文白板动画分镜导演。下面已经把文案固定拆成 {scene_count} 幕。
总口播时长约 {duration:.1f} 秒。风格：{style}。
严格按幕输出 title、concept、elements，不要输出或改写原文。
elements 必须是恰好 3 个具体可画的中文短语，按叙事顺序排列；每项必须包含主体和动作或物体，禁止使用抽象词。
同一位主角始终是“中国青年男性，短黑发，朴素深色上衣”，人物外观必须保持一致。
每幕只讲一个清晰事件，禁止加入原文没有的童年、旅行、花鸟、山水、宠物等内容。
只返回 JSON 数组，不要解释。
固定分幕：
{fixed_segments}"""
    payload = provider_post(config, "responses", {"model": config["text_model"], "input": prompt})
    scenes = parse_json_block(extract_response_text(payload))
    if not isinstance(scenes, list) or not scenes:
        raise RuntimeError("分镜模型未返回有效场景")
    if len(scenes) != scene_count:
        raise RuntimeError(f"分镜模型返回 {len(scenes)} 幕，预期 {scene_count} 幕，请重新生成")
    for i, scene in enumerate(scenes):
        scene["text"] = segments[i]
    weights = [max(1, len(s["text"])) for s in scenes]
    total = sum(weights)
    remaining_ms = round(duration * 1000)
    for i, scene in enumerate(scenes):
        ms = remaining_ms if i == len(scenes) - 1 else round(duration * 1000 * weights[i] / total)
        scene["duration_ms"] = max(2000, ms)
        remaining_ms -= scene["duration_ms"]
        raw_elements = scene.get("elements") or []
        labels = [str(x.get("label", "")) if isinstance(x, dict) else str(x) for x in raw_elements]
        labels = [x.strip() for x in labels if x.strip()][:4]
        if len(labels) < 2:
            labels = [scene.get("title", "口播主角"), scene.get("concept", "核心事件")]
        scene["elements"] = labels
    return scenes


def build_image_prompt(scene: dict[str, Any], style: str) -> str:
    labels = scene.get("elements") or [scene.get("title", "场景主体")]
    count = len(labels)
    lanes = "；".join(f"第{i + 1}区：{label}" for i, label in enumerate(labels))
    return f"""生成一张用于中文口播的 16:9 白板动画分镜原画。
风格名称：{style}。
视觉配方：{style_recipe(style)}
必须严格执行这套视觉配方，不得自动改回其他白板风格；人物、物体和配色都要让所选风格一眼可辨。
本幕标题：{scene.get('title', '')}
本幕叙事：{scene.get('concept', '')}
本幕原文：{scene.get('text', '')}
必须严格表现本幕叙事，不得生成童年成长、旅行、花鸟、山水、宠物等无关意象。
同一主角固定为：中国青年男性，短黑发，朴素深色上衣，普通人形象；不要改变年龄与外貌。
构图必须从左到右平均分成 {count} 个互不重叠的独立小场景，每区主体居中，区间有明显留白：{lanes}。
必须把上述每个元素都画出来，顺序不得改变；任何人物或物体不得跨越相邻区域。
主体整体垂直居中并略微靠上，主要人物和物体中心位于画面高度 42%～48%，顶部不得出现大面积无意义空白。
禁止任何文字、字母、数字、Logo、水印、边框、对话框和装饰性填充。画面底部保留约 16% 空白作为字幕安全区。"""


def build_board_prompt(scenes: list[dict[str, Any]], style: str) -> str:
    panels: list[str] = []
    for i, scene in enumerate(scenes, 1):
        elements = "、".join(scene.get("elements") or [])
        panels.append(
            f"第{i}区｜标题：{scene.get('title', '')}｜事件：{scene.get('concept', '')}｜"
            f"必须包含：{elements}｜对应原文：{scene.get('text', '')}"
        )
    panel_text = "\n".join(panels)
    return f"""生成一张用于中文口播的 16:9 白板动画原画，一张图承载 {len(scenes)} 个连续分镜。
风格名称：{style}。
视觉配方：{style_recipe(style)}
必须严格执行这套视觉配方，不得自动改回其他白板风格；人物、物体和配色都要让所选风格一眼可辨。
同一主角固定为：中国青年男性，短黑发，朴素深色上衣，普通人形象；所有分镜中的年龄与外貌保持一致。
画面必须从左到右平均分成 {len(scenes)} 个互不重叠的叙事区域，不画边框；每区内部可以组合人物、动作和关键物体，但不得跨区。
{panel_text}
严格表现上述事件，不得生成原文没有的童年成长、旅行、花鸟、山水、宠物或装饰性意象。
所有区域的主体垂直居中并略微靠上，主要人物和物体中心位于画面高度 42%～48%，顶部不得出现大面积无意义空白。
禁止任何文字、字母、数字、Logo、水印、边框和对话框。画面底部保留约 16% 空白作为字幕安全区。"""


def generate_image(config: dict[str, Any], prompt: str, target: Path) -> None:
    # OpenLux documents a 1000-character limit for this GPT Image route.
    compact_prompt = prompt if len(prompt) <= 1000 else f"{prompt[:830]}\n{prompt[-160:]}"
    request_payload = {
        "model": config["image_model"],
        "prompt": compact_prompt,
        "n": 1,
        "size": "1536x1024",
        "quality": "medium",
        "format": "png",
    }
    try:
        payload = provider_post(config, "images/generations", request_payload, timeout=1800)
    except ProviderHTTPError as exc:
        if exc.status_code not in {404, 405}:
            raise
        # OpenLux currently also documents GPT Image 2 creation on this route.
        payload = provider_post(config, "images/edits", request_payload, timeout=1800)
    candidates = payload.get("data") or payload.get("choices") or []
    if not candidates:
        raise RuntimeError("GPT Image 2 没有返回图像数据")
    item = candidates[0]
    encoded = item.get("b64_json") or item.get("b64")
    url = item.get("url")
    if encoded:
        if isinstance(encoded, str) and encoded.startswith("data:image"):
            encoded = encoded.split(",", 1)[-1]
        target.write_bytes(base64.b64decode(encoded))
    elif url:
        with httpx.Client(timeout=120) as client:
            response = client.get(url)
            response.raise_for_status()
            target.write_bytes(response.content)
    else:
        raise RuntimeError("GPT Image 2 返回格式中没有 b64_json 或 url")


def synthesize_voice(config: dict[str, Any], reference: Path, copy: str, target: Path) -> None:
    if config.get("tts_mode") == "fastapi":
        with httpx.Client(timeout=900) as client, reference.open("rb") as audio:
            response = client.post(
                f"{config['tts_url'].rstrip('/')}/api/tts",
                data={"text": copy, "emo_weight": "0.65"},
                files={"voice": (reference.name, audio, "audio/wav")},
            )
            if response.is_error:
                raise RuntimeError(f"语音克隆失败：{response.status_code} {response.text[:500]}")
            target.write_bytes(response.content)
        return

    # Long-form cloning can keep the GPU busy for several minutes.  The
    # default Gradio HTTP read timeout is too short and abandons a healthy job.
    client = Client(config["tts_url"], verbose=False, httpx_kwargs={"timeout": 1800.0})
    job = client.submit(
        "与参考音频的音色相同", handle_file(str(reference)), copy, None, 0.65,
        0, 0, 0, 0, 0, 0, 0, 0, "", False, 120,
        True, 0.8, 30, 0.8, 0.0, 3, 10.0, 1500,
        api_name="/gen_single",
    )
    result = job.result(timeout=1800)
    # Gradio 4/5 may return a filepath string, while newer IndexTTS builds
    # return FileData as {"path": ..., "url": ...}.
    item: Any = result
    # Unwrap tuples/lists and Gradio update objects such as
    # {"visible": true, "value": {"path": ...}, "__type__": "update"}.
    while True:
        if isinstance(item, (list, tuple)) and item:
            item = item[0]
            continue
        if isinstance(item, dict) and "value" in item and not item.get("path"):
            item = item["value"]
            continue
        break
    if isinstance(item, dict):
        path_value = item.get("path")
        if path_value and Path(path_value).exists():
            shutil.copy2(Path(path_value), target)
            return
        if item.get("url"):
            with httpx.Client(timeout=300) as http:
                response = http.get(item["url"])
                response.raise_for_status()
                target.write_bytes(response.content)
            return
        raise RuntimeError(f"语音服务返回了无法识别的文件对象：{list(item.keys())}")
    if isinstance(item, (str, os.PathLike)):
        shutil.copy2(Path(item), target)
        return
    raise RuntimeError(f"语音服务返回格式不受支持：{type(item).__name__}")


def write_annotation(scene: dict[str, Any], image: Path, target: Path, index: int) -> None:
    from PIL import Image

    with Image.open(image) as im:
        width, height = im.size
    labels = scene.get("elements") or [scene.get("title", "场景主体")]
    count = max(1, len(labels))
    duration = int(scene["duration_ms"])
    gap = 120
    usable = duration - 500 - gap * (count - 1)
    each = max(500, usable // count)
    margin_x = max(10, width // 80)
    band = (width - margin_x * 2) / count
    elements = []
    for i, label in enumerate(labels):
        x = round(margin_x + i * band)
        x2 = round(margin_x + (i + 1) * band)
        start = 200 + i * (each + gap)
        elements.append({
            "id": f"part-{i+1}", "label": str(label), "sequence": i + 1,
            "narrativeRole": "按文案叙事顺序出现", "subtitle": scene.get("text", ""), "type": "concept",
            "region": {"x": x, "y": round(height * 0.02), "width": x2 - x, "height": round(height * 0.80)},
            "reveal": {"direction": "left_to_right", "startMs": start, "durationMs": each, "maskPaddingPx": 16, "protectedRegions": []},
            "handPath": {"start": [x + 5, height // 2], "end": [x2 - 5, height // 2], "easing": "easeInOut"},
        })
    data = {
        "sceneId": f"scene-{index:02d}", "canvas": {"width": width, "height": height},
        "storyBasis": scene.get("concept", scene.get("title", "")), "sceneDurationMs": duration,
        "elements": elements,
    }
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_board_annotation(scenes: list[dict[str, Any]], image: Path, target: Path, index: int) -> None:
    from PIL import Image

    with Image.open(image) as im:
        width, height = im.size
    count = len(scenes)
    margin_x = max(10, width // 100)
    band = (width - margin_x * 2) / count
    offset = 0
    elements = []
    for i, scene in enumerate(scenes):
        x = round(margin_x + i * band)
        x2 = round(margin_x + (i + 1) * band)
        duration = int(scene["duration_ms"])
        elements.append({
            "id": f"panel-{i + 1}", "label": scene.get("title", f"分镜{i + 1}"),
            "sequence": i + 1, "narrativeRole": scene.get("concept", "按原文叙事"),
            "subtitle": scene.get("text", ""), "type": "scene",
            "region": {"x": x, "y": round(height * 0.02), "width": x2 - x, "height": round(height * 0.80)},
            "reveal": {"direction": "left_to_right", "startMs": offset, "durationMs": duration, "maskPaddingPx": 14, "protectedRegions": []},
            "handPath": {"start": [x + 5, height // 2], "end": [x2 - 5, height // 2], "easing": "easeInOut"},
        })
        offset += duration
    data = {
        "sceneId": f"board-{index:02d}", "canvas": {"width": width, "height": height},
        "storyBasis": " / ".join(str(s.get("title", "")) for s in scenes),
        "sceneDurationMs": offset, "elements": elements,
    }
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def make_branded_hand(text: str, target: Path) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    if not text.strip():
        return HAND
    hand = Image.open(HAND).convert("RGBA")
    label = text.strip()[:12]
    font_paths = [Path("C:/Windows/Fonts/msyhbd.ttc"), Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/simhei.ttf")]
    font_path = next((p for p in font_paths if p.exists()), None)
    font = ImageFont.truetype(str(font_path), 58) if font_path else ImageFont.load_default()
    strip = Image.new("RGBA", (430, 104), (0, 0, 0, 0))
    draw = ImageDraw.Draw(strip)
    box = draw.textbbox((0, 0), label, font=font)
    text_width = box[2] - box[0]
    if text_width > 380 and font_path:
        font = ImageFont.truetype(str(font_path), max(24, round(58 * 380 / text_width)))
        box = draw.textbbox((0, 0), label, font=font)
        text_width = box[2] - box[0]
    draw.text(((430 - text_width) / 2, 20), label, font=font, fill=(105, 48, 30, 240), stroke_width=1, stroke_fill=(255, 255, 255, 200))
    rotated = strip.rotate(-40, resample=Image.Resampling.BICUBIC, expand=True)
    hand.alpha_composite(rotated, (430, 300))
    hand.save(target)
    return target


def _subtitle_chunks(text: str, max_chars: int = 22) -> list[str]:
    sentences = [x.strip() for x in re.findall(r"[^。！？!?；;，,]+[。！？!?；;，,]?", text) if x.strip()]
    chunks: list[str] = []
    for sentence in sentences:
        while len(sentence) > max_chars:
            chunks.append(sentence[:max_chars])
            sentence = sentence[max_chars:]
        if sentence:
            chunks.append(sentence)
    return chunks or [text]


def _srt_time(ms: int) -> str:
    hours, rem = divmod(max(0, ms), 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def write_subtitles(scenes: list[dict[str, Any]], target: Path) -> None:
    cues: list[tuple[int, int, str]] = []
    offset = 0
    for scene in scenes:
        chunks = _subtitle_chunks(str(scene.get("text", "")))
        weights = [max(1, len(re.sub(r"\s+", "", x))) for x in chunks]
        duration = int(scene["duration_ms"])
        used = 0
        for i, (chunk, weight) in enumerate(zip(chunks, weights)):
            cue_ms = duration - used if i == len(chunks) - 1 else round(duration * weight / sum(weights))
            cues.append((offset + used, offset + used + cue_ms, chunk))
            used += cue_ms
        offset += duration
    lines: list[str] = []
    for i, (start, end, text) in enumerate(cues, 1):
        lines.extend([str(i), f"{_srt_time(start)} --> {_srt_time(end)}", text, ""])
    target.write_text("\n".join(lines), encoding="utf-8")


def process_job(job_id: str, copy: str, style: str, reference: Path, scenes_per_image: int, pen_text: str, include_subtitles: bool) -> None:
    job_dir = JOBS_DIR / job_id
    try:
        config = load_config()
        begin_phase(job_id, "voice", "语音克隆", "正在克隆声音", 8)
        voice = job_dir / "voice.wav"
        synthesize_voice(config, reference, copy, voice)
        duration = probe_duration(voice)

        begin_phase(job_id, "planning", "分镜规划", "正在生成分镜", 18)
        scenes = make_plan(config, copy, duration, style)
        boards = [scenes[i:i + scenes_per_image] for i in range(0, len(scenes), scenes_per_image)]
        (job_dir / "plan.json").write_text(json.dumps(scenes, ensure_ascii=False, indent=2), encoding="utf-8")
        (job_dir / "boards.json").write_text(json.dumps([
            {"scene_numbers": list(range(i * scenes_per_image + 1, i * scenes_per_image + len(board) + 1)), "image_prompt": build_board_prompt(board, style)}
            for i, board in enumerate(boards)
        ], ensure_ascii=False, indent=2), encoding="utf-8")
        hand_asset = make_branded_hand(pen_text, job_dir / "hand-branded.png")

        videos = []
        for i, board in enumerate(boards, 1):
            base_progress = 22 + int((i - 1) / len(boards) * 64)
            draw_progress = 22 + int((i - 0.45) / len(boards) * 64)
            begin_phase(job_id, "images", "图片生成", f"正在生成第 {i}/{len(boards)} 张分镜图", base_progress)
            stem = f"board-{i:02d}"
            image = job_dir / f"{stem}.png"
            annotation = job_dir / f"{stem}.annotation.json"
            video = job_dir / f"{stem}.mp4"
            generate_image(config, build_board_prompt(board, style), image)
            write_board_annotation(board, image, annotation, i)
            begin_phase(job_id, "drawing", "手绘渲染", f"正在绘制第 {i}/{len(boards)} 张分镜图", draw_progress)
            run([str(PYTHON), str(ROOT / "scripts" / "render_stream_whiteboard.py"), str(image), str(annotation), str(video), str(hand_asset), "--ink-path", "skeleton", "--color-fill", "contour-wipe"])
            videos.append(video)

        begin_phase(job_id, "compositing", "音画合成", "正在合成声音和画面", 90)
        silent = job_dir / "silent.mp4"
        final = job_dir / "final.mp4"
        run([str(PYTHON), str(ROOT / "scripts" / "merge_scenes.py"), "--inputs", *map(str, videos), "--output", str(silent)])
        ffmpeg_command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", "silent.mp4", "-i", "voice.wav", "-map", "0:v:0", "-map", "1:a:0"]
        if include_subtitles:
            subtitles = job_dir / "subtitles.srt"
            write_subtitles(scenes, subtitles)
            subtitle_filter = "subtitles=subtitles.srt:force_style='FontName=Microsoft YaHei,FontSize=20,PrimaryColour=&H00FFFFFF,OutlineColour=&H00202020,BorderStyle=1,Outline=2,Shadow=0,MarginV=28,Alignment=2'"
            ffmpeg_command.extend(["-vf", subtitle_filter])
        ffmpeg_command.extend(["-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-shortest", "final.mp4"])
        run(ffmpeg_command, cwd=job_dir)
        finish_timing(job_id)
        update_job(job_id, status="done", stage="制作完成", progress=100, result_url=f"/api/jobs/{job_id}/download", duration=duration, scenes=len(scenes), boards=len(boards))
    except Exception as exc:
        finish_timing(job_id)
        update_job(job_id, status="error", stage="制作失败", error=str(exc))


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "renderer": PYTHON.exists(), "tts": load_config()["tts_url"]}


@app.get("/api/config")
def get_config() -> dict[str, Any]:
    return safe_config(load_config())


@app.post("/api/config")
def save_config(payload: dict[str, Any]) -> dict[str, Any]:
    current = load_config()
    for key in DEFAULT_CONFIG:
        value = payload.get(key)
        if key == "api_key" and isinstance(value, str) and "••••" in value:
            continue
        if value not in (None, ""):
            current[key] = value
    STATE_DIR.mkdir(exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    return safe_config(current)


@app.post("/api/config/test")
def test_config(payload: dict[str, Any]) -> dict[str, Any]:
    config = load_config()
    config.update({
        k: v for k, v in payload.items()
        if k in DEFAULT_CONFIG and v and not (k == "api_key" and isinstance(v, str) and "••••" in v)
    })
    results: dict[str, Any] = {}
    try:
        provider_post(config, "responses", {"model": config["text_model"], "input": "只回复：连接成功"}, timeout=60)
        results["openlux"] = {"ok": True, "message": f"OpenLux {config['text_model']} 连接成功"}
    except Exception as exc:
        results["openlux"] = {"ok": False, "message": str(exc)}
    try:
        models = provider_models(config)
        image_model = str(config["image_model"])
        if models and image_model not in models:
            raise RuntimeError(f"当前 Key 的模型列表中没有 {image_model}")
        results["image"] = {"ok": True, "message": f"{image_model} 已可用" if models else f"{image_model} 将在生成时验证"}
    except Exception as exc:
        results["image"] = {"ok": False, "message": str(exc)}
    try:
        url = config["tts_url"].rstrip("/")
        check = f"{url}/gradio_api/info" if config.get("tts_mode") == "gradio" else f"{url}/api/health"
        response = httpx.get(check, timeout=8)
        response.raise_for_status()
        results["tts"] = {"ok": True, "message": "语音克隆服务连接成功"}
    except Exception as exc:
        results["tts"] = {"ok": False, "message": f"语音服务连接失败：{exc}"}
    return results


@app.get("/api/preferences")
def get_preferences() -> dict[str, Any]:
    if not PREFERENCES_PATH.exists():
        return {"pen_text": ""}
    try:
        data = json.loads(PREFERENCES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"pen_text": ""}
    return {"pen_text": str(data.get("pen_text", ""))[:12]}


@app.post("/api/preferences")
def save_preferences(payload: dict[str, Any]) -> dict[str, Any]:
    preferences = {"pen_text": str(payload.get("pen_text", "")).strip()[:12]}
    STATE_DIR.mkdir(exist_ok=True)
    PREFERENCES_PATH.write_text(json.dumps(preferences, ensure_ascii=False, indent=2), encoding="utf-8")
    return preferences


@app.post("/api/jobs")
async def create_job(
    script: str = Form(..., alias="copy"),
    style: str = Form("极简粗线简笔白板风"),
    scenes_per_image: int = Form(1),
    pen_text: str = Form(""),
    include_subtitles: bool = Form(True),
    reference: UploadFile = File(...),
) -> dict[str, Any]:
    if len(script.strip()) < 10:
        raise HTTPException(400, "文案至少需要 10 个字")
    job_id = uuid.uuid4().hex[:12]
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(reference.filename or "reference.wav").suffix or ".wav"
    reference_path = job_dir / f"reference{suffix}"
    with reference_path.open("wb") as target:
        shutil.copyfileobj(reference.file, target)
    now = time.time()
    with LOCK:
        JOBS[job_id] = {
            "id": job_id, "status": "queued", "stage": "等待开始", "progress": 1,
            "created_at": now, "started_at": now, "timings": {},
            "current_phase": None, "phase_started_at": None, "total_elapsed": 0.0,
        }
    scenes_per_image = max(1, min(4, scenes_per_image))
    threading.Thread(target=process_job, args=(job_id, script.strip(), style, reference_path, scenes_per_image, pen_text.strip()[:12], include_subtitles), daemon=True).start()
    return job_snapshot(job_id)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    if job_id not in JOBS:
        raise HTTPException(404, "任务不存在或服务已经重启")
    return job_snapshot(job_id)


@app.get("/api/jobs/{job_id}/download")
def download_job(job_id: str) -> FileResponse:
    path = JOBS_DIR / job_id / "final.mp4"
    if not path.exists():
        raise HTTPException(404, "视频尚未生成")
    return FileResponse(path, media_type="video/mp4", filename=f"whiteboard-{job_id}.mp4")
