from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import require_current_user
from ..chat.types import ChatMessagePayload
from ..runtime.model_runner import complete_model_response
from ..storage.models import User

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


class PetChatStats(BaseModel):
    energy: int = Field(ge=0, le=100)
    hunger: int = Field(ge=0, le=100)
    mood: int = Field(ge=0, le=100)
    thirst: int = Field(ge=0, le=100)


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
        "你是用户桌面上的小狐狸宠物，正在一个聊天应用里陪用户。"
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
    return compact_reply[:reply_max_chars].strip()


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
