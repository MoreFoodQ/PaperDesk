"""設定頁的儲存類介面（POST）。server.py 按路徑轉過來，每個函式收請求體、回傳要回給頁面的 JSON。"""
from __future__ import annotations

from . import chat_models, config, engines, langs, openai_api
from .i18n import tr


def save_config(patch: dict) -> dict:
    if "translate_images" in patch and type(patch["translate_images"]) is not bool:
        raise ValueError("translate_images must be a boolean")
    if 'metadata_lookup' in patch and type(patch['metadata_lookup']) is not bool:
        raise ValueError('Metadata lookup must be a boolean')
    if 'budget' in patch:
        from .budget import validate
        validate(patch['budget'])
    for engine in ("codex", "claude"):
        options = patch.get(engine)
        if isinstance(options, dict) and any(key in options for key in ("command", "extra_args")):
            raise ValueError("CLI executable and extra arguments cannot be changed from the browser")
    patch.pop("library_dir", None)
    if "page_cap" in patch and (type(patch["page_cap"]) is not int or patch["page_cap"] < 0):
        raise ValueError(tr("页数确认上限必须是非负整数"))
    if "target" in patch:
        patch["target"] = langs.valid(patch["target"])
    if isinstance(patch.get("openai"), dict):
        patch["openai"] = config.with_key(patch["openai"])
    return {"config": config.public(config.save(patch))}


def save_chat_models(body: dict) -> dict:
    """儲存“問 AI”的名單和預設模型；或面板裡只改預設。"""
    patch = {}
    if "models" in body:
        patch["models"] = chat_models.sanitize(body["models"])
    if body.get("default"):
        patch["default"] = str(body["default"])
    full = {"chat": patch}
    if isinstance(body.get("keys"), dict):  # 設定裡給某家 API 填的 Key，和翻譯那邊共用
        keys = dict(config.load()["openai"].get("keys") or {})
        keys.update({str(k): str(v).strip() for k, v in body["keys"].items() if v and not str(v).startswith("••••")})
        full["openai"] = {"keys": keys}
    config.save(full)
    return chat_models.listing(config.load())


def test_engine(body: dict) -> dict:
    cfg = config.load()
    if body.get("engine"):
        cfg["engine"] = body["engine"]
    return engines.test(cfg)


def list_models(body: dict) -> dict:
    """設定頁“取得模型清單”：{base_url, preset, api_key}；Key 留空或打碼時用這家已存的。"""
    key = str(body.get("api_key") or "").strip()
    if not key or key.startswith("••••"):
        key = config.saved_key(config.load()["openai"], str(body.get("preset") or ""), str(body.get("base_url") or ""))
    try:
        return {"ok": True, "models": openai_api.models({"base_url": body.get("base_url"), "api_key": key})}
    except engines.EngineError as e:
        return {"ok": False, "message": str(e)[:300]}


POST = {"/api/config": save_config, "/api/chat/models": save_chat_models,
        "/api/config/test": test_engine, "/api/models/list": list_models}
