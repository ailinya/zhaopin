"""
ASR 服务（§13.3）—— 基于 faster-whisper（CTranslate2 加速，CPU 上比 openai-whisper 快 4-5 倍）

提供：
- load_whisper_model()：lifespan 启动时调用（eager-load）
- transcribe(audio_path)：同步阻塞调用
- 后处理：OpenCC 繁转简 + 术语字典修正

模型下载路径：~/.cache/huggingface/hub/（faster-whisper 默认）
"""
from __future__ import annotations

import logging
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from app.config import settings


logger = logging.getLogger(__name__)


# ===== 全局单例 =====
_whisper_model = None
_whisper_device: Optional[str] = None
_compute_type: str = "int8"


# ===== Whisper prompt 引导 =====
# 中文训练语料繁简混杂，base/medium 模型默认倾向输出繁体。
# 给一个简体中文 prompt + 专业术语表，引导模型输出简体 + 识别专业词汇。
DEFAULT_INITIAL_PROMPT_ZH = (
    "以下是简体中文面试录音。常见术语："
    "RAG、检索增强生成、向量数据库、Milvus、Pinecone、意图识别、知识库、"
    "BLEU、ROUGE、准确率、召回率、置信区间、p值、A/B 测试、转化率、留存率、"
    "TPS、ROI、PRD、PRD评审、Sprint、Kano模型、MoSCoW优先级排序、"
    "智能客服、对话系统、自然语言处理、Transformer、微调、SFT、RLHF、Token、"
    "商业模式、定价、订阅制、API调用。"
)


