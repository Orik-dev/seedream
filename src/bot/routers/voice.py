from __future__ import annotations

import os
import tempfile
import logging
from typing import BinaryIO

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from openai import AsyncOpenAI

from core.config import settings
from bot.states import GenStates, CreateStates
from services.queue import enqueue_generation
from db.engine import SessionLocal
from db.models import User

router = Router()
logger = logging.getLogger("voice")

# ✅ Инициализация OpenAI клиента с проверкой
try:
    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "your_openai_api_key":
        openai_client = None
        logger.warning("OpenAI API key not configured - voice messages disabled")
    else:
        openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        logger.info("OpenAI client initialized successfully")
except Exception as e:
    openai_client = None
    logger.error(f"Failed to initialize OpenAI client: {e}")


async def transcribe_voice_whisper(audio_file: BinaryIO, filename: str = "audio.ogg") -> str:
    """
    ✅ Транскрибация голосового сообщения через OpenAI Whisper API
    """
    if openai_client is None:
        raise ValueError("OpenAI API not configured")
    
    try:
        transcript = await openai_client.audio.transcriptions.create(
            model=settings.WHISPER_MODEL,
            file=(filename, audio_file, "audio/ogg"),
            language="ru",
            response_format="text"
        )
        
        text = transcript.strip()
        
        logger.info(
            "whisper_transcription_success",
            extra={
                "text_length": len(text),
                "model": settings.WHISPER_MODEL
            }
        )
        
        return text
        
    except Exception as e:
        logger.exception(
            "whisper_transcription_error",
            extra={"error": str(e)}
        )
        raise


