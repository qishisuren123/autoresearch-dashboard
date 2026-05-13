"""
LLM 统一调用客户端
支持: Gemini (OpenAI兼容) / Claude (evomap gateway) / GPT-5.5 (灵活免费 + 收费中转站双通道)
所有 key 从 /data/renyiming/config.json 读取

免费窗口路由（北京时间 00:00-08:00）：
  - GPT-5.5: 优先走 linghuo（anyrouter.top, Responses API），失败回落收费中转站
  - Claude:  ⚠️ 当前 anyrouter 网关对 Anthropic 协议有 bug（panic / 误报 1m 错误），
             call_claude 始终走收费 evomap。免费版本仅供 Claude Code CLI 使用。
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


def _is_linghuo_free_window():
    """北京时间（UTC+8）00:00–08:00 为灵活Claude免费时段"""
    import datetime
    bj_hour = (datetime.datetime.utcnow().hour + 8) % 24
    return 0 <= bj_hour < 8


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
                content = resp.json()["choices"][0]["message"].get("content")
                if content is None:
                    # thinking 模型 max_tokens 过小时无输出，重试无意义
                    print(f"  [Gemini] 无输出内容（max_tokens 过小或全用于 thinking）")
                    return None
                return content
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
# 灵活 Claude（anyrouter.top，免费窗口，通过 Claude Code CLI 调用）
# 直接 API 调有 bug，但 CLI 加 --betas context-1m-2025-08-07 可以正常工作。
# ============================================================
def call_linghuo_claude(prompt, model="claude-opus-4-7", temperature=0.3, max_tokens=2000):
    """通过 Claude Code CLI 调用 anyrouter 免费渠道（1M context）。
    北京时间 00:00-08:00 免费；逐 key 轮换；--no-session-persistence 保证无状态。
    成功返回字符串；全部失败返回 None。"""
    import subprocess, os

    lh_cfg = get_preset("linghuo-claude")
    if not lh_cfg:
        return None

    keys = lh_cfg.get("auth_keys", [])
    base_url = lh_cfg["base_url"]

    for i, key in enumerate(keys):
        print(f"  [灵活Claude/{model}] 尝试 key {i+1}/{len(keys)}...")
        env = os.environ.copy()
        env["ANTHROPIC_AUTH_TOKEN"] = key
        env["ANTHROPIC_BASE_URL"] = base_url

        cmd = [
            "claude", "-p", prompt,
            "--model", model,
            "--betas", "context-1m-2025-08-07",
            "--no-session-persistence",
            "--dangerously-skip-permissions",
        ]
        try:
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=lh_cfg.get("timeout", 3600),
                stdin=subprocess.DEVNULL,
            )
            if result.returncode == 0:
                out = result.stdout.strip()
                if out:
                    return out
                print(f"  [灵活Claude] key {i+1} 返回为空，尝试下一个")
            else:
                err = (result.stderr or result.stdout or "").strip()
                print(f"  [灵活Claude] key {i+1} 失败(exit {result.returncode}): {err[:150]}")
        except subprocess.TimeoutExpired:
            print(f"  [灵活Claude] key {i+1} 超时")
        except Exception as e:
            print(f"  [灵活Claude] key {i+1} 异常: {type(e).__name__}: {e}")

    print(f"  [灵活Claude/{model}] 所有 key 均失败")
    return None


# ============================================================
# Claude 系列（主入口：免费窗口优先灵活Claude CLI，否则走收费evomap）
# ============================================================
def call_claude(prompt, preset_name="claude-sonnet-4-6", temperature=0.3, max_tokens=2000, retries=3):
    resolved = _resolve_claude_preset(preset_name)
    cfg = get_preset(resolved)
    if not cfg:
        print(f"  [Claude] 未找到 preset: {resolved}")
        return None

    # 免费窗口：优先灵活Claude CLI
    if _is_linghuo_free_window():
        result = call_linghuo_claude(
            prompt, model=cfg["model"],
            temperature=temperature, max_tokens=max_tokens,
        )
        if result is not None:
            return result
        print(f"  [Claude] 灵活Claude 全部失败，回落收费版本 ({resolved})")

    # 收费版本（evomap gateway）
    if cfg.get("provider") != "anthropic_gateway":
        print(f"  [Claude] preset {resolved} 不是 anthropic_gateway，请更新 config.json")
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
                for block in data.get("content", []):
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
# 灵活 GPT-5.5（anyrouter.top，免费窗口，OpenAI Responses API）
# ============================================================
def _extract_responses_text(data):
    """从 Responses API 返回体里提取最终的 output_text"""
    for item in data.get("output", []):
        if isinstance(item, dict) and item.get("type") == "message":
            for c in item.get("content", []):
                if isinstance(c, dict) and c.get("type") == "output_text":
                    return c.get("text", "")
    return ""


def call_linghuo_gpt(prompt, preset_name="linghuo-gpt-5.5", max_output_tokens=None):
    """北京时间00:00-08:00免费；多 key 轮换；走 OpenAI Responses API。
    成功返回字符串；全部 key 失败返回 None（上层应回落到收费渠道）。"""
    cfg = get_preset(preset_name)
    if not cfg or cfg.get("provider") != "openai_responses":
        return None

    keys = cfg.get("auth_keys", [])
    if not keys:
        return None
    timeout = cfg.get("timeout", 600)
    url = cfg["base_url"].rstrip("/") + cfg.get("endpoint", "/v1/responses")
    model = cfg["model"]

    payload = {"model": model, "input": prompt}
    if max_output_tokens is not None:
        payload["max_output_tokens"] = max_output_tokens

    for i, key in enumerate(keys):
        print(f"  [灵活GPT/{model}] 尝试 key {i+1}/{len(keys)}...")
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
        try:
            req_kwargs = {"timeout": timeout}
            if cfg.get("needs_proxy"):
                req_kwargs["proxy"] = PROXY_URL
            resp = httpx.post(url, headers=headers, json=payload, **req_kwargs)
            if resp.status_code == 200:
                text = _extract_responses_text(resp.json())
                if text:
                    return text
                print(f"  [灵活GPT] key {i+1} 200 但无文本输出，尝试下一个")
            else:
                print(f"  [灵活GPT] key {i+1} HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"  [灵活GPT] key {i+1} 失败: {type(e).__name__}: {e}")

    print(f"  [灵活GPT/{model}] 所有 key 均失败")
    return None


# ============================================================
# GPT-5.5（主入口：免费窗口优先灵活，否则走收费中转站）
# ============================================================
def call_gpt(prompt, temperature=0.3, max_tokens=2000, retries=2, force_paid=False):
    """免费窗口优先 anyrouter（免费），失败或非免费窗口走 35.220.164.252 中转站（收费）。
    force_paid=True 可强制走收费版本（用于排除灵活渠道质量问题时）。"""
    # 1) 免费窗口优先灵活
    if not force_paid and _is_linghuo_free_window():
        result = call_linghuo_gpt(prompt, "linghuo-gpt-5.5", max_output_tokens=max_tokens)
        if result:
            return result
        print(f"  [GPT] 灵活GPT 全部失败，回落收费中转站")

    # 2) 收费中转站（OpenAI Chat Completions 格式）
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
                print(f"  [GPT/收费] HTTP {resp.status_code}: {resp.text[:100]}")
                return None
        except Exception as e:
            if attempt < retries:
                time.sleep(5)
                continue
            print(f"  [GPT/收费] 失败: {e}")
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
    import datetime
    bj_hour = (datetime.datetime.utcnow().hour + 8) % 24
    free = _is_linghuo_free_window()
    print(f"测试所有模型连通性... (北京时间 {bj_hour:02d}:xx，免费窗口: {free})")
    print(f"  Gemini Flash:        {call_flash('1+1=?', max_tokens=20)}")
    print(f"  GPT-5.5(自动路由):   {call_gpt('1+1=?', max_tokens=30)}")
    print(f"  GPT-5.5(强制收费):   {call_gpt('1+1=?', max_tokens=30, force_paid=True)}")
    if free:
        print(f"  GPT-5.5(灵活直调):   {call_linghuo_gpt('1+1=?', max_output_tokens=30)}")
    print(f"  Claude Sonnet:       {call_claude('1+1=?', 'claude-sonnet-4-6', max_tokens=20)}")
    print(f"  Claude Opus:         {call_claude('1+1=?', 'claude-opus-4-7', max_tokens=20)}")