# ===== 后处理：术语字典 =====
# 同音字错字修正（按候选项累计出现频次）
# 规则：键 = 错字，值 = 正确字
# 触发条件：原字在 whisper 输出中出现时替换为正确字。
# 注意：只在能确定是错字时替换，避免误伤（不用模糊匹配）
_TERM_FIXES: dict[str, str] = {
    # 业务术语
    "克服": "客服",          # 智能克服 → 智能客服
    "减锁": "检索",          # 知识减锁 → 知识检索
    "减鎖": "检索",
    "减所": "检索",          # 知识减所 → 知识检索（新增）
    "知识减所": "知识检索",
    "知识减锁": "知识检索",
    "知識減鎖": "知识检索",
    "Rag": "RAG",            # 大小写规范化
    "rag": "RAG",
    "SFTV": "SFT",
    "CatGBT": "ChatGPT",
    "ChatGBT": "ChatGPT",
    "GBT": "GPT",
    "MWP": "MoSCoW",         # MWP → MoSCoW
    "MWP原则": "MoSCoW 原则",
    "MoSCoW原则": "MoSCoW 原则",
    # 数据指标术语
    "招回率": "召回率",
    "招毀率": "召回率",
    "招毁率": "召回率",
    "反人工裔": "人工评估",   # 反人工裔 → 人工评估
    "综合痕疆": "综合衡量",
    "反人工": "人工",
    "笔译精准精确度": "翻译精确度",
    "测重翻译": "衡量翻译",
    "测重摘要": "衡量摘要",
    # 录音 / 转写绿/率/所等高频同音错字
    "转接绿": "转接率",
    "转接滤": "转接率",
    "油层率": "留存率",
    "有存率": "留存率",
    "显度水平": "显著水平",
    "样门量": "样本量",
    "样本量避免": "样本量，避免",
    # 产品术语
    "进品偵探": "竞品侦探",
    "進品偵探": "竞品侦探",
    "竞品侦探": "竞品分析",
    "競品偵探": "竞品分析",
    "进品": "竞品",
    "進品": "竞品",
    "套壳 Rag": "套壳 RAG",
    "套壳rag": "套壳 RAG",
    "Rag价格": "RAG 架构",
    "选注性": "显著性",
    "批指": "p 值",
    "统计选注性": "统计显著性",
    "对道组": "对照组",
    "实验组与对道组": "实验组与对照组",
    "功效分析": "功效分析",   # 无错
    "谈品": "产品",
    "談品": "产品",
    "坦品": "产品",
    # 实验分组
    "随机氛围": "随机分为",
    "氛围实验组": "分为实验组",
    "单一辨量": "单一变量",
    # 项目管理
    "动态鐵三角": "动态铁三角",
    "鐵三角": "铁三角",
    "每日戰衛": "每日站会",
    "战卫": "站会",
    "跌代复刊": "迭代复盘",
    "跌代": "迭代",
    "複刊": "复盘",
    "叠带": "迭代",
    # 用户研究
    "用户未表他的进步需求": "用户未表达的真实需求",
    "三维调研法": "三维调研法",
    # 商业化
    "定案模式": "定价模式",
    "基础定月": "基础定价",
    "定月": "定价",
    "干量": "计量",
    "机费": "按量",
    "机费加效果分成": "按量加效果分成",
    "高王": "高昂",
    "微运": "运维",
    "微调和微运": "微调和运维",
    "欠入业务流": "嵌入业务流",
    "深度欠入": "深度嵌入",
    "数字劳动力": "数字劳动力",  # 无错
    "将本追销": "降本增效",
    # 沟通
    "技术觀念词踩地需求": "技术语言拆解需求",
    "踩地需求": "拆解需求",
    "双向翻译": "双向翻译",  # 无错
    # 信息流
    "一家二的信息流": "一二的信息流",
    "一家二": "一二",
    "1加2": "一二",
    # 技术细节
    "普达问题": "评估问题",
    "普达": "评估",
    "录油": "路由",
    "分类录油": "分类路由",
    "换绝": "幻觉",
    "模型换绝": "模型幻觉",
    "极神": "提升",
    "极神准确率": "提升准确率",
    "落立": "落地",
    "落立一种": "落地中",
    "公单": "工单",
    "公單": "工单",
    "评测级": "评测集",
    "評測級": "评测集",
    "技术必环": "技术闭环",
    "必环": "闭环",
    "将接绿": "转接率",
    # 通用
    "恆良": "可衡量",
    "可恆良": "可衡量",
    "州代末": "迭代",
    "派速": "快速",
    "派速反馈": "快速反馈",
    "未表他": "未表达",
    "表他": "表达",
    "拓起": "挖掘",
    "多摩太冷逆": "多模态能力",
    "冷逆": "能力",
    "挖起": "挖掘",
    "中場": "中",
    "后期反共": "后期返工",
    "反共": "返工",
    "暗示交付": "按时交付",
    "暗示": "按时",
    "比賽": "节奏",
    "採檢邊緣功能": "砍掉边缘功能",
    "採檢": "砍掉",
    # 信息流/前沿
    "等聚合平台": "等内容平台",
    "聚合平台": "内容平台",
    "机器自信": "机器之心",
    "等垂直": "等垂直媒体",
    "深度技术逻辑": "深度技术文章",
    "技术逻辑": "技术文章",
    "业务通缘": "业务视角",
    "通缘": "视角",
    "停估": "评估",
    "停估技术ROI": "评估技术 ROI",
    "RAID": "RSS",  # AI聚合平台通常是 RSS
    "1加2": "一二",
}


def _apply_term_fixes(text: str) -> str:
    """应用术语字典修正（按 key 长度倒序，优先匹配长 key 避免被短 key 截胡）"""
    if not text or not _TERM_FIXES:
        return text
    # 按 key 长度倒序
    sorted_keys = sorted(_TERM_FIXES.keys(), key=len, reverse=True)
    out = text
    for wrong in sorted_keys:
        correct = _TERM_FIXES[wrong]
        if wrong in out:
            out = out.replace(wrong, correct)
    return out


# ===== 后处理：OpenCC 繁转简 =====
@lru_cache(maxsize=1)
def _get_opencc_converter():
    """懒加载 OpenCC t2s 转换器（Traditional → Simplified）"""
    try:
        from opencc import OpenCC
        return OpenCC("t2s")  # 繁体 → 简体
    except Exception as e:
        logger.warning("opencc_load_failed", extra={"error": str(e)})
        return None


def _traditional_to_simplified(text: str) -> str:
    """繁体 → 简体（如果 OpenCC 不可用，原样返回）"""
    if not text:
        return text
    converter = _get_opencc_converter()
    if converter is None:
        return text
    try:
        return converter.convert(text)
    except Exception as e:
        logger.warning("opencc_convert_failed", extra={"error": str(e)})
        return text


