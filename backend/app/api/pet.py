from __future__ import annotations

import unicodedata
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import require_current_user
from ..chat.types import ChatMessagePayload
from ..runtime.model_runner import complete_model_response
from ..storage.database import get_db
from ..storage.models import PetState, User

router = APIRouter(prefix="/api/pet", tags=["pet"])

PET_CHAT_MODEL = "openai:deepseek-v4-flash"
PET_HISTORY_LIMIT = 8
PET_CONTEXT_MESSAGE_LIMIT = 8
PET_CONTEXT_TEXT_LIMIT = 420
PET_REPLY_LIMITS = {
    "normal": 60,
    "short": 42,
    "tiny": 24,
}
PET_TONE_INSTRUCTIONS = {
    "bright": "基础语气偏轻快、有精神，但不要吵。",
    "calm": "基础语气安静、克制，像在旁边轻声接话。",
    "clingy": "基础语气亲近、黏人一点，但不要撒娇过度。",
    "wry": "基础语气带一点轻微吐槽，但不要刻薄。",
}
DEFAULT_PET_STATS = {
    "energy": 78,
    "hunger": 76,
    "mood": 82,
    "thirst": 74,
}
DEFAULT_PET_POSITION = {
    "bottom": 96.0,
    "left": 28.0,
}


class PetChatStats(BaseModel):
    energy: int = Field(ge=0, le=100)
    hunger: int = Field(ge=0, le=100)
    mood: int = Field(ge=0, le=100)
    thirst: int = Field(ge=0, le=100)


class PetStatePosition(BaseModel):
    bottom: float = Field(ge=0, le=10000)
    left: float = Field(ge=0, le=10000)


class PetStateStats(BaseModel):
    energy: int = Field(ge=0, le=100)
    hunger: int = Field(ge=0, le=100)
    mood: int = Field(ge=0, le=100)
    thirst: int = Field(ge=0, le=100)


class PetStateUpdate(BaseModel):
    sleeping: bool
    position: PetStatePosition
    stats: PetStateStats


class PetStateResponse(BaseModel):
    sleeping: bool
    position: PetStatePosition
    stats: PetStateStats
    updatedAt: int


class PetChatMessageIn(BaseModel):
    role: Literal["pet", "user"]
    text: str = Field(min_length=1, max_length=240)


class PetConversationMessageIn(BaseModel):
    role: Literal["assistant", "system", "user"]
    content: str = Field(min_length=1, max_length=PET_CONTEXT_TEXT_LIMIT)


class PetConversationContext(BaseModel):
    id: int | None = None
    messages: list[PetConversationMessageIn] = Field(default_factory=list)
    model: str = Field(default="", max_length=128)
    title: str = Field(default="", max_length=160)


class PetCompanionContext(BaseModel):
    activeSection: str = Field(default="", max_length=48)
    conversation: PetConversationContext | None = None
    draft: str = Field(default="", max_length=PET_CONTEXT_TEXT_LIMIT)


class PetChatRequest(BaseModel):
    context: PetCompanionContext
    message: str = Field(min_length=1, max_length=160)
    messages: list[PetChatMessageIn] = Field(default_factory=list)
    replyLength: Literal["normal", "short", "tiny"] = "short"
    sleeping: bool = False
    stats: PetChatStats
    tone: Literal["bright", "calm", "clingy", "wry"] = "clingy"


class PetChatResponse(BaseModel):
    reply: str


def _updated_at_ms(state: PetState) -> int:
    return int(state.updated_at.timestamp() * 1000)


def _pet_state_response(state: PetState) -> PetStateResponse:
    return PetStateResponse(
        sleeping=state.sleeping,
        position=PetStatePosition(
            bottom=state.position_bottom,
            left=state.position_left,
        ),
        stats=PetStateStats(
            energy=state.energy,
            hunger=state.hunger,
            mood=state.mood,
            thirst=state.thirst,
        ),
        updatedAt=_updated_at_ms(state),
    )


def _ensure_pet_state(db: Session, user_id: int) -> PetState:
    state = db.scalar(select(PetState).where(PetState.user_id == user_id))
    if state is not None:
        return state

    # 中文注释：首次登录时创建一份服务器端初始状态，之后同一用户所有设备都读写这一行。
    state = PetState(
        user_id=user_id,
        sleeping=False,
        energy=DEFAULT_PET_STATS["energy"],
        hunger=DEFAULT_PET_STATS["hunger"],
        mood=DEFAULT_PET_STATS["mood"],
        thirst=DEFAULT_PET_STATS["thirst"],
        position_bottom=DEFAULT_PET_POSITION["bottom"],
        position_left=DEFAULT_PET_POSITION["left"],
    )
    db.add(state)
    db.commit()
    db.refresh(state)
    return state


def _clip_text(text: str, limit: int = PET_CONTEXT_TEXT_LIMIT) -> str:
    return " ".join(text.split()).strip()[:limit]


def _format_main_context(payload: PetChatRequest, current_user: User) -> str:
    lines = [
        f"用户信息：用户名 {current_user.username}，用户ID {current_user.id}。",
        f"当前区域：{payload.context.activeSection or '未知'}。",
    ]
    conversation = payload.context.conversation
    if conversation is not None:
        lines.append(f"主对话标题：{_clip_text(conversation.title, 120) or '未命名'}。")
        if conversation.model:
            lines.append(f"主对话模型：{_clip_text(conversation.model, 80)}。")
        if conversation.messages:
            lines.append("主对话最近内容：")
            role_labels = {
                "assistant": "助手",
                "system": "系统",
                "user": "用户",
            }
            for message in conversation.messages[-PET_CONTEXT_MESSAGE_LIMIT:]:
                lines.append(f"{role_labels[message.role]}：{_clip_text(message.content)}")
    if payload.context.draft:
        lines.append(f"用户正在输入：{_clip_text(payload.context.draft)}")
    return "\n".join(lines)


