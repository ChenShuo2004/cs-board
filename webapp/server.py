from __future__ import annotations

import base64
import json
import mimetypes
import os
import queue
import re
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
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
    "tts_url_2": "",
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
    "纸感隐喻拼贴风": (
        "暖米白手工纸背景，清晰纸纤维、撕边、轻微褶皱与手工裁切痕迹；人物和物体由剪纸拼贴叠层构成，"
        "带柔和浅浮雕投影，成人卡通比例、圆白眼与小黑瞳、细线鼻口。主色仅使用米杏、炭黑、深灰、暖灰、"
        "珊瑚红和灰粉，金黄只用于希望、价值或关键转折。每张图只选择定义、流程、对比、层级、因果、清单、"
        "时间或矩阵中的一个主结构，用单一具体隐喻表达观点；留白占 25%–45%，主视觉不超过 3 组，辅助符号不超过 5 类。"
        "禁止摄影写实、光滑塑料 3D、扁平矢量图标、儿童贴纸、霓虹科技 UI、文字、Logo、水印和图标堆砌。"
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
    if style not in STYLE_PRESETS:
        raise RuntimeError(f"后台未加载画面风格：{style}，请重启后台后重新提交任务")
    return STYLE_PRESETS[style]


PAPER_METAPHOR_STYLE = "纸感隐喻拼贴风"
PAPER_METAPHOR_REFERENCE_DIR = ROOT / "assets" / "style-references" / "paper-metaphor"
PAPER_METAPHOR_ROUTES: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = [
    ("流程", ("流程", "系统", "自动化", "生产", "步骤", "机器", "效率"), ("03-process-machine.png",)),
    ("对比", ("对比", "选择", "判断", "黑白", "两种", "不是", "而是"), ("05-choice-black-white.png", "09-road-between-extremes.png")),
    ("因果", ("原因", "结果", "影响", "关系", "伤害", "希望", "改变"), ("01-cause-heart-vs-wound.png",)),
    ("层级", ("层级", "成长", "方向", "阶段", "进阶", "山峰"), ("09-road-between-extremes.png",)),
    ("清单", ("清单", "资源", "经验", "多个", "几件", "要素"), ("08-dual-boxes.png",)),
    ("矩阵", ("矩阵", "四象限", "双维度"), ("02-balance-many-forces.png",)),
    ("对比", ("价值", "权衡", "平衡", "责任", "收益"), ("07-scale-values.png", "02-balance-many-forces.png")),
    ("因果", ("压力", "过载", "诱惑", "信息", "职场", "家庭"), ("04-overload-pushback.png", "06-work-stress.png")),
    ("对比", ("边界", "群体", "立场", "冲突", "夹击"), ("10-boundary-two-crowds.png",)),
]


def paper_metaphor_reference_context(scenes: list[dict[str, Any]]) -> tuple[list[Path], str]:
    text = " ".join(
        str(scene.get(key, ""))
        for scene in scenes
        for key in ("title", "concept", "text", "key_text", "metaphor")
    )
    structure = "定义"
    filenames = ("01-cause-heart-vs-wound.png",)
    for candidate, keywords, routed_files in PAPER_METAPHOR_ROUTES:
        if any(keyword in text for keyword in keywords):
            structure, filenames = candidate, routed_files
            break
    paths = [PAPER_METAPHOR_REFERENCE_DIR / filename for filename in filenames]
    paths = [path for path in paths if valid_image_file(path)][:3]
    if not paths:
        raise RuntimeError("纸感隐喻拼贴风的本地参考图缺失")
    instruction = (
        f"这些输入图仅作为纸艺视觉语言与“{structure}”构图参考，不提供人物身份或具体故事。"
        "只迁移纸纤维、撕边、叠层阴影、配色、构图密度与情绪表达；禁止照搬参考图中的人物、商品、文字、符号和场景组合。"
        f"本图统一使用“{structure}”作为唯一主结构，先用一个具体主隐喻表达观点，不做逐句图标化。"
    )
    return paths, instruction

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
VOICE_QUEUE: queue.Queue[tuple[Any, ...]] = queue.Queue()
MODEL_QUEUE: queue.Queue[tuple[Any, ...]] = queue.Queue()
WORKER_LOCK = threading.Lock()
VOICE_WORKER_THREADS: dict[int, threading.Thread] = {}
VOICE_NODE_JOBS: dict[int, str | None] = {}
VOICE_NODE_LOCK = threading.Lock()
MODEL_WORKER_THREADS: list[threading.Thread] = []
RENDER_THREADS: set[threading.Thread] = set()
RENDER_THREADS_LOCK = threading.Lock()
MODEL_CONCURRENCY = 4
MAX_ACTIVE_AND_QUEUED = 20


def _persist_job_locked(job_id: str) -> None:
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    target = job_dir / "job.json"
    temporary = job_dir / "job.json.tmp"
    temporary.write_text(json.dumps(JOBS[job_id], ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(target)


def atomic_write_json(target: Path, value: Any) -> None:
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(target)


def valid_image_file(path: Path) -> bool:
    if not path.exists() or path.stat().st_size < 1024:
        return False
    try:
        from PIL import Image
        with Image.open(path) as image:
            image.verify()
        return True
    except Exception:
        return False


def valid_media_file(path: Path) -> bool:
    if not path.exists() or path.stat().st_size < 1024:
        return False
    try:
        return probe_duration(path) > 0.1
    except Exception:
        return False


def valid_timed_video(path: Path, expected_ms: int, tolerance_seconds: float = 0.22) -> bool:
    """Reject stale scene clips whose old renderer added time past the narration."""
    if not valid_media_file(path):
        return False
    try:
        return abs(probe_duration(path) - expected_ms / 1000.0) <= tolerance_seconds
    except Exception:
        return False


def fit_scene_durations(scenes: list[dict[str, Any]], audio_duration: float) -> bool:
    """Make scene timing add up exactly to the voice track without starving the final image."""
    if not scenes:
        return False
    target_ms = max(len(scenes), round(max(0.001, audio_duration) * 1000))
    minimum_ms = min(1000, target_ms // len(scenes))
    remaining_ms = target_ms - minimum_ms * len(scenes)
    weights = [max(1, len(str(scene.get("text", "")))) for scene in scenes]
    total_weight = sum(weights)
    exact_extras = [remaining_ms * weight / total_weight for weight in weights]
    extras = [int(value) for value in exact_extras]
    leftover = remaining_ms - sum(extras)
    order = sorted(range(len(scenes)), key=lambda i: exact_extras[i] - extras[i], reverse=True)
    for index in order[:leftover]:
        extras[index] += 1
    durations = [minimum_ms + extra for extra in extras]
    changed = any(int(scene.get("duration_ms", 0)) != durations[i] for i, scene in enumerate(scenes))
    for scene, duration_ms in zip(scenes, durations):
        scene["duration_ms"] = duration_ms
    return changed


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


def configured_tts_nodes(config: dict[str, Any] | None = None) -> list[str]:
    source = config or load_config()
    nodes: list[str] = []
    for key in ("tts_url", "tts_url_2"):
        url = str(source.get(key, "")).strip().rstrip("/")
        if url and url not in nodes:
            nodes.append(url)
    return nodes


def normalized_task_name(value: Any, script: str = "", job_id: str = "") -> str:
    explicit = re.sub(r"\s+", " ", str(value or "")).strip()
    if explicit:
        return explicit[:30]
    automatic = re.sub(r"\s+", "", script.strip())[:15]
    return automatic or f"未命名任务-{job_id[-4:]}"


def request_client_ip(request: Request) -> str:
    # The API only listens on loopback and is reached through the local Vite
    # proxy. Its last forwarded address is therefore the nearest LAN client.
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        candidate = forwarded.split(",")[-1].strip()
        if candidate:
            return candidate
    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip
    return request.client.host if request.client else "未知 IP"


def update_job(job_id: str, **values: Any) -> None:
    with LOCK:
        JOBS[job_id].update(values)
        _persist_job_locked(job_id)


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
        _persist_job_locked(job_id)


def queue_for_stage(job_id: str, queue_stage: str, stage: str, progress: int) -> None:
    """Close the active timer and move a job to the next pipeline queue."""
    now = time.time()
    with LOCK:
        job = JOBS[job_id]
        current = job.get("current_phase")
        started = job.get("phase_started_at")
        if current and started:
            entry = job.setdefault("timings", {}).setdefault(current, {"label": current, "seconds": 0.0})
            entry["seconds"] = float(entry.get("seconds", 0.0)) + max(0.0, now - float(started))
        job.update(
            status="queued", stage=stage, progress=progress,
            queue_stage=queue_stage, queue_order=time.time_ns(),
            current_phase=None, phase_started_at=None,
        )
        _persist_job_locked(job_id)


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
        _persist_job_locked(job_id)


def restore_jobs() -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    with LOCK:
        for metadata in JOBS_DIR.glob("*/job.json"):
            try:
                item = json.loads(metadata.read_text(encoding="utf-8"))
                job_id = str(item.get("id") or metadata.parent.name)
                item["task_name"] = normalized_task_name(item.get("task_name"), str(item.get("copy", "")), job_id)
                if item.get("status") in {"queued", "running"}:
                    current = item.get("current_phase")
                    started = item.get("phase_started_at")
                    if current and started:
                        entry = item.setdefault("timings", {}).setdefault(current, {"label": current, "seconds": 0.0})
                        entry["seconds"] = float(entry.get("seconds", 0.0)) + max(0.0, time.time() - float(started))
                    item.update(
                        status="queued", stage="服务已恢复，正在检查任务断点", error=None,
                        current_phase=None, phase_started_at=None, finished_at=None,
                        resume_count=int(item.get("resume_count", 0)) + 1,
                    )
                JOBS[job_id] = item
                _persist_job_locked(job_id)
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                continue


def job_snapshot(job_id: str) -> dict[str, Any]:
    now = time.time()
    with LOCK:
        source = JOBS[job_id]
        result = source.copy()
        result["task_name"] = normalized_task_name(source.get("task_name"), str(source.get("copy", "")), job_id)
        result["can_retry"] = source.get("status") == "error"
        result.pop("copy", None)
        result.pop("visual_references", None)
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
        if source.get("status") == "queued":
            order = int(source.get("queue_order", 0))
            queue_stage = str(source.get("queue_stage", "voice"))
            ahead = sum(
                1 for other_id, other in JOBS.items()
                if other_id != job_id
                and other.get("status") in {"queued", "running"}
                and str(other.get("queue_stage", "voice")) == queue_stage
                and int(other.get("queue_order", 0)) < order
            )
            result["queue_ahead"] = ahead
            queue_labels = {"voice": "语音克隆", "model": "模型调用", "render": "本地渲染"}
            label = queue_labels.get(queue_stage, "任务")
            if queue_stage == "render":
                result["stage"] = "正在进入本地渲染"
            else:
                result["stage"] = f"{label}排队中，前方 {ahead} 个任务" if ahead else f"即将开始{label}"
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


def provider_retry_delay(attempt: int) -> int:
    return (3, 8, 15)[min(attempt, 2)]


def provider_post(config: dict[str, Any], endpoint: str, payload: dict[str, Any], timeout: float = 1800, job_id: str | None = None) -> dict[str, Any]:
    if not config.get("api_key"):
        raise RuntimeError("请先在 API 设置中填写 OpenLux API Key")
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    f"{config['base_url'].rstrip('/')}/{endpoint.lstrip('/')}",
                    headers={"Authorization": f"Bearer {config['api_key']}", "Content-Type": "application/json"},
                    json=payload,
                )
            if response.is_error:
                error = ProviderHTTPError(response.status_code, f"OpenLux 调用失败：{response.status_code} {response.text[:800]}")
                if response.status_code not in {408, 409, 425, 429, 500, 502, 503, 504}:
                    raise error
                raise error
            return response.json()
        except (httpx.TimeoutException, httpx.TransportError, ProviderHTTPError) as exc:
            last_error = exc
            retryable = not isinstance(exc, ProviderHTTPError) or exc.status_code in {408, 409, 425, 429, 500, 502, 503, 504}
            if not retryable or attempt == 2:
                raise
            if job_id and job_id in JOBS:
                update_job(job_id, stage=f"模型服务暂时异常，正在自动重试 {attempt + 2}/3", model_retry_count=int(JOBS[job_id].get("model_retry_count", 0)) + 1)
            time.sleep(provider_retry_delay(attempt))
    raise RuntimeError(f"模型服务重试失败：{last_error}")


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


def script_units(copy: str) -> list[str]:
    """Use the writer's sentence and paragraph boundaries as semantic units."""
    return [x.strip() for x in re.findall(r"[^。！？!?；;\n]+[。！？!?；;]?", copy) if x.strip()]


def split_script(copy: str, target_count: int) -> list[str]:
    # Prefer complete sentences and paragraphs so a scene follows the copy.
    units = script_units(copy)
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


def scene_limit_for_duration(duration: float) -> int:
    """Duration is a ceiling only: never exceed eight scenes per minute."""
    return max(1, int(max(0.0, duration) * 8 / 60))


def make_plan(config: dict[str, Any], copy: str, duration: float, style: str, character_context: str = "", job_id: str | None = None) -> list[dict[str, Any]]:
    # The copy decides how many meaningful scenes exist. Duration only caps
    # their density so short narration never receives too many images.
    requested_count = min(len(script_units(copy)) or 1, scene_limit_for_duration(duration))
    segments = split_script(copy, requested_count)
    scene_count = len(segments)
    fixed_segments = "\n".join(f"第{i + 1}幕原文：{text}" for i, text in enumerate(segments))
    character_rule = (
        f"可用人物如下：{character_context}。根据原文语义选择出场人物，并在 title、concept 和 elements 中写明人物名称；不得改变人物身份与外观。"
        if character_context else
        "主角必须严格来自原文；原文是动物就保持该动物，原文没有指定身份时才使用普通中国青年。所有分镜中的同一角色外观保持一致。"
        if style == PAPER_METAPHOR_STYLE else
        "同一位主角始终是“中国青年男性，短黑发，朴素深色上衣”，人物外观必须保持一致。"
    )
    paper_rule = (
        "额外为每幕输出 visual_structure 和 metaphor：visual_structure 只能从定义、流程、对比、层级、因果、清单、时间、矩阵中选择一项；"
        "metaphor 只写一个可被画出的核心隐喻。不要把文案中的每个名词都转成图标。"
        if style == PAPER_METAPHOR_STYLE else ""
    )
    prompt = f"""你是中文白板动画分镜导演。下面已经把文案固定拆成 {scene_count} 幕。
总口播时长约 {duration:.1f} 秒。风格：{style}。
严格按幕输出 title、key_text、concept、elements，不要输出或改写原文。
key_text 是给观众看的中文重点短语，必须准确概括本幕原文，只写 4～10 个汉字，不加标点，不得编造原文没有的观点。
elements 必须是恰好 3 个具体可画的中文短语，按叙事顺序排列；每项必须包含主体和动作或物体，禁止使用抽象词。
{character_rule}
{paper_rule}
每幕只讲一个清晰事件，禁止加入原文没有的童年、旅行、花鸟、山水、宠物等内容。
只返回 JSON 数组，不要解释。
固定分幕：
{fixed_segments}"""
    scenes: list[dict[str, Any]] = []
    last_plan_error: Exception | None = None
    for attempt in range(3):
        payload = provider_post(config, "responses", {"model": config["text_model"], "input": prompt}, job_id=job_id)
        try:
            candidate = parse_json_block(extract_response_text(payload))
            if not isinstance(candidate, list) or not candidate:
                raise RuntimeError("分镜模型未返回有效场景")
            if len(candidate) != scene_count:
                raise RuntimeError(f"分镜模型返回 {len(candidate)} 幕，预期 {scene_count} 幕")
            if not all(isinstance(scene, dict) for scene in candidate):
                raise RuntimeError("分镜模型返回的数据结构无效")
            scenes = candidate
            break
        except (json.JSONDecodeError, RuntimeError, TypeError, ValueError) as exc:
            last_plan_error = exc
            if attempt == 2:
                break
            if job_id and job_id in JOBS:
                update_job(job_id, stage=f"分镜结果异常，正在自动重试 {attempt + 2}/3", model_retry_count=int(JOBS[job_id].get("model_retry_count", 0)) + 1)
            time.sleep(provider_retry_delay(attempt))
    if not scenes:
        raise RuntimeError(f"分镜模型连续 3 次返回无效结果：{last_plan_error}")
    from scripts.add_key_text import clean_key_text
    for i, scene in enumerate(scenes):
        scene["text"] = segments[i]
        key_text = clean_key_text(str(scene.get("key_text") or scene.get("title") or segments[i]), 10)
        scene["key_text"] = key_text or clean_key_text(segments[i], 10) or "本幕重点"
    fit_scene_durations(scenes, duration)
    for scene in scenes:
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


def build_board_prompt(scenes: list[dict[str, Any]], style: str, reference_instruction: str = "", use_character_references: bool = False) -> str:
    panels: list[str] = []
    for i, scene in enumerate(scenes, 1):
        elements = "、".join(scene.get("elements") or [])
        panels.append(
            f"第{i}区｜标题：{scene.get('title', '')}｜事件：{scene.get('concept', '')}｜"
            f"主结构：{scene.get('visual_structure', '')}｜核心隐喻：{scene.get('metaphor', '')}｜"
            f"必须包含：{elements}｜对应原文：{scene.get('text', '')}"
        )
    panel_text = "\n".join(panels)
    style_instruction = (
        "严格复现输入风格参考图的配色、线条粗细、材质、造型比例与构图语言；不要复制风格图里原有的人物或事件。"
        if reference_instruction else
        f"视觉配方：{style_recipe(style)}\n必须严格执行这套视觉配方，不得自动改回其他白板风格；人物、物体和配色都要让所选风格一眼可辨。"
    )
    character_instruction = (
        "只使用人物参考组中定义的角色；人物出现时必须保持对应参考图的脸型、发型、年龄、服装和标志性特征一致。"
        if use_character_references else
        "主角必须严格来自原文；动物、人物身份与年龄不得被替换，同一角色在所有分镜中保持一致。"
        if style == PAPER_METAPHOR_STYLE else
        "同一主角固定为：中国青年男性，短黑发，朴素深色上衣，普通人形象；所有分镜中的年龄与外貌保持一致。"
    )
    reference_block = f"参考图说明：\n{reference_instruction}\n" if reference_instruction else ""
    return f"""{reference_block}生成一张用于中文口播的 16:9 白板动画原画，一张图承载 {len(scenes)} 个连续分镜。
风格名称：{style}。
{style_instruction}
{character_instruction}
画面必须从左到右平均分成 {len(scenes)} 个互不重叠的叙事区域，不画边框；每区内部可以组合人物、动作和关键物体，但不得跨区。
{panel_text}
严格表现上述事件，不得生成原文没有的童年成长、旅行、花鸟、山水、宠物或装饰性意象。
所有区域的主体垂直居中并略微靠上，主要人物和物体中心位于画面高度 42%～48%，顶部不得出现大面积无意义空白。
禁止任何文字、字母、数字、Logo、水印、边框和对话框。画面底部保留约 16% 空白作为字幕安全区。"""


def generate_image(config: dict[str, Any], prompt: str, target: Path, reference_images: list[Path] | None = None, job_id: str | None = None) -> None:
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
    if reference_images:
        if not config.get("api_key"):
            raise RuntimeError("请先在 API 设置中填写 OpenLux API Key")
        form_data = {key: str(value) for key, value in request_payload.items()}
        raw_files = [(path.name, path.read_bytes(), mimetypes.guess_type(path.name)[0] or "image/png") for path in reference_images]
        response = None
        last_transport_error: Exception | None = None
        for attempt in range(3):
            try:
                with httpx.Client(timeout=1800) as client:
                    for field_name in ("image", "image[]"):
                        files = [(field_name, (name, content, mime)) for name, content, mime in raw_files]
                        response = client.post(
                            f"{config['base_url'].rstrip('/')}/images/edits",
                            headers={"Authorization": f"Bearer {config['api_key']}"},
                            data=form_data,
                            files=files,
                        )
                        if not response.is_error or response.status_code not in {400, 422}:
                            break
                if response is not None and not response.is_error:
                    break
                retryable = response is not None and response.status_code in {408, 409, 425, 429, 500, 502, 503, 504}
                if not retryable or attempt == 2:
                    break
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_transport_error = exc
                if attempt == 2:
                    raise
            if job_id and job_id in JOBS:
                update_job(job_id, stage=f"参考图模型暂时异常，正在自动重试 {attempt + 2}/3", model_retry_count=int(JOBS[job_id].get("model_retry_count", 0)) + 1)
            time.sleep(provider_retry_delay(attempt))
        if response is None or response.is_error:
            status = response.status_code if response is not None else 500
            detail = response.text[:800] if response is not None else str(last_transport_error or "没有响应")
            raise ProviderHTTPError(status, f"OpenLux 参考图调用失败：{status} {detail}")
        payload = response.json()
    else:
        try:
            payload = provider_post(config, "images/generations", request_payload, timeout=1800, job_id=job_id)
        except ProviderHTTPError as exc:
            if exc.status_code not in {404, 405}:
                raise
            # OpenLux currently also documents GPT Image 2 creation on this route.
            payload = provider_post(config, "images/edits", request_payload, timeout=1800, job_id=job_id)
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


def custom_reference_context(job_id: str) -> tuple[list[Path], str, str]:
    with LOCK:
        job = JOBS.get(job_id, {}).copy()
    if job.get("reference_mode") != "custom":
        return [], "", ""
    job_dir = JOBS_DIR / job_id
    references = job.get("visual_references") or {}
    style_name = str(references.get("style_image") or "")
    style_path = job_dir / style_name
    if not style_name or not valid_image_file(style_path):
        raise RuntimeError("自定义风格参考图缺失或无效")
    paths = [style_path]
    lines = ["输入图1是唯一的画面风格参考，只学习其视觉风格，不复制图中人物。"]
    character_descriptions: list[str] = []
    image_index = 2
    for character in references.get("characters") or []:
        name = str(character.get("name") or "未命名人物")[:20]
        description = str(character.get("description") or "以参考图外观为准")[:80]
        character_paths = [job_dir / str(value) for value in character.get("images") or []]
        character_paths = [path for path in character_paths if valid_image_file(path)]
        if not character_paths:
            continue
        start = image_index
        paths.extend(character_paths)
        image_index += len(character_paths)
        end = image_index - 1
        range_label = f"输入图{start}" if start == end else f"输入图{start}至输入图{end}"
        lines.append(f"{range_label}共同定义人物“{name}”：{description}。同名人物在所有分镜保持一致。")
        character_descriptions.append(f"{name}（{description}）")
    if not character_descriptions:
        raise RuntimeError("没有可用的人物参考图")
    return paths, "\n".join(lines), "；".join(character_descriptions)


def _synthesize_voice_once(config: dict[str, Any], reference: Path, copy: str, target: Path) -> None:
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


def synthesize_voice(config: dict[str, Any], reference: Path, copy: str, target: Path) -> None:
    """Retry transient LAN failures while keeping TTS concurrency at one."""
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            _synthesize_voice_once(config, reference, copy, target)
            return
        except Exception as exc:
            last_error = exc
            message = str(exc).lower()
            retryable = any(token in message for token in ("10061", "connection refused", "connecterror", "timed out"))
            if not retryable or attempt == 3:
                break
            time.sleep(5 * (attempt + 1))
    raw = str(last_error or "未知错误")
    if "10061" in raw or "connection refused" in raw.lower():
        raise RuntimeError(
            f"无法连接语音克隆服务 {config.get('tts_url', '')}。请确认 IndexTTS 已启动并可从本机访问；系统已自动重试 4 次。"
        ) from last_error
    raise RuntimeError(f"语音克隆失败：{raw}") from last_error


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


def fail_job(job_id: str, stage: str, exc: Exception) -> None:
    finish_timing(job_id)
    update_job(job_id, status="error", stage=stage, error=str(exc))


def voice_stage(job_id: str, copy: str, style: str, reference: Path, scenes_per_image: int, pen_text: str, include_key_text: bool, include_subtitles: bool, stroke_detail: str, tts_url: str, node_index: int) -> None:
    job_dir = JOBS_DIR / job_id
    try:
        config = load_config()
        config["tts_url"] = tts_url
        update_job(job_id, tts_node=tts_url, tts_node_index=node_index + 1)
        begin_phase(job_id, "voice", "语音克隆", f"语音节点 {node_index + 1} 正在克隆声音", 8)
        voice = job_dir / "voice.wav"
        if not valid_media_file(voice):
            partial_voice = job_dir / "voice.partial.wav"
            partial_voice.unlink(missing_ok=True)
            synthesize_voice(config, reference, copy, partial_voice)
            if not valid_media_file(partial_voice):
                raise RuntimeError("语音服务返回的音频文件无效")
            partial_voice.replace(voice)
        duration = probe_duration(voice)
        update_job(job_id, duration=duration, checkpoint="voice_done")
        queue_for_stage(job_id, "model", "等待调用模型", 14)
        MODEL_QUEUE.put((job_id, copy, style, reference, scenes_per_image, pen_text, include_key_text, include_subtitles, stroke_detail))
        ensure_pipeline_workers()
    except Exception as exc:
        fail_job(job_id, "语音克隆失败", exc)


def model_stage(job_id: str, copy: str, style: str, reference: Path, scenes_per_image: int, pen_text: str, include_key_text: bool, include_subtitles: bool, stroke_detail: str) -> None:
    job_dir = JOBS_DIR / job_id
    try:
        config = load_config()
        voice = job_dir / "voice.wav"
        duration = probe_duration(voice)
        reference_images, reference_instruction, character_context = custom_reference_context(job_id)

        plan_path = job_dir / "plan.json"
        scenes: list[dict[str, Any]] = []
        if plan_path.exists():
            try:
                saved_plan = json.loads(plan_path.read_text(encoding="utf-8"))
                if isinstance(saved_plan, list) and saved_plan and all(isinstance(scene, dict) for scene in saved_plan):
                    scenes = saved_plan
            except (OSError, json.JSONDecodeError):
                scenes = []
        if not scenes:
            begin_phase(job_id, "planning", "分镜规划", "正在生成分镜", 18)
            scenes = make_plan(config, copy, duration, style, character_context, job_id)
            atomic_write_json(plan_path, scenes)
        else:
            begin_phase(job_id, "planning", "分镜规划", "已恢复分镜计划", 20)
        if fit_scene_durations(scenes, duration):
            atomic_write_json(plan_path, scenes)
        boards = [scenes[i:i + scenes_per_image] for i in range(0, len(scenes), scenes_per_image)]
        board_specs: list[tuple[list[Path], str, str]] = []
        for board in boards:
            board_images = reference_images
            board_instruction = reference_instruction
            use_character_references = bool(character_context)
            if style == PAPER_METAPHOR_STYLE and not board_images:
                board_images, board_instruction = paper_metaphor_reference_context(board)
                use_character_references = False
            board_prompt = build_board_prompt(board, style, board_instruction, use_character_references)
            board_specs.append((board_images, board_instruction, board_prompt))
        update_job(job_id, duration=duration, scenes=len(scenes), boards=len(boards), checkpoint="plan_done")
        atomic_write_json(job_dir / "boards.json", [
            {"scene_numbers": list(range(i * scenes_per_image + 1, i * scenes_per_image + len(board) + 1)), "image_prompt": board_specs[i][2]}
            for i, board in enumerate(boards)
        ])
        from scripts.add_key_text import add_key_text
        for i, board in enumerate(boards, 1):
            board_images, _board_instruction, board_prompt = board_specs[i - 1]
            base_progress = 22 + int((i - 1) / len(boards) * 54)
            begin_phase(job_id, "images", "图片生成", f"正在生成第 {i}/{len(boards)} 张分镜图", base_progress)
            stem = f"board-{i:02d}"
            image = job_dir / f"{stem}.png"
            source_image = job_dir / f"{stem}.source.png"
            if not valid_image_file(source_image):
                partial_image = job_dir / f"{stem}.source.partial.png"
                last_image_error: Exception | None = None
                for attempt in range(3):
                    partial_image.unlink(missing_ok=True)
                    try:
                        generate_image(config, board_prompt, partial_image, board_images, job_id)
                        if valid_image_file(partial_image):
                            break
                        raise RuntimeError("模型返回的图片文件无效")
                    except ProviderHTTPError:
                        raise
                    except (RuntimeError, ValueError, OSError) as exc:
                        last_image_error = exc
                        if attempt == 2:
                            break
                        update_job(job_id, stage=f"第 {i} 张图片结果异常，正在自动重试 {attempt + 2}/3", model_retry_count=int(JOBS[job_id].get("model_retry_count", 0)) + 1)
                        time.sleep(provider_retry_delay(attempt))
                if not valid_image_file(partial_image):
                    raise RuntimeError(f"第 {i} 张分镜图连续 3 次生成无效：{last_image_error}")
                partial_image.replace(source_image)
            if include_key_text:
                add_key_text(source_image, [str(scene.get("key_text", "")) for scene in board], image)
            else:
                shutil.copy2(source_image, image)
            update_job(job_id, checkpoint="images", completed_boards=i)
        queue_for_stage(job_id, "render", "准备本地渲染", 78)
        start_render_task(render_generated_job, job_id, scenes, boards, pen_text, include_subtitles, stroke_detail, duration)
    except Exception as exc:
        fail_job(job_id, "模型调用失败", exc)


def render_generated_job(job_id: str, scenes: list[dict[str, Any]], boards: list[list[dict[str, Any]]], pen_text: str, include_subtitles: bool, stroke_detail: str, duration: float) -> None:
    job_dir = JOBS_DIR / job_id
    try:
        hand_asset = make_branded_hand(pen_text, job_dir / "hand-branded.png")
        videos: list[Path] = []
        for i, board in enumerate(boards, 1):
            progress = 78 + int((i - 1) / len(boards) * 12)
            begin_phase(job_id, "drawing", "手绘渲染", f"正在绘制第 {i}/{len(boards)} 张分镜图", progress)
            stem = f"board-{i:02d}"
            image = job_dir / f"{stem}.png"
            annotation = job_dir / f"{stem}.annotation.json"
            video = job_dir / f"{stem}.mp4"
            write_board_annotation(board, image, annotation, i)
            expected_ms = sum(int(scene["duration_ms"]) for scene in board)
            if not valid_timed_video(video, expected_ms):
                video.unlink(missing_ok=True)
                partial_video = job_dir / f"{stem}.partial.mp4"
                partial_video.unlink(missing_ok=True)
                run([str(PYTHON), str(ROOT / "scripts" / "render_stream_whiteboard.py"), str(image), str(annotation), str(partial_video), str(hand_asset), "--ink-path", "skeleton", "--stroke-detail", stroke_detail, "--color-fill", "contour-wipe"])
                if not valid_media_file(partial_video):
                    raise RuntimeError(f"第 {i} 段手绘视频无效")
                partial_video.replace(video)
            videos.append(video)
            update_job(job_id, checkpoint="render", completed_videos=i)

        begin_phase(job_id, "compositing", "音画合成", "正在合成声音和画面", 92)
        silent = job_dir / "silent.mp4"
        final = job_dir / "final.mp4"
        if not valid_media_file(silent):
            partial_silent = job_dir / "silent.partial.mp4"
            partial_silent.unlink(missing_ok=True)
            run([str(PYTHON), str(ROOT / "scripts" / "merge_scenes.py"), "--inputs", *map(str, videos), "--output", str(partial_silent)])
            if not valid_media_file(partial_silent):
                raise RuntimeError("合并后的无声视频无效")
            partial_silent.replace(silent)
        if not valid_media_file(final):
            partial_final = job_dir / "final.partial.mp4"
            partial_final.unlink(missing_ok=True)
            ffmpeg_command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", "silent.mp4", "-i", "voice.wav", "-map", "0:v:0", "-map", "1:a:0"]
            if include_subtitles:
                subtitles = job_dir / "subtitles.srt"
                write_subtitles(scenes, subtitles)
                subtitle_filter = "subtitles=subtitles.srt:force_style='FontName=Microsoft YaHei,FontSize=20,PrimaryColour=&H00FFFFFF,OutlineColour=&H00202020,BorderStyle=1,Outline=2,Shadow=0,MarginV=28,Alignment=2'"
                ffmpeg_command.extend(["-vf", subtitle_filter])
            ffmpeg_command.extend(["-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-shortest", partial_final.name])
            run(ffmpeg_command, cwd=job_dir)
            if not valid_media_file(partial_final):
                raise RuntimeError("最终音画文件无效")
            partial_final.replace(final)
        finish_timing(job_id)
        update_job(job_id, status="done", stage="制作完成", progress=100, result_url=f"/api/jobs/{job_id}/download", duration=duration, scenes=len(scenes), boards=len(boards), can_rerender=True)
    except Exception as exc:
        fail_job(job_id, "本地渲染失败", exc)


def rerender_job(job_id: str, scenes_per_image: int, pen_text: str, include_key_text: bool, include_subtitles: bool, stroke_detail: str) -> None:
    job_dir = JOBS_DIR / job_id
    try:
        scenes = json.loads((job_dir / "plan.json").read_text(encoding="utf-8"))
        voice = job_dir / "voice.wav"
        duration = probe_duration(voice)
        if fit_scene_durations(scenes, duration):
            atomic_write_json(job_dir / "plan.json", scenes)
        boards = [scenes[i:i + scenes_per_image] for i in range(0, len(scenes), scenes_per_image)]
        hand_asset = make_branded_hand(pen_text, job_dir / "hand-branded.png")
        from scripts.add_key_text import add_key_text
        videos: list[Path] = []
        for i, board in enumerate(boards, 1):
            progress = 15 + int(i / len(boards) * 68)
            begin_phase(job_id, "drawing", "重新手绘", f"正在重新绘制第 {i}/{len(boards)} 张分镜图", progress)
            stem = f"board-{i:02d}"
            image = job_dir / f"{stem}.png"
            source_image = job_dir / f"{stem}.source.png"
            annotation = job_dir / f"{stem}.annotation.json"
            video = job_dir / f"{stem}.mp4"
            if source_image.exists():
                if include_key_text:
                    add_key_text(source_image, [str(scene.get("key_text", "")) for scene in board], image)
                else:
                    shutil.copy2(source_image, image)
            if not image.exists():
                raise RuntimeError(f"缺少可复用的分镜图：{image.name}")
            write_board_annotation(board, image, annotation, i)
            expected_ms = sum(int(scene["duration_ms"]) for scene in board)
            if not valid_timed_video(video, expected_ms):
                video.unlink(missing_ok=True)
                partial_video = job_dir / f"{stem}.partial.mp4"
                partial_video.unlink(missing_ok=True)
                run([str(PYTHON), str(ROOT / "scripts" / "render_stream_whiteboard.py"), str(image), str(annotation), str(partial_video), str(hand_asset), "--ink-path", "skeleton", "--stroke-detail", stroke_detail, "--color-fill", "contour-wipe"])
                if not valid_media_file(partial_video):
                    raise RuntimeError(f"第 {i} 段重新渲染视频无效")
                partial_video.replace(video)
            videos.append(video)
            update_job(job_id, checkpoint="rerender", completed_videos=i)

        begin_phase(job_id, "compositing", "音画合成", "正在重新合成声音和画面", 90)
        silent = job_dir / "silent.mp4"
        if not valid_media_file(silent):
            partial_silent = job_dir / "silent.partial.mp4"
            partial_silent.unlink(missing_ok=True)
            run([str(PYTHON), str(ROOT / "scripts" / "merge_scenes.py"), "--inputs", *map(str, videos), "--output", str(partial_silent)])
            if not valid_media_file(partial_silent):
                raise RuntimeError("重新合并后的无声视频无效")
            partial_silent.replace(silent)
        final = job_dir / "final.mp4"
        if not valid_media_file(final):
            partial_final = job_dir / "final.partial.mp4"
            partial_final.unlink(missing_ok=True)
            ffmpeg_command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", "silent.mp4", "-i", "voice.wav", "-map", "0:v:0", "-map", "1:a:0"]
            if include_subtitles:
                subtitles = job_dir / "subtitles.srt"
                write_subtitles(scenes, subtitles)
                subtitle_filter = "subtitles=subtitles.srt:force_style='FontName=Microsoft YaHei,FontSize=20,PrimaryColour=&H00FFFFFF,OutlineColour=&H00202020,BorderStyle=1,Outline=2,Shadow=0,MarginV=28,Alignment=2'"
                ffmpeg_command.extend(["-vf", subtitle_filter])
            ffmpeg_command.extend(["-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-shortest", partial_final.name])
            run(ffmpeg_command, cwd=job_dir)
            if not valid_media_file(partial_final):
                raise RuntimeError("重新渲染的最终音画文件无效")
            partial_final.replace(final)
        finish_timing(job_id)
        update_job(job_id, status="done", stage="重新渲染完成", progress=100, result_url=f"/api/jobs/{job_id}/download", duration=duration, scenes=len(scenes), boards=len(boards), can_rerender=True)
    except Exception as exc:
        fail_job(job_id, "重新渲染失败", exc)


def voice_queue_worker(node_index: int) -> None:
    while True:
        nodes = configured_tts_nodes()
        if node_index >= len(nodes):
            time.sleep(1)
            continue
        task = VOICE_QUEUE.get()
        try:
            nodes = configured_tts_nodes()
            if node_index >= len(nodes):
                VOICE_QUEUE.put(task)
                time.sleep(1)
                continue
            with VOICE_NODE_LOCK:
                VOICE_NODE_JOBS[node_index] = str(task[0])
            voice_stage(*task, nodes[node_index], node_index)
        except Exception as exc:
            job_id = str(task[0])
            if job_id in JOBS:
                fail_job(job_id, "语音队列异常", exc)
        finally:
            with VOICE_NODE_LOCK:
                VOICE_NODE_JOBS[node_index] = None
            VOICE_QUEUE.task_done()


def model_queue_worker() -> None:
    while True:
        task = MODEL_QUEUE.get()
        try:
            model_stage(*task)
        except Exception as exc:
            job_id = str(task[0])
            if job_id in JOBS:
                fail_job(job_id, "模型队列异常", exc)
        finally:
            MODEL_QUEUE.task_done()


def start_render_task(target: Any, *args: Any) -> None:
    job_id = str(args[0])

    def runner() -> None:
        try:
            target(*args)
        finally:
            with RENDER_THREADS_LOCK:
                RENDER_THREADS.discard(threading.current_thread())

    thread = threading.Thread(target=runner, name=f"local-render-{job_id}", daemon=True)
    with RENDER_THREADS_LOCK:
        RENDER_THREADS.add(thread)
    thread.start()


def ensure_pipeline_workers() -> None:
    with WORKER_LOCK:
        for index, _url in enumerate(configured_tts_nodes()):
            thread = VOICE_WORKER_THREADS.get(index)
            if thread is None or not thread.is_alive():
                thread = threading.Thread(target=voice_queue_worker, args=(index,), name=f"voice-worker-{index + 1}", daemon=True)
                VOICE_WORKER_THREADS[index] = thread
                thread.start()
        MODEL_WORKER_THREADS[:] = [thread for thread in MODEL_WORKER_THREADS if thread.is_alive()]
        while len(MODEL_WORKER_THREADS) < MODEL_CONCURRENCY:
            index = len(MODEL_WORKER_THREADS) + 1
            thread = threading.Thread(target=model_queue_worker, name=f"model-worker-{index}", daemon=True)
            MODEL_WORKER_THREADS.append(thread)
            thread.start()


def enqueue_job_from_checkpoint(job_id: str, item: dict[str, Any]) -> None:
    job_dir = JOBS_DIR / job_id
    if valid_media_file(job_dir / "final.mp4"):
        finish_timing(job_id)
        update_job(job_id, status="done", stage="已从断点恢复完成", progress=100, result_url=f"/api/jobs/{job_id}/download", can_rerender=True)
        return
    scenes_per_image = max(1, min(4, int(item.get("scenes_per_image", 1))))
    pen_text = str(item.get("pen_text", "")).strip()[:12]
    include_key_text = bool(item.get("include_key_text", True))
    include_subtitles = bool(item.get("include_subtitles", True))
    stroke_detail = str(item.get("stroke_detail", "detailed"))
    stroke_detail = stroke_detail if stroke_detail in {"light", "standard", "detailed", "full"} else "detailed"
    if item.get("job_type") == "rerender":
        queue_for_stage(job_id, "render", "正在恢复本地渲染", max(1, int(item.get("progress", 1))))
        start_render_task(rerender_job, job_id, scenes_per_image, pen_text, include_key_text, include_subtitles, stroke_detail)
        return
    copy = str(item.get("copy", "")).strip()
    if not copy:
        raise RuntimeError("旧任务缺少可恢复的文案，请从历史记录重新提交")
    reference = next(iter(sorted(job_dir.glob("reference.*"))), job_dir / "reference.wav")
    task = (job_id, copy, str(item.get("style", DEFAULT_STYLE)), reference, scenes_per_image, pen_text, include_key_text, include_subtitles, stroke_detail)
    if valid_media_file(job_dir / "voice.wav"):
        queue_for_stage(job_id, "model", "已恢复配音，等待继续模型任务", max(14, int(item.get("progress", 14))))
        MODEL_QUEUE.put(task)
    else:
        if not reference.exists():
            raise RuntimeError("任务缺少参考音频，无法从断点继续")
        queue_for_stage(job_id, "voice", "等待恢复语音克隆", max(1, int(item.get("progress", 1))))
        VOICE_QUEUE.put(task)


def resume_pending_jobs() -> None:
    with LOCK:
        pending = sorted(
            [(job_id, item.copy()) for job_id, item in JOBS.items() if item.get("status") in {"queued", "running"}],
            key=lambda entry: (int(entry[1].get("queue_order", 0)), float(entry[1].get("created_at", 0))),
        )
    for job_id, item in pending:
        try:
            enqueue_job_from_checkpoint(job_id, item)
        except Exception as exc:
            fail_job(job_id, "任务恢复失败", exc)
    ensure_pipeline_workers()


restore_jobs()
resume_pending_jobs()


@app.get("/api/health")
def health() -> dict[str, Any]:
    with RENDER_THREADS_LOCK:
        render_active = sum(1 for thread in RENDER_THREADS if thread.is_alive())
    nodes = configured_tts_nodes()
    with VOICE_NODE_LOCK:
        voice_nodes = [
            {"index": index + 1, "url": url, "active": bool(VOICE_NODE_JOBS.get(index)), "job_id": VOICE_NODE_JOBS.get(index)}
            for index, url in enumerate(nodes)
        ]
    return {
        "status": "ok", "renderer": PYTHON.exists(), "tts": nodes,
        "queues": {
            "voice": {"concurrency": len(nodes), "waiting": VOICE_QUEUE.qsize(), "nodes": voice_nodes},
            "model": {"concurrency": MODEL_CONCURRENCY, "waiting": MODEL_QUEUE.qsize()},
            "render": {"concurrency": "local-direct", "active": render_active},
        },
    }


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
        if key == "tts_url_2" and isinstance(value, str):
            current[key] = value.strip()
            continue
        if value not in (None, ""):
            current[key] = value
    STATE_DIR.mkdir(exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    ensure_pipeline_workers()
    return safe_config(current)


@app.post("/api/config/test")
def test_config(payload: dict[str, Any]) -> dict[str, Any]:
    config = load_config()
    for key, value in payload.items():
        if key not in DEFAULT_CONFIG or (key == "api_key" and isinstance(value, str) and "••••" in value):
            continue
        if key == "tts_url_2" and isinstance(value, str):
            config[key] = value.strip()
        elif value:
            config[key] = value
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
    tts_results: list[dict[str, Any]] = []
    for index, url in enumerate(configured_tts_nodes(config), 1):
        try:
            check = f"{url}/gradio_api/info" if config.get("tts_mode") == "gradio" else f"{url}/api/health"
            response = httpx.get(check, timeout=8)
            response.raise_for_status()
            tts_results.append({"index": index, "url": url, "ok": True, "message": f"语音节点 {index} 连接成功"})
        except Exception as exc:
            tts_results.append({"index": index, "url": url, "ok": False, "message": f"语音节点 {index} 连接失败：{exc}"})
    tts_ok = bool(tts_results) and all(item["ok"] for item in tts_results)
    results["tts_nodes"] = tts_results
    results["tts"] = {"ok": tts_ok, "message": "；".join(str(item["message"]) for item in tts_results) or "未配置语音节点"}
    return results


@app.get("/api/preferences")
def get_preferences() -> dict[str, Any]:
    if not PREFERENCES_PATH.exists():
        return {"pen_text": "", "stroke_detail": "detailed"}
    try:
        data = json.loads(PREFERENCES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"pen_text": "", "stroke_detail": "detailed"}
    detail = str(data.get("stroke_detail", "detailed"))
    return {"pen_text": str(data.get("pen_text", ""))[:12], "stroke_detail": detail if detail in {"light", "standard", "detailed", "full"} else "detailed"}


@app.post("/api/preferences")
def save_preferences(payload: dict[str, Any]) -> dict[str, Any]:
    detail = str(payload.get("stroke_detail", "detailed"))
    preferences = {
        "pen_text": str(payload.get("pen_text", "")).strip()[:12],
        "stroke_detail": detail if detail in {"light", "standard", "detailed", "full"} else "detailed",
    }
    STATE_DIR.mkdir(exist_ok=True)
    PREFERENCES_PATH.write_text(json.dumps(preferences, ensure_ascii=False, indent=2), encoding="utf-8")
    return preferences


@app.post("/api/jobs")
async def create_job(
    request: Request,
    script: str = Form(..., alias="copy"),
    style: str = Form("极简粗线简笔白板风"),
    scenes_per_image: int = Form(1),
    task_name: str = Form(""),
    pen_text: str = Form(""),
    include_key_text: bool = Form(True),
    include_subtitles: bool = Form(True),
    stroke_detail: str = Form("detailed"),
    reference: UploadFile = File(...),
    reference_mode: str = Form("standard"),
    character_manifest: str = Form("[]"),
    style_reference: UploadFile | None = File(None),
    character_references: list[UploadFile] | None = File(None),
) -> dict[str, Any]:
    if len(script.strip()) < 10:
        raise HTTPException(400, "文案至少需要 10 个字")
    with LOCK:
        pending = sum(1 for item in JOBS.values() if item.get("status") in {"queued", "running"})
    if pending >= MAX_ACTIVE_AND_QUEUED:
        raise HTTPException(429, f"当前已有 {pending} 个任务，请稍后再提交")
    job_id = uuid.uuid4().hex[:12]
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(reference.filename or "reference.wav").suffix or ".wav"
    reference_path = job_dir / f"reference{suffix}"
    with reference_path.open("wb") as target:
        shutil.copyfileobj(reference.file, target)
    reference_mode = "custom" if reference_mode == "custom" else "standard"
    visual_references: dict[str, Any] = {}
    if reference_mode == "custom":
        uploads = character_references or []
        try:
            manifest = json.loads(character_manifest)
        except json.JSONDecodeError as exc:
            shutil.rmtree(job_dir, ignore_errors=True)
            raise HTTPException(400, "人物参考信息格式无效") from exc
        if style_reference is None or not isinstance(manifest, list) or not 1 <= len(manifest) <= 5:
            shutil.rmtree(job_dir, ignore_errors=True)
            raise HTTPException(400, "自定义参考需要 1 张风格图和 1–5 个人物")
        try:
            counts = [int(item.get("file_count", 0)) for item in manifest if isinstance(item, dict)]
        except (TypeError, ValueError) as exc:
            shutil.rmtree(job_dir, ignore_errors=True)
            raise HTTPException(400, "人物参考图片数量无效") from exc
        if len(counts) != len(manifest) or any(count < 1 or count > 3 for count in counts):
            shutil.rmtree(job_dir, ignore_errors=True)
            raise HTTPException(400, "每个人物需要上传 1–3 张参考图")
        expected = sum(counts)
        if expected != len(uploads) or expected < 1 or expected > 15:
            shutil.rmtree(job_dir, ignore_errors=True)
            raise HTTPException(400, "人物参考图片数量不匹配")
        style_suffix = Path(style_reference.filename or "style.png").suffix.lower()
        if style_suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
            shutil.rmtree(job_dir, ignore_errors=True)
            raise HTTPException(400, "风格参考图只支持 PNG、JPG 或 WebP")
        style_path = job_dir / f"style-reference{style_suffix}"
        with style_path.open("wb") as target:
            shutil.copyfileobj(style_reference.file, target)
        saved_characters: list[dict[str, Any]] = []
        cursor = 0
        for character_index, item in enumerate(manifest, 1):
            if not isinstance(item, dict):
                continue
            count = max(1, min(3, int(item.get("file_count", 1))))
            image_names: list[str] = []
            for image_index, upload in enumerate(uploads[cursor:cursor + count], 1):
                suffix = Path(upload.filename or "character.png").suffix.lower()
                if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
                    shutil.rmtree(job_dir, ignore_errors=True)
                    raise HTTPException(400, "人物参考图只支持 PNG、JPG 或 WebP")
                image_name = f"character-{character_index:02d}-{image_index:02d}{suffix}"
                image_path = job_dir / image_name
                with image_path.open("wb") as target:
                    shutil.copyfileobj(upload.file, target)
                if image_path.stat().st_size > 15 * 1024 * 1024 or not valid_image_file(image_path):
                    shutil.rmtree(job_dir, ignore_errors=True)
                    raise HTTPException(400, "人物参考图无效或超过 15MB")
                image_names.append(image_name)
            cursor += count
            saved_characters.append({
                "name": str(item.get("name") or f"人物 {character_index}").strip()[:20],
                "description": str(item.get("description") or "").strip()[:80],
                "images": image_names,
            })
        if style_path.stat().st_size > 15 * 1024 * 1024 or not valid_image_file(style_path):
            shutil.rmtree(job_dir, ignore_errors=True)
            raise HTTPException(400, "风格参考图无效或超过 15MB")
        visual_references = {"style_image": style_path.name, "characters": saved_characters}
    scenes_per_image = max(1, min(4, scenes_per_image))
    stroke_detail = stroke_detail if stroke_detail in {"light", "standard", "detailed", "full"} else "detailed"
    task_name = normalized_task_name(task_name, script, job_id)
    now = time.time()
    with LOCK:
        JOBS[job_id] = {
            "id": job_id, "status": "queued", "stage": "等待语音克隆", "progress": 1,
            "created_at": now, "started_at": now, "timings": {},
            "queue_stage": "voice", "queue_order": time.time_ns(),
            "client_ip": request_client_ip(request),
            "job_type": "generate", "style": style, "scenes_per_image": scenes_per_image,
            "reference_mode": reference_mode, "character_count": len(visual_references.get("characters", [])),
            "visual_references": visual_references,
            "task_name": task_name,
            "copy": script.strip(),
            "pen_text": pen_text.strip()[:12], "include_key_text": include_key_text,
            "include_subtitles": include_subtitles,
            "stroke_detail": stroke_detail, "can_rerender": False,
            "current_phase": None, "phase_started_at": None, "total_elapsed": 0.0,
        }
        _persist_job_locked(job_id)
    VOICE_QUEUE.put((job_id, script.strip(), style, reference_path, scenes_per_image, pen_text.strip()[:12], include_key_text, include_subtitles, stroke_detail))
    ensure_pipeline_workers()
    return job_snapshot(job_id)


@app.get("/api/jobs")
def list_jobs(limit: int = 20) -> dict[str, Any]:
    with LOCK:
        ids = sorted(JOBS, key=lambda item: float(JOBS[item].get("created_at", 0)), reverse=True)[:max(1, min(100, limit))]
    return {"items": [job_snapshot(job_id) for job_id in ids]}


@app.post("/api/jobs/{job_id}/retry")
def retry_failed_job(job_id: str, request: Request) -> dict[str, Any]:
    with LOCK:
        if job_id not in JOBS:
            raise HTTPException(404, "历史任务不存在")
        source = JOBS[job_id]
        if source.get("status") != "error":
            raise HTTPException(400, "只有失败任务可以继续")
        pending = sum(1 for item in JOBS.values() if item.get("status") in {"queued", "running"})
        if pending >= MAX_ACTIVE_AND_QUEUED:
            raise HTTPException(429, f"当前已有 {pending} 个任务，请稍后再试")
        source.update(
            status="queued", stage="正在检查任务断点", error=None, finished_at=None,
            current_phase=None, phase_started_at=None, queue_order=time.time_ns(),
            client_ip=request_client_ip(request),
            manual_retry_count=int(source.get("manual_retry_count", 0)) + 1,
        )
        item = source.copy()
        _persist_job_locked(job_id)
    try:
        enqueue_job_from_checkpoint(job_id, item)
        ensure_pipeline_workers()
    except Exception as exc:
        fail_job(job_id, "继续任务失败", exc)
    return job_snapshot(job_id)


@app.post("/api/jobs/{job_id}/rerender")
def create_rerender(job_id: str, payload: dict[str, Any], request: Request) -> dict[str, Any]:
    if job_id not in JOBS:
        raise HTTPException(404, "历史任务不存在")
    source_dir = JOBS_DIR / job_id
    required = [source_dir / "voice.wav", source_dir / "plan.json"]
    if any(not path.exists() for path in required) or not list(source_dir.glob("board-*.png")):
        raise HTTPException(400, "该任务缺少配音、分镜计划或原图，无法重新渲染")
    with LOCK:
        pending = sum(1 for item in JOBS.values() if item.get("status") in {"queued", "running"})
        source = JOBS[job_id].copy()
    if pending >= MAX_ACTIVE_AND_QUEUED:
        raise HTTPException(429, f"当前已有 {pending} 个任务，请稍后再提交")
    detail = str(payload.get("stroke_detail", source.get("stroke_detail", "detailed")))
    detail = detail if detail in {"light", "standard", "detailed", "full"} else "detailed"
    scenes_per_image = max(1, min(4, int(source.get("scenes_per_image", 1))))
    task_name = normalized_task_name(payload.get("task_name") or source.get("task_name"), str(source.get("copy", "")), job_id)
    pen_text = str(payload.get("pen_text", source.get("pen_text", ""))).strip()[:12]
    include_key_text = bool(payload.get("include_key_text", source.get("include_key_text", True)))
    include_subtitles = bool(payload.get("include_subtitles", source.get("include_subtitles", True)))
    new_id = uuid.uuid4().hex[:12]
    target_dir = JOBS_DIR / new_id
    target_dir.mkdir(parents=True, exist_ok=True)
    for name in ("voice.wav", "plan.json", "boards.json"):
        candidate = source_dir / name
        if candidate.exists():
            shutil.copy2(candidate, target_dir / name)
    for image in source_dir.glob("board-*.png"):
        shutil.copy2(image, target_dir / image.name)
    now = time.time()
    with LOCK:
        JOBS[new_id] = {
            "id": new_id, "status": "queued", "stage": "准备重新渲染", "progress": 1,
            "created_at": now, "started_at": now, "timings": {},
            "queue_stage": "render", "queue_order": time.time_ns(),
            "client_ip": request_client_ip(request),
            "job_type": "rerender", "rerender_of": job_id, "style": source.get("style", ""),
            "task_name": task_name,
            "scenes_per_image": scenes_per_image, "pen_text": pen_text,
            "include_key_text": include_key_text, "include_subtitles": include_subtitles,
            "stroke_detail": detail, "can_rerender": False,
            "current_phase": None, "phase_started_at": None, "total_elapsed": 0.0,
        }
        _persist_job_locked(new_id)
    start_render_task(rerender_job, new_id, scenes_per_image, pen_text, include_key_text, include_subtitles, detail)
    return job_snapshot(new_id)


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