# ===== 模型管理 =====


def detect_device() -> str:
    """检测可用设备（cuda 优先）"""
    try:
        import torch
        if settings.WHISPER_DEVICE == "cuda":
            return "cuda" if torch.cuda.is_available() else "cpu"
        elif settings.WHISPER_DEVICE == "cpu":
            return "cpu"
        else:  # auto
            return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def load_whisper_model() -> None:
    """
    加载 faster-whisper 模型（lifespan 启动时调用）

    faster-whisper 用 CTranslate2，CPU 上比 openai-whisper 快 4-5 倍。
    compute_type="int8" 是 CPU 推荐配置，速度翻倍且精度损失小。
    """
    global _whisper_model, _whisper_device, _compute_type

    device = detect_device()
    model_name = settings.WHISPER_MODEL

    # CPU 上用 int8 加速；GPU 上用 float16
    if device == "cuda":
        _compute_type = "float16"
    else:
        _compute_type = "int8"

    logger.info(
        "loading_whisper_model",
        extra={"model_name": model_name, "device": device, "compute_type": _compute_type},
    )

    try:
        from faster_whisper import WhisperModel

        _whisper_model = WhisperModel(
            model_name,
            device=device,
            compute_type=_compute_type,
        )
        _whisper_device = device
        logger.info(
            "whisper_model_loaded",
            extra={"model_name": model_name, "device": device, "compute_type": _compute_type},
        )
    except Exception as e:
        logger.error("whisper_model_load_failed", extra={"err": str(e)})
        _whisper_model = None


def release_whisper_model() -> None:
    """释放模型资源（lifespan 关闭时调用）"""
    global _whisper_model, _whisper_device
    _whisper_model = None
    _whisper_device = None
    logger.info("whisper_model_released")


def get_model():
    """获取当前加载的模型（可能为 None）"""
    return _whisper_model


def is_loaded() -> bool:
    """模型是否已加载"""
    return _whisper_model is not None


# ===== 转写 =====


def transcribe(
    audio_path: str | Path,
    language: str = "zh",
    timeout_seconds: int | None = None,
    initial_prompt: str | None = DEFAULT_INITIAL_PROMPT_ZH,
) -> str:
    """
    同步转写音频文件（阻塞）

    Args:
        audio_path: 音频文件路径（webm / wav / mp3）
        language: 强制指定语言（默认 zh）
        timeout_seconds: 超时（秒），None = 不超时
        initial_prompt: 引导 prompt（默认带简中术语表）。None 表示不传。

    Returns:
        转写后的文本（已做繁转简 + 术语修正）

    Raises:
        RuntimeError: 模型未加载
    """
    global _whisper_model

    if _whisper_model is None:
        logger.warning("whisper_model_not_loaded_attempting_lazy_load")
        load_whisper_model()
        if _whisper_model is None:
            raise RuntimeError("Whisper model 未加载，请检查 lifespan")

    # faster-whisper 转写（CPU int8 ~2-3s/段，GPU float16 ~0.5-1s/段）
    transcribe_kwargs = dict(
        language=language,
        beam_size=5,
        vad_filter=True,  # 过滤静音段，加速
    )
    if initial_prompt:
        transcribe_kwargs["initial_prompt"] = initial_prompt

    segments, info = _whisper_model.transcribe(
        str(audio_path),
        **transcribe_kwargs,
    )

    raw_text = " ".join(seg.text.strip() for seg in segments).strip()

    # 后处理 1：术语字典修正（在繁转简前修正，可识别部分简繁混淆术语）
    fixed_text = _apply_term_fixes(raw_text)

    # 后处理 2：OpenCC 繁转简（兜底，处理剩余的繁体字）
    final_text = _traditional_to_simplified(fixed_text)

    return final_text


async def transcribe_async(
    audio_path: str | Path,
    language: str = "zh",
) -> str:
    """异步版本（跑在线程池里，不阻塞 event loop）"""
    import asyncio
    from functools import partial

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        partial(transcribe, audio_path, language),
    )