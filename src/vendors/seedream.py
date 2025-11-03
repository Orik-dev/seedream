from __future__ import annotations
import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from core.config import settings

log = logging.getLogger("seedream")

class SeedreamError(Exception):
    ...

def _j(event: str, **fields) -> str:
    return json.dumps({"event": event, **fields}, ensure_ascii=False)

class SeedreamClient:
    """
    Client для Seedream V4 API (KIE.ai)
    Поддерживает:
    - Edit: bytedance/seedream-v4-edit (редактирование фото)
    - Text-to-Image: bytedance/seedream-v4-text-to-image (создание с нуля)
    - max_images: 1-6 изображений
    - seed: для воспроизводимости
    """
    def __init__(self):
        base = settings.KIE_BASE.rstrip("/")
        self.create_url = f"{base}/jobs/createTask"
        self.status_url = f"{base}/jobs/recordInfo"
        self.auth_hdr = {"Authorization": f"Bearer {settings.KIE_API_KEY}"}
        self.common_hdr = {**self.auth_hdr, "Content-Type": "application/json"}
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=15.0, read=120.0, write=30.0, pool=10.0)
        )

    async def aclose(self):
        try:
            await self._client.aclose()
        except Exception:
            pass

    def _map_image_size(self, aspect_ratio: Optional[str]) -> str:
        """Маппинг aspect_ratio в image_size"""
        mapping = {
            "9:16": "portrait_16_9",
            "16:9": "landscape_16_9",
            "4:3": "landscape_4_3",
            "3:4": "portrait_4_3",
            "1:1": "square_hd",
            None: "square_hd",
        }
        return mapping.get(aspect_ratio, "square_hd")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.8, max=8),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    )
    async def create_task_edit(
        self,
        prompt: str,
        image_urls: List[str],
        callback_url: Optional[str] = None,
        aspect_ratio: Optional[str] = None,
        image_resolution: str = "1K",
        max_images: int = 1,
        seed: Optional[int] = None,
        *,
        cid: Optional[str] = None,
    ) -> str:
        """Создание задачи редактирования (Edit mode)"""
        prompt = (prompt or "").strip()
        if not prompt:
            raise ValueError("prompt is empty")
        if not image_urls:
            raise ValueError("image_urls is empty")

        image_size = self._map_image_size(aspect_ratio)
        max_images = max(1, min(6, max_images))  # 1-6

        payload: Dict[str, Any] = {
            "model": settings.KIE_MODEL_EDIT,
            "input": {
                "prompt": prompt,
                "image_urls": image_urls[:10],
                "image_size": image_size,
                "image_resolution": image_resolution,
                "max_images": max_images,
            }
        }
        
        if seed is not None:
            payload["input"]["seed"] = seed
            
        if callback_url:
            payload["callBackUrl"] = callback_url

        log.info(_j("seedream.create_edit.request", cid=cid, prompt_len=len(prompt), 
                   images=len(image_urls), size=image_size, resolution=image_resolution,
                   max_images=max_images, seed=seed))

        try:
            r = await self._client.post(self.create_url, headers=self.common_hdr, json=payload)
            
            log.info(_j("seedream.response", cid=cid, status=r.status_code, 
                       body=r.text[:1000]))
            
            if r.status_code == 401:
                log.error(_j("seedream.create.unauthorized", cid=cid))
                raise SeedreamError("❌ Неправильный API ключ. Проверьте KIE_API_KEY")
            
            if r.status_code == 402:
                log.error(_j("seedream.create.insufficient_funds", cid=cid))
                raise SeedreamError("❌ Недостаточно средств на аккаунте KIE.ai")
            
            if r.status_code == 404:
                log.error(_j("seedream.create.not_found", cid=cid))
                raise SeedreamError("❌ Модель не найдена на https://kie.ai")
            
            if r.status_code == 422:
                log.error(_j("seedream.create.validation_error", cid=cid, body=r.text))
                raise SeedreamError(f"❌ Ошибка валидации: {r.text}")
            
            if r.status_code == 429:
                ra = r.headers.get("Retry-After")
                delay = int(ra) if (ra and ra.isdigit()) else 3
                log.warning(_j("seedream.create.rate_limited", cid=cid, retry_after=delay))
                await asyncio.sleep(delay)
                r = await self._client.post(self.create_url, headers=self.common_hdr, json=payload)
            
            if 500 <= r.status_code < 600:
                log.error(_j("seedream.create.5xx", cid=cid, status=r.status_code))
                raise SeedreamError(f"❌ Ошибка сервера KIE.ai: {r.status_code}")
            
            if r.status_code == 400:
                log.error(_j("seedream.create.bad_request", cid=cid, resp=r.text[:500]))
                raise SeedreamError(f"❌ Неправильный запрос: {r.text[:200]}")

            r.raise_for_status()
            data = r.json()
            
            if data.get("code") != 200:
                error_msg = data.get('msg', 'unknown')
                log.error(_j("seedream.create.api_error", cid=cid, msg=error_msg))
                raise SeedreamError(f"❌ Ошибка API: {error_msg}")
            
            task_id = data.get("data", {}).get("taskId")
            if not task_id:
                log.error(_j("seedream.create.no_task_id", cid=cid))
                raise SeedreamError("❌ Нет taskId в ответе")

            log.info(_j("seedream.create_edit.ok", cid=cid, task_id=task_id))
            return task_id
            
        except httpx.HTTPError as e:
            log.error(_j("seedream.http_error", cid=cid, error=str(e)))
            raise SeedreamError(f"❌ Ошибка HTTP: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.8, max=8),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    )
    async def create_task_text_to_image(
        self,
        prompt: str,
        callback_url: Optional[str] = None,
        aspect_ratio: Optional[str] = None,
        image_resolution: str = "1K",
        max_images: int = 1,
        seed: Optional[int] = None,
        *,
        cid: Optional[str] = None,
    ) -> str:
        """Создание задачи генерации из текста (Text-to-Image mode)"""
        prompt = (prompt or "").strip()
        if not prompt:
            raise ValueError("prompt is empty")

        image_size = self._map_image_size(aspect_ratio)
        max_images = max(1, min(6, max_images))

        payload: Dict[str, Any] = {
            "model": settings.KIE_MODEL_TEXT_TO_IMAGE,
            "input": {
                "prompt": prompt,
                "image_size": image_size,
                "image_resolution": image_resolution,
                "max_images": max_images,
            }
        }
        
        if seed is not None:
            payload["input"]["seed"] = seed
            
        if callback_url:
            payload["callBackUrl"] = callback_url

        log.info(_j("seedream.create_t2i.request", cid=cid, prompt_len=len(prompt), 
                   size=image_size, resolution=image_resolution, max_images=max_images, seed=seed))

        try:
            r = await self._client.post(self.create_url, headers=self.common_hdr, json=payload)
            
            log.info(_j("seedream.response", cid=cid, status=r.status_code, body=r.text[:1000]))
            
            if r.status_code == 401:
                raise SeedreamError("❌ Неправильный API ключ")
            if r.status_code == 402:
                raise SeedreamError("❌ Недостаточно средств на KIE.ai")
            if r.status_code == 404:
                raise SeedreamError("❌ Модель не найдена")
            if r.status_code == 422:
                raise SeedreamError(f"❌ Ошибка валидации: {r.text[:200]}")
            if r.status_code == 429:
                await asyncio.sleep(3)
                r = await self._client.post(self.create_url, headers=self.common_hdr, json=payload)
            if 500 <= r.status_code < 600:
                raise SeedreamError(f"❌ Ошибка сервера: {r.status_code}")

            r.raise_for_status()
            data = r.json()
            
            if data.get("code") != 200:
                raise SeedreamError(f"❌ API: {data.get('msg', 'unknown')}")
            
            task_id = data.get("data", {}).get("taskId")
            if not task_id:
                raise SeedreamError("❌ Нет taskId")

            log.info(_j("seedream.create_t2i.ok", cid=cid, task_id=task_id))
            return task_id
            
        except httpx.HTTPError as e:
            log.error(_j("seedream.http_error", cid=cid, error=str(e)))
            raise SeedreamError(f"❌ HTTP: {e}")

    async def get_status(self, task_id: str, *, cid: Optional[str] = None) -> Dict[str, Any]:
        """Получение статуса задачи"""
        r = await self._client.get(self.status_url, headers=self.auth_hdr, params={"taskId": task_id})
        if r.status_code == 429:
            await asyncio.sleep(2)
            r = await self._client.get(self.status_url, headers=self.auth_hdr, params={"taskId": task_id})
        r.raise_for_status()
        data = r.json()
        if data.get("code") != 200:
            raise SeedreamError(f"API error: {data.get('msg')}")
        return data.get("data", {})