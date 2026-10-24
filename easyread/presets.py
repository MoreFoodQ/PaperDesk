"""翻譯 / 對話引擎的 API 預設：服務商、位址、推薦模型。"""

# OpenAI 相容服務資料；region 保留舊設定識別碼。可見服務與分組由 presets() 決定。
# models：推薦的模型 {id, name 顯示名, tag 一句說明, vision 能看圖}；也能手填，或點“取得模型清單”從介面拉全部。
# api：預設 chat（/chat/completions）；OpenAI 官方用 responses。
# 模型名和免費政策會變，以服務商頁面為準（2026-10 核對過）。


def _m(mid: str, name: str, tag: str = "", vision: bool = False) -> dict:
    return {"id": mid, "name": name, "tag": tag, "vision": vision}


def _build(tr) -> list[dict]:
    # tr 作參數傳進來：PRESETS 用原樣中文（按 id / 位址查找用），presets() 用當前介面語言（顯示用）
    return [
        # ---- 舊版相容服務資料 ----
        {"id": "deepseek", "region": "cn", "name": "DeepSeek", "base_url": "https://api.deepseek.com", "model": "deepseek-flash", "key": True, "free": False,
         "models": [_m("deepseek-flash", "DeepSeek V4.1 Flash", tr("便宜、能看图"), True), _m("deepseek-v4-pro", "DeepSeek V4 Pro", tr("更强，不能看图"))],
         "key_url": "https://platform.deepseek.com/api_keys", "note": tr("开源模型的官方接口，一篇 20 页论文几毛钱。")},
        {"id": "zhipu", "region": "cn", "name": tr("智谱"), "base_url": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-4.7-flash", "key": True, "free": True,
         "models": [_m("glm-4.7-flash", "GLM-4.7-Flash", tr("免费")), _m("glm-4.6v-flash", "GLM-4.6V-Flash", tr("免费、能看图"), True),
                    _m("glm-5.3-flash", "GLM-5.3-Flash", tr("付费、能看图"), True), _m("glm-5.3", "GLM-5.3", tr("付费、最强"))],
         "key_url": "https://open.bigmodel.cn/usercenter/apikeys", "note": tr("GLM-4.7-Flash、GLM-4.6V-Flash 免费。")},
        {"id": "dashscope", "region": "cn", "name": tr("阿里云百炼（通义千问）"), "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen3.8-flash", "key": True, "free": False,
         "models": [_m("qwen3.8-flash", "Qwen3.8-Flash", tr("便宜、能看图"), True), _m("qwen3.7-plus", "Qwen3.7-Plus", tr("均衡、能看图"), True),
                    _m("qwen3.8-max", "Qwen3.8-Max", tr("最强、能看图"), True)],
         "key_url": "https://bailian.console.aliyun.com/?apiKey=1", "note": tr("新用户有免费额度。")},
        {"id": "moonshot", "region": "cn", "name": "Kimi", "base_url": "https://api.moonshot.cn/v1", "model": "kimi-k3", "key": True, "free": False,
         "models": [_m("kimi-k3", "Kimi K3", tr("能看图"), True), _m("kimi-k2.6", "Kimi K2.6", tr("能看图"), True)],
         "key_url": "https://platform.moonshot.cn/console/api-keys", "note": tr("月之暗面的官方接口。")},
        {"id": "siliconflow", "region": "cn", "name": tr("硅基流动"), "base_url": "https://api.siliconflow.cn/v1", "model": "Qwen/Qwen3-8B", "key": True, "free": True,
         "models": [_m("Qwen/Qwen3-8B", "Qwen3 8B", tr("免费")), _m("Qwen/Qwen3.5-4B", "Qwen3.5 4B", tr("免费")), _m("THUDM/GLM-4-9B-0414", "GLM-4 9B", tr("免费")),
                    _m("deepseek-ai/DeepSeek-V4-Flash", "DeepSeek V4 Flash", tr("付费")), _m("zai-org/GLM-5.3", "GLM-5.3", tr("付费"))],
         "key_url": "https://cloud.siliconflow.cn/account/ak", "note": tr("托管各家开源模型，小模型免费、大模型付费。")},
        {"id": "modelscope", "region": "cn", "name": tr("魔搭 ModelScope"), "base_url": "https://api-inference.modelscope.cn/v1", "model": "Qwen/Qwen3.8-27B", "key": True, "free": True,
         "models": [_m("Qwen/Qwen3.8-27B", "Qwen3.8 27B"), _m("Qwen/Qwen3.5-122B-A10B", "Qwen3.5 122B"),
                    _m("deepseek-ai/DeepSeek-V4.1-Flash", "DeepSeek V4.1 Flash"), _m("ZhipuAI/GLM-5.2", "GLM-5.2")],
         "key_url": "https://modelscope.cn/my/myaccesstoken", "note": tr("阿里的开源模型社区，每天有免费调用次数（要绑定阿里云账号）。")},
        # ---- 雲端 API 服務 ----
        {"id": "openai", "region": "intl", "name": "OpenAI", "base_url": "https://api.openai.com/v1", "model": "gpt-6-luna", "key": True, "free": False, "api": "responses",
         "models": [_m("gpt-6-luna", "GPT-6 Luna", tr("最便宜"), True), _m("gpt-6.1-sol", "GPT-6.1 Sol", tr("均衡"), True), _m("gpt-6-astra", "GPT-6 Astra", tr("最强"), True)],
         "key_url": "https://platform.openai.com/api-keys", "note": tr("用 Responses 接口。")},
        {"id": "anthropic", "region": "intl", "name": "Anthropic", "base_url": "https://api.anthropic.com/v1", "model": "claude-sonnet-5-5", "key": True, "free": False,
         "models": [_m("claude-sonnet-5-5", "Claude Sonnet 5.5", tr("均衡"), True), _m("claude-opus-5-5", "Claude Opus 5.5", tr("更强"), True),
                    _m("claude-haiku-4-5", "Claude Haiku 4.5", tr("最快最省"), True), _m("claude-fable-5-1", "Claude Fable 5.1", tr("最强、最贵"), True)],
         "key_url": "https://platform.claude.com/settings/keys", "note": tr("Claude 的 API（按量付费，和 Claude 订阅是两回事；有订阅就用上面的 Claude Code）。")},
        {"id": "gemini", "region": "intl", "name": "Google Gemini", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "model": "gemini-3.8-flash", "key": True, "free": True,
         "models": [_m("gemini-3.8-flash", "Gemini 3.8 Flash", tr("有免费额度、能看图"), True), _m("gemini-3.5-flash-lite", "Gemini 3.5 Flash-Lite", tr("有免费额度、最快"), True),
                    _m("gemini-3.1-pro-preview", "Gemini 3.1 Pro", tr("付费、最强"), True)],
         "key_url": "https://aistudio.google.com/apikey", "note": tr("Flash 系列有免费额度。")},
        {"id": "openrouter", "region": "intl", "name": "OpenRouter", "base_url": "https://openrouter.ai/api/v1", "model": "qwen/qwen3.8-27b:free", "key": True, "free": True,
         "models": [_m("qwen/qwen3.8-27b:free", "Qwen3.8 27B", tr("免费")), _m("google/gemma-4-31b-it:free", "Gemma 4 31B", tr("免费")),
                    _m("nvidia/nemotron-3-super-120b-a12b:free", "Nemotron 3 Super", tr("免费"))],
         "key_url": "https://openrouter.ai/keys", "note": tr("一个 Key 用各家模型；带 :free 的免费，有频率限制，名单常变，点“获取模型列表”看最新的。")},
        {"id": "groq", "region": "intl", "name": "Groq", "base_url": "https://api.groq.com/openai/v1", "model": "openai/gpt-oss-120b", "key": True, "free": True,
         "models": [_m("openai/gpt-oss-120b", "GPT-OSS 120B", tr("免费额度")), _m("qwen/qwen3.8-27b", "Qwen3.8 27B", tr("免费额度、预览")),
                    _m("llama-3.3-70b-versatile", "Llama 3.3 70B", tr("免费额度"))],
         "key_url": "https://console.groq.com/keys", "note": tr("开源模型、速度很快；有每分钟频率限制，“同时翻译几批”开 1–2。")},
        {"id": "cerebras", "region": "intl", "name": "Cerebras", "base_url": "https://api.cerebras.ai/v1", "model": "gpt-oss-120b", "key": True, "free": True,
         "models": [_m("gpt-oss-120b", "GPT-OSS 120B", tr("免费额度")), _m("qwen-3.8-27b", "Qwen3.8 27B", tr("免费额度"))],
         "key_url": "https://cloud.cerebras.ai", "note": tr("开源模型、速度很快。")},
        # ---- 本機 ----
        {"id": "ollama", "region": "local", "name": "Ollama", "base_url": "http://127.0.0.1:11434/v1", "model": "qwen3.5:9b", "key": False, "free": True,
         "models": [_m("qwen3.5:9b", "Qwen3.5 9B", tr("下载 6.6 GB，推荐")), _m("qwen3.5:4b", "Qwen3.5 4B", tr("下载 3.4 GB，显卡小用")),
                    _m("qwen3.5:27b", "Qwen3.5 27B", tr("下载 17 GB，译得更好")), _m("gemma4:12b", "Gemma 4 12B")],
         "key_url": "https://ollama.com/download", "note": tr("装好 Ollama，再在终端运行 ollama pull qwen3.5:9b。完全离线、免费。")},
        {"id": "lmstudio", "region": "local", "name": "LM Studio", "base_url": "http://127.0.0.1:1234/v1", "model": "", "key": False, "free": True,
         "models": [],
         "key_url": "https://lmstudio.ai", "note": tr("在 LM Studio 里下载模型，打开 Developer → Start Server，再点“获取模型列表”选一个。")},
    ]


def _same(text: str) -> str:
    return text


PRESETS = _build(_same)


def presets() -> list[dict]:
    """給介面顯示用：名稱、說明按當前語言（語言執行時才知道、還能切換，所以每次現算）。"""
    from .i18n import tr
    visible = [p for p in _build(tr) if p['region'] != 'cn']
    for p in visible:
        # Discover models from the provider instead of shipping regional recommendations.
        p.update(model='', models=[], free=False)
        p['note'] = tr('費用、可用模型與使用限制以服務商為準；請讀取模型清單或自行輸入模型 ID。') if p['region'] != 'local' else tr('請先在本機下載模型並啟動服務，再讀取模型清單。模型授權與硬體需求依所選模型而定。')
    return visible


def localized(preset_id: str | None) -> dict | None:
    return next((p for p in presets() if p["id"] == preset_id), None)


# 保留舊介面欄位；目前不依服務商預設任何代理連線需求。
NEEDS_VPN = set()
PRESET_GROUPS = [("intl", "雲端 API 服務"), ("local", "本機模型服務")]  # i18n-ok


def preset_groups() -> list[tuple[str, str]]:
    from .i18n import tr
    return [("intl", tr("雲端 API 服務")), ("local", tr("本機模型服務"))]
