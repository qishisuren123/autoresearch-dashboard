"""
LLM 统一调用客户端
支持: Gemini (OpenAI兼容) / Claude (AWS Bedrock) / GPT-5.5 (中转站)
所有 key 从 /data/renyiming/config.json 读取
"""

import json
import httpx
import boto3
from pathlib import Path

CONFIG_PATH = Path("/data/renyiming/config.json")
PROXY_URL = "http://127.0.0.1:10407"


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def get_preset(name):
    config = load_config()
    return config.get("presets", {}).get(name)


# ============================================================
# Gemini 系列（OpenAI 兼容格式，需代理）
# ============================================================
def call_gemini(prompt, preset_name="gemini-3.1-flash-lite", temperature=0.3, max_tokens=2000):
    cfg = get_preset(preset_name)
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

    try:
        kwargs = {"timeout": 90}
        if cfg.get("needs_proxy"):
            kwargs["proxy"] = PROXY_URL
        with httpx.Client(**kwargs) as client:
            resp = client.post(url, headers=headers, json=payload)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        else:
            print(f"  [Gemini] HTTP {resp.status_code}: {resp.text[:100]}")
            return None
    except Exception as e:
        print(f"  [Gemini] 失败: {e}")
        return None


# ============================================================
# Claude 系列（AWS Bedrock invoke_model）
# ============================================================
def call_claude(prompt, preset_name="claude-haiku", temperature=0.3, max_tokens=2000):
    cfg = get_preset(preset_name)
    if not cfg:
        return None

    try:
        client = boto3.client(
            "bedrock-runtime",
            region_name=cfg["aws_region"],
            aws_access_key_id=cfg["aws_access_key_id"],
            aws_secret_access_key=cfg["aws_secret_access_key"],
        )
        response = client.invoke_model(
            modelId=cfg["model"],
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}],
            }),
        )
        result = json.loads(response["body"].read())
        return result["content"][0]["text"]
    except Exception as e:
        print(f"  [Claude/{preset_name}] 失败: {e}")
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
    print(f"  Gemini Flash: {call_flash('1+1=?', max_tokens=10)}")
    print(f"  GPT-5.5: {call_gpt('1+1=?', max_tokens=10)}")
    print(f"  Claude Haiku: {call_claude('1+1=?', 'claude-haiku', max_tokens=10)}")
