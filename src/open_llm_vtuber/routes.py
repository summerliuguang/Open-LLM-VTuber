import os
import json
from uuid import uuid4
import numpy as np
from datetime import datetime
from fastapi import APIRouter, WebSocket, UploadFile, File, Request, Response
from starlette.responses import JSONResponse
from starlette.websockets import WebSocketDisconnect
from loguru import logger
from .service_context import ServiceContext
from .websocket_handler import WebSocketHandler
from .proxy_handler import ProxyHandler


def init_client_ws_route(default_context_cache: ServiceContext) -> APIRouter:
    """
    Create and return API routes for handling the `/client-ws` WebSocket connections.

    Args:
        default_context_cache: Default service context cache for new sessions.

    Returns:
        APIRouter: Configured router with WebSocket endpoint.
    """

    router = APIRouter()
    ws_handler = WebSocketHandler(default_context_cache)

    @router.websocket("/client-ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket endpoint for client connections"""
        await websocket.accept()
        client_uid = str(uuid4())

        try:
            await ws_handler.handle_new_connection(websocket, client_uid)
            await ws_handler.handle_websocket_communication(websocket, client_uid)
        except WebSocketDisconnect:
            await ws_handler.handle_disconnect(client_uid)
        except Exception as e:
            logger.error(f"Error in WebSocket connection: {e}")
            await ws_handler.handle_disconnect(client_uid)
            raise

    @router.get("/api/llm-config")
    async def get_llm_config():
        """读取 conf.yaml 中当前使用的语言模型配置（api_key 脱敏）"""
        import yaml

        try:
            with open("conf.yaml", "r", encoding="utf-8") as f:
                conf = yaml.safe_load(f)
            agent_conf = conf["character_config"]["agent_config"]
            provider = agent_conf.get("llm_provider", "openai_compatible_llm")
            llm_settings = agent_conf.get("llm_configs", {})
            section = llm_settings.get(provider, {}) or {}
            api_key = str(section.get("llm_api_key") or "")
            masked = (api_key[:6] + "..." + api_key[-4:]) if len(api_key) > 12 else ("已设置" if api_key else "")
            return JSONResponse(
                {
                    "provider": provider,
                    "base_url": section.get("base_url", ""),
                    "model": section.get("model", ""),
                    "api_key_masked": masked,
                }
            )
        except Exception as e:
            logger.error(f"Failed to read LLM config: {e}")
            return JSONResponse({"error": str(e)}, status_code=500)

    @router.post("/api/llm-config")
    async def update_llm_config(request: Request):
        """修改 conf.yaml 中语言模型配置；对新连接生效（页面刷新/重连后加载）"""
        import yaml
        from pydantic import BaseModel

        class LlmConfigBody(BaseModel):
            provider: str = "openai_compatible_llm"
            base_url: str
            api_key: str = ""  # 留空或与脱敏值相同表示不修改
            model: str

        body = LlmConfigBody(**(await request.json()))
        try:
            with open("conf.yaml", "r", encoding="utf-8") as f:
                conf = yaml.safe_load(f)
            agent_conf = conf["character_config"]["agent_config"]
            agent_conf["llm_provider"] = body.provider
            llm_settings = agent_conf.setdefault("llm_configs", {})
            section = llm_settings.setdefault(body.provider, {})
            section["base_url"] = body.base_url
            if body.api_key and "..." not in body.api_key:
                section["llm_api_key"] = body.api_key
            section["model"] = body.model
            with open("conf.yaml", "w", encoding="utf-8") as f:
                yaml.safe_dump(conf, f, allow_unicode=True, sort_keys=False)
            logger.info(f"LLM config updated: provider={body.provider}, model={body.model}")
            return JSONResponse({"ok": True})
        except Exception as e:
            logger.error(f"Failed to update LLM config: {e}")
            return JSONResponse({"error": str(e)}, status_code=500)

    return router


def init_proxy_route(server_url: str) -> APIRouter:
    """
    Create and return API routes for handling proxy connections.

    Args:
        server_url: The WebSocket URL of the actual server

    Returns:
        APIRouter: Configured router with proxy WebSocket endpoint
    """
    router = APIRouter()
    proxy_handler = ProxyHandler(server_url)

    @router.websocket("/proxy-ws")
    async def proxy_endpoint(websocket: WebSocket):
        """WebSocket endpoint for proxy connections"""
        try:
            await proxy_handler.handle_client_connection(websocket)
        except Exception as e:
            logger.error(f"Error in proxy connection: {e}")
            raise

    return router


def init_webtool_routes(default_context_cache: ServiceContext) -> APIRouter:
    """
    Create and return API routes for handling web tool interactions.

    Args:
        default_context_cache: Default service context cache for new sessions.

    Returns:
        APIRouter: Configured router with WebSocket endpoint.
    """

    router = APIRouter()

    @router.get("/web-tool")
    async def web_tool_redirect():
        """Redirect /web-tool to /web_tool/index.html"""
        return Response(status_code=302, headers={"Location": "/web-tool/index.html"})

    @router.get("/web_tool")
    async def web_tool_redirect_alt():
        """Redirect /web_tool to /web_tool/index.html"""
        return Response(status_code=302, headers={"Location": "/web-tool/index.html"})

    @router.get("/live2d-models/info")
    async def get_live2d_folder_info():
        """Get information about available Live2D models"""
        live2d_dir = "live2d-models"
        if not os.path.exists(live2d_dir):
            return JSONResponse(
                {"error": "Live2D models directory not found"}, status_code=404
            )

        valid_characters = []
        supported_extensions = [".png", ".jpg", ".jpeg"]

        for entry in os.scandir(live2d_dir):
            if entry.is_dir():
                folder_name = entry.name.replace("\\", "/")
                # model3.json 可能在模型根目录,也可能在 runtime/ 子目录(如 mao_pro/shizuku)
                model3_candidates = [
                    os.path.join(live2d_dir, folder_name, f"{folder_name}.model3.json"),
                    os.path.join(live2d_dir, folder_name, "runtime", f"{folder_name}.model3.json"),
                ]
                model3_file = next(
                    (p.replace("\\", "/") for p in model3_candidates if os.path.isfile(p)),
                    None,
                )
                if model3_file is not None:
                    # Find avatar file if it exists (root or runtime/)
                    avatar_file = None
                    for ext in supported_extensions:
                        for base in (
                            os.path.join(live2d_dir, folder_name),
                            os.path.join(live2d_dir, folder_name, "runtime"),
                        ):
                            avatar_path = os.path.join(base, f"{folder_name}{ext}")
                            if os.path.isfile(avatar_path):
                                avatar_file = avatar_path.replace("\\", "/")
                                break
                        if avatar_file is not None:
                            break

                    valid_characters.append(
                        {
                            "name": folder_name,
                            "avatar": avatar_file,
                            "model_path": model3_file,
                        }
                    )
        return JSONResponse(
            {
                "type": "live2d-models/info",
                "count": len(valid_characters),
                "characters": valid_characters,
            }
        )

    @router.post("/asr")
    async def transcribe_audio(file: UploadFile = File(...)):
        """
        Endpoint for transcribing audio using the ASR engine
        """
        logger.info(f"Received audio file for transcription: {file.filename}")

        try:
            contents = await file.read()

            # Validate minimum file size
            if len(contents) < 44:  # Minimum WAV header size
                raise ValueError("Invalid WAV file: File too small")

            # Decode the WAV header and get actual audio data
            wav_header_size = 44  # Standard WAV header size
            audio_data = contents[wav_header_size:]

            # Validate audio data size
            if len(audio_data) % 2 != 0:
                raise ValueError("Invalid audio data: Buffer size must be even")

            # Convert to 16-bit PCM samples to float32
            try:
                audio_array = (
                    np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
                    / 32768.0
                )
            except ValueError as e:
                raise ValueError(
                    f"Audio format error: {str(e)}. Please ensure the file is 16-bit PCM WAV format."
                )

            # Validate audio data
            if len(audio_array) == 0:
                raise ValueError("Empty audio data")

            text = await default_context_cache.asr_engine.async_transcribe_np(
                audio_array
            )
            logger.info(f"Transcription result: {text}")
            return {"text": text}

        except ValueError as e:
            logger.error(f"Audio format error: {e}")
            return Response(
                content=json.dumps({"error": str(e)}),
                status_code=400,
                media_type="application/json",
            )
        except Exception as e:
            logger.error(f"Error during transcription: {e}")
            return Response(
                content=json.dumps(
                    {"error": "Internal server error during transcription"}
                ),
                status_code=500,
                media_type="application/json",
            )

    @router.websocket("/tts-ws")
    async def tts_endpoint(websocket: WebSocket):
        """WebSocket endpoint for TTS generation"""
        await websocket.accept()
        logger.info("TTS WebSocket connection established")

        try:
            while True:
                data = await websocket.receive_json()
                text = data.get("text")
                if not text:
                    continue

                logger.info(f"Received text for TTS: {text}")

                # Split text into sentences
                sentences = [s.strip() for s in text.split(".") if s.strip()]

                try:
                    # Generate and send audio for each sentence
                    for sentence in sentences:
                        sentence = sentence + "."  # Add back the period
                        file_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid4())[:8]}"
                        audio_path = (
                            await default_context_cache.tts_engine.async_generate_audio(
                                text=sentence, file_name_no_ext=file_name
                            )
                        )
                        logger.info(
                            f"Generated audio for sentence: {sentence} at: {audio_path}"
                        )

                        await websocket.send_json(
                            {
                                "status": "partial",
                                "audioPath": audio_path,
                                "text": sentence,
                            }
                        )

                    # Send completion signal
                    await websocket.send_json({"status": "complete"})

                except Exception as e:
                    logger.error(f"Error generating TTS: {e}")
                    await websocket.send_json({"status": "error", "message": str(e)})

        except WebSocketDisconnect:
            logger.info("TTS WebSocket client disconnected")
        except Exception as e:
            logger.error(f"Error in TTS WebSocket connection: {e}")
            await websocket.close()

    return router
