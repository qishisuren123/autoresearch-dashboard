"""
LLM 统一调用客户端
支持: Gemini (OpenAI兼容) / Claude (evomap gateway, Anthropic 原生) / GPT-5.5 (中转站)
所有 key 从 /data/renyiming/config.json 读取
"""

import json
import httpx
from pathlib import Path

CONFIG_PATH = Path("/data/renyiming/config.json")
PROXY_URL = "http://127.0.0.1:10407"


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def get_preset(name):
    config = load_config()
    return config.get("presets", {}).get(name)


def _resolve_claude_preset(name):
    """把短名映射到真实 preset 名"""
    config = load_config()
    aliases = config.get("_aliases", {})
    if name in aliases:
        name = aliases[name]
    return name


# ============================================================
# Gemini 系列（OpenAI 兼容格式，需代理）
# ============================================================
def call_gemini(prompt, preset_name="gemini-3.1-flash-lite", temperature=0.3, max_tokens=2000, retries=3):
    cfg = get_preset(preset_name)
    if not cfg:
        return None

    import time as _time
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {cfg['api_key']}",
    }
    payload = {
        "model": cfg["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    for attempt in range(retries):
        try:
            kwargs = {"timeout": 120}
            if cfg.get("needs_proxy"):
                kwargs["proxy"] = PROXY_URL
            with httpx.Client(**kwargs) as client:
                resp = client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            elif resp.status_code >= 500 and attempt < retries - 1:
                _time.sleep(5)
                continue
            else:
                print(f"  [Gemini] HTTP {resp.status_code}: {resp.text[:100]}")
                return None
        except Exception as e:
            if attempt < retries - 1:
                _time.sleep(5)
                continue
            print(f"  [Gemini] 失败(重试{retries}次): {e}")
            return None


# ============================================================
# Claude 系列（evomap gateway, Anthropic 原生 Messages API）
# ============================================================
def call_claude(prompt, preset_name="claude-sonnet-4-6", temperature=0.3, max_tokens=2000, retries=3):
    preset_name = _resolve_claude_preset(preset_name)
    cfg = get_preset(preset_name)
    if not cfg:
        print(f"  [Claude] 未找到 preset: {preset_name}")
        return None
    if cfg.get("provider") != "anthropic_gateway":
        print(f"  [Claude] preset {preset_name} 不是 anthropic_gateway，请更新 config.json")
        return None

    import time as _time
    url = cfg["base_url"].rstrip("/") + "/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {cfg['auth_token']}",
        "anthropic-version": "2023-06-01",
        "User-Agent": "curl/7.88.1",
    }
    payload = {
        "model": cfg["model"],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }

    for attempt in range(retries):
        try:
            req_kwargs = {"timeout": 180}
            if cfg.get("needs_proxy"):
                req_kwargs["proxy"] = PROXY_URL
            resp = httpx.post(url, headers=headers, json=payload, **req_kwargs)
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("content", [])
                for block in content:
                    if block.get("type") == "text":
                        return block.get("text", "")
                return None
            elif resp.status_code >= 500 and attempt < retries - 1:
                _time.sleep(5)
                continue
            else:
                print(f"  [Claude/{cfg['model']}] HTTP {resp.status_code}: {resp.text[:200]}")
                if attempt < retries - 1:
                    _time.sleep(5)
                    continue
                return None
        except Exception as e:
            if attempt < retries - 1:
                _time.sleep(5)
                continue
            print(f"  [Claude/{cfg['model']}] 失败(重试{retries}次): {e}")
            return None


# ============================================================
# GPT-5.5（中转站，OpenAI 兼容格式）
# ============================================================
def call_gpt(prompt, temperature=0.3, max_tokens=2000, retries=2):
    cfg = get_preset("gpt-5.5")
    if not cfg:
        return None

    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {cfg['api_key']}",
    }
    payload = {
        "model": cfg["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    import time
    for attempt in range(retries + 1):
        try:
            with httpx.Client(timeout=120) as client:
                resp = client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            else:
                if attempt < retries:
                    time.sleep(5)
                    continue
                print(f"  [GPT] HTTP {resp.status_code}: {resp.text[:100]}")
                return None
        except Exception as e:
            if attempt < retries:
                time.sleep(5)
                continue
            print(f"  [GPT] 失败: {e}")
            return None


# ============================================================
# 便捷接口（按任务复杂度选模型）
# ============================================================
def call_flash(prompt, **kwargs):
    """简单任务：用最便宜的 Gemini Flash Lite"""
    return call_gemini(prompt, "gemini-3.1-flash-lite", **kwargs)


def call_pro(prompt, **kwargs):
    """综合研判：用 Gemini 3.1 Pro"""
    kwargs.setdefault("temperature", 0.2)
    kwargs.setdefault("max_tokens", 3000)
    return call_gemini(prompt, "gemini-3.1-pro", **kwargs)


def call_model(model_name, prompt, **kwargs):
    """通用入口，按名称调用"""
    if model_name == "gemini-pro":
        return call_pro(prompt, **kwargs)
    elif model_name == "gemini-flash":
        return call_flash(prompt, **kwargs)
    elif model_name == "claude-opus":
        return call_claude(prompt, "claude-opus", **kwargs)
    elif model_name == "claude-sonnet":
        return call_claude(prompt, "claude-sonnet", **kwargs)
    elif model_name == "claude-haiku":
        return call_claude(prompt, "claude-haiku", **kwargs)
    elif model_name == "gpt-5.5":
        return call_gpt(prompt, **kwargs)
    else:
        print(f"  未知模型: {model_name}")
        return None


if __name__ == "__main__":
    print("测试所有模型连通性...")
    print(f"  Gemini Flash: {call_flash('1+1=?', max_tokens=20)}")
    print(f"  GPT-5.5: {call_gpt('1+1=?', max_tokens=30)}")
    print(f"  Claude Sonnet: {call_claude('1+1=?', 'claude-sonnet-4-6', max_tokens=20)}")
    print(f"  Claude Opus: {call_claude('1+1=?', 'claude-opus-4-7', max_tokens=20)}")
