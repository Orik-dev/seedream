# from fastapi import APIRouter, Request, Header, HTTPException
# from fastapi.responses import JSONResponse
# from aiogram.types import Update

# router = APIRouter()

# @router.post("/tg/webhook")
# async def tg_webhook(request: Request, x_telegram_bot_api_secret_token: str = Header(None)):
#     if x_telegram_bot_api_secret_token != request.app.state.webhook_secret:
#         raise HTTPException(403, "forbidden")
#     update = Update.model_validate(await request.json(), context={"bot": request.app.state.bot})
#     await request.app.state.dp.feed_update(request.app.state.bot, update)
#     return JSONResponse({"ok": True})

import logging
from fastapi import APIRouter, Request, Header, HTTPException
from fastapi.responses import JSONResponse
from aiogram.types import Update

router = APIRouter()
log = logging.getLogger("tg_webhook")

@router.post("/tg/webhook")
async def tg_webhook(request: Request, x_telegram_bot_api_secret_token: str = Header(None)):
    """✅ Telegram webhook с подробным логированием"""
    log.info("webhook_hit", extra={
        "has_secret": bool(x_telegram_bot_api_secret_token),
        "expected_secret": request.app.state.webhook_secret[:10] + "..." if request.app.state.webhook_secret else None
    })
    
    if x_telegram_bot_api_secret_token != request.app.state.webhook_secret:
        log.warning("webhook_forbidden", extra={
            "received": x_telegram_bot_api_secret_token[:10] + "..." if x_telegram_bot_api_secret_token else None
        })
        raise HTTPException(403, "forbidden")
    
    try:
        body = await request.json()
        log.info("webhook_update", extra={
            "update_id": body.get("update_id"),
            "has_message": "message" in body,
            "has_callback": "callback_query" in body
        })
        
        update = Update.model_validate(body, context={"bot": request.app.state.bot})
        await request.app.state.dp.feed_update(request.app.state.bot, update)
        
        log.info("webhook_processed", extra={"update_id": body.get("update_id")})
        return JSONResponse({"ok": True})
    except Exception as e:
        log.exception("webhook_error", extra={"error": str(e)})
        return JSONResponse({"ok": False, "error": str(e)})