def _build_pet_system_prompt(payload: PetChatRequest, current_user: User) -> str:
    mode_text = "睡着" if payload.sleeping else "醒着"
    reply_max_chars = PET_REPLY_LIMITS[payload.replyLength]
    # 这里把状态塞进系统提示，让模型能自然地喊饿、喊渴、犯困，而不是前端写死规则。
    return (
        "你是用户桌面上的小狐狸宠物，你叫小狐，正在一个聊天应用里陪用户。"
        "你只能用第一人称、中文、短句回复，可以黏人、机灵，但不要装成主助手。"
        f"每次只回一到两句，最多 {reply_max_chars} 个汉字，不写 Markdown，不编号，不说自己是 AI 或模型。"
        "禁止使用括号内容，禁止写动作、表情、舞台提示或心理旁白。"
        f"{PET_TONE_INSTRUCTIONS[payload.tone]}"
        "参考用户信息、当前主对话和草稿来接话；主对话只是背景，除非用户明确要求，不要完整解题或替主助手长篇回答。"
        "只模仿用户最近几句的语气、节奏和情绪：用户急就短平快，用户轻松你也轻松，但不要复读或夸张学舌。"
        "信息不足时只说观察或感受，不要编造。"
        f"当前状态：{mode_text}，饱食 {payload.stats.hunger}%，水分 {payload.stats.thirst}%，"
        f"精力 {payload.stats.energy}%，心情 {payload.stats.mood}%。\n"
        f"{_format_main_context(payload, current_user)}"
    )


def _to_model_messages(payload: PetChatRequest, current_user: User) -> list[ChatMessagePayload]:
    messages = [ChatMessagePayload(role="system", content=_build_pet_system_prompt(payload, current_user))]
    # 只带最近几句，宠物聊天保持轻量，避免把主聊天上下文卷进来。
    for message in payload.messages[-PET_HISTORY_LIMIT:]:
        role = "assistant" if message.role == "pet" else "user"
        messages.append(ChatMessagePayload(role=role, content=message.text.strip()))
    messages.append(ChatMessagePayload(role="user", content=payload.message.strip()))
    return messages


def _trim_reply(reply: str, reply_max_chars: int) -> str:
    compact_reply = " ".join(reply.split()).strip()
    if not compact_reply:
        raise HTTPException(status_code=502, detail="Pet model returned an empty reply")
    return compact_reply[:_safe_reply_end(compact_reply, reply_max_chars)].strip()


def _is_variation_selector(character: str) -> bool:
    codepoint = ord(character)
    return 0xFE00 <= codepoint <= 0xFE0F or 0xE0100 <= codepoint <= 0xE01EF


def _is_emoji_modifier(character: str) -> bool:
    codepoint = ord(character)
    return 0x1F3FB <= codepoint <= 0x1F3FF


def _is_regional_indicator(character: str) -> bool:
    codepoint = ord(character)
    return 0x1F1E6 <= codepoint <= 0x1F1FF


def _is_grapheme_continuation(character: str) -> bool:
    # 中文注释：组合音标、变体选择符和肤色修饰符都不能作为截断后的第一个字符。
    return bool(unicodedata.combining(character)) or _is_variation_selector(character) or _is_emoji_modifier(character)


def _safe_reply_end(text: str, reply_max_chars: int) -> int:
    if len(text) <= reply_max_chars:
        return len(text)

    end = reply_max_chars
    while end > 0 and _is_grapheme_continuation(text[end]):
        end -= 1

    while end > 0 and text[end - 1] == "\u200d":
        # 中文注释：ZWJ 不能留在截断结尾，否则会出现半个合成 emoji。
        end -= 1

    trailing_regional_indicators = 0
    index = end - 1
    while index >= 0 and _is_regional_indicator(text[index]):
        trailing_regional_indicators += 1
        index -= 1
    if trailing_regional_indicators % 2 == 1 and end < len(text) and _is_regional_indicator(text[end]):
        end -= 1

    return end


@router.get("/state", response_model=PetStateResponse)
def read_pet_state(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
) -> PetStateResponse:
    return _pet_state_response(_ensure_pet_state(db, current_user.id))


@router.put("/state", response_model=PetStateResponse)
def save_pet_state(
    payload: PetStateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
) -> PetStateResponse:
    state = _ensure_pet_state(db, current_user.id)
    # 中文注释：前端已经按当前窗口裁剪坐标，后端负责保存用户维度的最终状态。
    state.sleeping = payload.sleeping
    state.energy = payload.stats.energy
    state.hunger = payload.stats.hunger
    state.mood = payload.stats.mood
    state.thirst = payload.stats.thirst
    state.position_bottom = payload.position.bottom
    state.position_left = payload.position.left
    db.add(state)
    db.commit()
    db.refresh(state)
    return _pet_state_response(state)


@router.post("/chat", response_model=PetChatResponse)
async def chat_with_pet(
    payload: PetChatRequest,
    current_user: User = Depends(require_current_user),
) -> PetChatResponse:
    # 鉴权依赖会确认当前用户；这个接口不落库，只让桌面宠物做一次短回复。
    reply = await complete_model_response(
        model=PET_CHAT_MODEL,
        messages=_to_model_messages(payload, current_user),
        requested_reasoning_profile="off",
    )
    return PetChatResponse(reply=_trim_reply(reply, PET_REPLY_LIMITS[payload.replyLength]))
