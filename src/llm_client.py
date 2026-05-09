"""
LLM 调用客户端
从 /data/renyiming/config.json 读取 API 配置
支持 Gemini 3.1 Flash（简单任务）和 Gemini 3.1 Pro（综合研判）
"""

import json
import httpx
from pathlib import Path

CONFIG_PATH = Path("/data/renyiming/config.json")

# 需要代理
PROXY_URL = "http://127.0.0.1:10407"


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def get_model_config(model_name):
    """获取模型配置，model_name 可以是 'flash' 或 'pro'"""
    config = load_config()
    presets = config.get("presets", {})

    if model_name == "flash":
        return presets.get("gemini-3.1-flash-lite") or presets.get("gemini-3-flash")
    elif model_name == "pro":
        return presets.get("gemini-3.1-pro")
    elif model_name == "flash-main":
        return presets.get("gemini-3-flash") or presets.get("gemini-2.5-flash")
    else:
        return presets.get(model_name)


def call_llm(prompt, model_name="flash", temperature=0.3, max_tokens=2000):
    """
    调用 LLM
    model_name: "flash" (简单任务) / "pro" (综合研判)
    返回模型回复文本，失败返回 None
    """
    cfg = get_model_config(model_name)
    if not cfg:
        print(f"  [LLM] 配置未找到: {model_name}")
        return None

    base_url = cfg["base_url"].rstrip("/")
    api_key = cfg["api_key"]
    model = cfg["model"]
    needs_proxy = cfg.get("needs_proxy", False)

    url = f"{base_url}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:
        client_kwargs = {"timeout": 60}
        if needs_proxy:
            client_kwargs["proxy"] = PROXY_URL

        with httpx.Client(**client_kwargs) as client:
            resp = client.post(url, headers=headers, json=payload)

        if resp.status_code == 200:
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        else:
            print(f"  [LLM] HTTP {resp.status_code}: {resp.text[:200]}")
            return None
    except Exception as e:
        print(f"  [LLM] 调用失败: {e}")
        return None


def call_flash(prompt, **kwargs):
    """快速模型（简单任务：学术判断、关键词匹配）"""
    return call_llm(prompt, model_name="flash", **kwargs)


def call_pro(prompt, **kwargs):
    """强模型（综合研判：是否值得做、A+B可行性）"""
    return call_llm(prompt, model_name="pro", temperature=0.2, max_tokens=3000, **kwargs)


if __name__ == "__main__":
    print("测试 LLM 连通性...")
    result = call_flash("请用一句话回答：什么是 attention mechanism？")
    if result:
        print(f"  Flash 响应: {result[:100]}")
    else:
        print("  Flash 调用失败")