@router.message(F.voice)
async def handle_voice_message(message: Message, state: FSMContext):
    """
    ✅ Обработка голосовых сообщений через OpenAI Whisper API
    """
    # ✅ Проверка конфигурации OpenAI
    if openai_client is None:
        await message.answer(
            "❌ Распознавание голоса временно недоступно.\n\n"
            "💡 Пожалуйста, напишите текстом или обратитесь в поддержку: @guard_gpt"
        )
        return
    
    user_id = message.from_user.id
    temp_file_path = None

    cur = await state.get_state()
    data = await state.get_data()
    
    logger.info(
        "voice_message_received",
        extra={
            "user_id": user_id,
            "state": cur,
            "duration": message.voice.duration
        }
    )

    # ❌ Блокировка голоса в неподходящих состояниях
    if cur == GenStates.uploading_images.state:
        await message.answer(
            "⚠️ Сначала загрузите 1–10 фотографий, которые нужно изменить.\n"
            "После загрузки отправьте голосовое с описанием изменений."
        )
        return

    if cur in (GenStates.generating.state, CreateStates.generating.state):
        await message.answer("⏳ Подождите, идёт генерация. После завершения можно отправить новый запрос.")
        return

    processing_msg = await message.answer("🎙️ Распознаю голос через Whisper AI...")

    try:
        file = await message.bot.get_file(message.voice.file_id)
        voice_data = await message.bot.download_file(file.file_path)
        
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_file:
            temp_file.write(voice_data.getvalue())
            temp_file_path = temp_file.name
        
        with open(temp_file_path, "rb") as audio_file:
            text = await transcribe_voice_whisper(audio_file, filename="voice.ogg")
        
        if not text or len(text) < 2:
            await processing_msg.edit_text(
                "❌ Не удалось распознать голос.\n\n"
                "💡 Советы:\n"
                "• Говорите чётче и громче\n"
                "• Записывайте минимум 2 секунды\n"
                "• Избегайте сильного фонового шума"
            )
            return
        
        try:
            await processing_msg.edit_text(
                f"🎙️ <b>Распознано:</b>\n\n<i>{text}</i>",
                parse_mode="HTML"
            )
        except Exception:
            await message.answer(
                f"🎙️ <b>Распознано:</b>\n\n<i>{text}</i>",
                parse_mode="HTML"
            )
            try:
                await processing_msg.delete()
            except Exception:
                pass
        
        async with SessionLocal() as s:
            user = (await s.execute(select(User).where(User.chat_id == user_id))).scalar_one_or_none()
            if not user:
                await message.answer("Нажмите /start для инициализации")
                return
            
            image_resolution = user.image_resolution
            max_images = user.max_images
        
        # ========== ОБРАБОТКА ПО СОСТОЯНИЯМ ==========
        
        if cur == GenStates.waiting_prompt.state:
            photos = data.get("photos") or []
            if not photos:
                await message.answer("❌ Нет загруженных фото. Используйте /gen и отправьте фото сначала.")
                return
            
            file_ids = [p["file_id"] for p in photos]
            wait_msg = await message.answer(f"⏳ Генерирую {max_images} изображений...")
            
            await state.set_state(GenStates.generating)
            await state.update_data(
                prompt=text,
                base_prompt=text,
                edits=[],
                mode="edit",
                wait_msg_id=wait_msg.message_id,
                image_resolution=image_resolution,
                max_images=max_images,
            )
            
            await enqueue_generation(
                user_id, 
                text, 
                file_ids, 
                image_resolution=image_resolution, 
                max_images=max_images
            )
            return
        
        if cur == GenStates.final_menu.state:
            photos = data.get("photos") or []
            if not photos:
                await message.answer("❌ Не удалось найти исходные изображения. Нажмите «Начать заново».")
                return
            
            base_prompt = (data.get("base_prompt") or data.get("prompt") or "").strip()
            edits = list(data.get("edits") or [])
            edits.append(text)
            
            cumulative_prompt = " ".join([base_prompt] + edits).strip()
            if len(cumulative_prompt) > 4000:
                cumulative_prompt = cumulative_prompt[:4000]
            
            file_ids = [p["file_id"] for p in photos]
            seed = data.get("last_seed")
            
            wait_msg = await message.answer(f"⏳ Генерирую {max_images} изображений...")
            
            await state.set_state(GenStates.generating)
            await state.update_data(
                prompt=cumulative_prompt,
                base_prompt=base_prompt,
                edits=edits,
                mode="edit",
                wait_msg_id=wait_msg.message_id,
                image_resolution=image_resolution,
                max_images=max_images,
            )
            
            await enqueue_generation(
                user_id, 
                cumulative_prompt, 
                file_ids, 
                image_resolution=image_resolution, 
                max_images=max_images, 
                seed=seed
            )
            return
        
        if cur == CreateStates.waiting_prompt.state:
            aspect_ratio = data.get("aspect_ratio")
            
            wait_msg = await message.answer(f"⏳ Генерирую {max_images} изображений...")
            
            await state.set_state(CreateStates.generating)
            await state.update_data(
                mode="create",
                prompt=text,
                wait_msg_id=wait_msg.message_id,
                image_resolution=image_resolution,
                max_images=max_images,
            )
            
            await enqueue_generation(
                user_id, 
                text, 
                [], 
                aspect_ratio=aspect_ratio, 
                image_resolution=image_resolution, 
                max_images=max_images
            )
            return
        
        if cur == CreateStates.final_menu.state:
            last_result_urls = data.get("last_result_urls", [])
            aspect_ratio = data.get("aspect_ratio")
            seed = data.get("last_seed")
            
            wait_msg = await message.answer(f"⏳ Генерирую {max_images} изображений...")
            
            await state.set_state(CreateStates.generating)
            await state.update_data(
                mode="create_edit",
                prompt=text,
                wait_msg_id=wait_msg.message_id,
                image_resolution=image_resolution,
                max_images=max_images,
            )
            
            await enqueue_generation(
                user_id, 
                text, 
                last_result_urls, 
                aspect_ratio=aspect_ratio, 
                image_resolution=image_resolution, 
                max_images=max_images,
                seed=seed
            )
            return
        
        if cur == CreateStates.selecting_aspect_ratio.state:
            aspect_ratio = data.get("aspect_ratio")
            
            wait_msg = await message.answer(f"⏳ Генерирую {max_images} изображений...")
            
            await state.set_state(CreateStates.generating)
            await state.update_data(
                mode="create",
                prompt=text,
                wait_msg_id=wait_msg.message_id,
                aspect_ratio=aspect_ratio,
                image_resolution=image_resolution,
                max_images=max_images,
            )
            
            await enqueue_generation(
                user_id, 
                text, 
                [], 
                aspect_ratio=aspect_ratio, 
                image_resolution=image_resolution, 
                max_images=max_images
            )
            return
        
        await message.answer(
            "ℹ️ Для генерации используйте:\n\n"
            "• <b>/gen</b> или <b>/edit</b> — редактировать фото\n"
            "  (загрузите фото, затем скажите промт)\n\n"
            "• <b>/create</b> — создать новое изображение\n"
            "  (скажите промт сразу)\n\n"
            "• <b>/set</b> — настройки качества и количества",
            parse_mode="HTML"
        )
    
    except ValueError as e:
        if "not configured" in str(e):
            await processing_msg.edit_text(
                "❌ Распознавание голоса временно недоступно.\n\n"
                "Пожалуйста, напишите текстом или обратитесь в поддержку: @guard_gpt"
            )
    except Exception as e:
        logger.exception(
            "voice_processing_error",
            extra={
                "user_id": user_id,
                "error": str(e)
            }
        )
        
        error_msg = "❌ Произошла ошибка при обработке голосового сообщения."
        
        error_str = str(e).lower()
        if "insufficient_quota" in error_str or "quota" in error_str:
            error_msg = (
                "❌ Превышена квота OpenAI API.\n"
                "Пожалуйста, напишите текстом или обратитесь в поддержку: @guard_gpt"
            )
        elif "invalid_api_key" in error_str or "authentication" in error_str or "401" in error_str:
            error_msg = (
                "❌ Ошибка конфигурации сервиса распознавания.\n"
                "Пожалуйста, напишите текстом или обратитесь в поддержку: @guard_gpt"
            )
        elif "timeout" in error_str:
            error_msg = (
                "❌ Превышено время ожидания ответа от сервиса.\n"
                "Попробуйте ещё раз или напишите текстом."
            )
        
        try:
            await processing_msg.edit_text(error_msg)
        except Exception:
            await message.answer(error_msg)
    
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as e:
                logger.warning(
                    "temp_file_cleanup_failed",
                    extra={"path": temp_file_path, "error": str(e)}
                )
