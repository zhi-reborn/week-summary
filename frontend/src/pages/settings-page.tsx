import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, ApiClientError } from "../api/client";

type ModelSettings = {
  base_url: string;
  model: string;
  timeout_seconds: number;
  max_retries: number;
  temperature: number;
  context_tokens: number | null;
  has_api_key: boolean;
};

type ModelCapabilities = {
  reachable: boolean;
  model_callable: boolean;
  json_mode: boolean;
  message: string;
};

const EMPTY_SETTINGS: ModelSettings = {
  base_url: "http://127.0.0.1:8000/v1",
  model: "",
  timeout_seconds: 120,
  max_retries: 2,
  temperature: 0.1,
  context_tokens: null,
  has_api_key: false,
};

export function SettingsPage() {
  const [settings, setSettings] = useState(EMPTY_SETTINGS);
  const [apiKey, setApiKey] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api<ModelSettings>("/api/settings/model")
      .then(setSettings)
      .catch((reason: ApiClientError) => {
        if (reason.code !== "MODEL_SETTINGS_NOT_CONFIGURED") setError(reason.message);
      });
  }, []);

  async function save(event: FormEvent) {
    event.preventDefault();
    setError("");
    const saved = await api<ModelSettings>("/api/settings/model", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...settings, has_api_key: undefined, api_key: apiKey || undefined }),
    });
    setSettings(saved);
    setApiKey("");
    setMessage("配置已保存");
  }

  async function testConnection() {
    setError("");
    try {
      const result = await api<ModelCapabilities>("/api/settings/model/test", { method: "POST" });
      setMessage(result.json_mode ? "连接成功 · 支持结构化 JSON" : "连接成功 · 使用普通 JSON 模式");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "连接失败");
    }
  }

  return (
    <main className="page-shell workflow-page settings-page">
      <Link className="back-link" to="/">← 返回首页</Link>
      <header><p className="eyebrow">Private Model / Connection</p><h1>模型连接设置</h1></header>
      {error ? <div className="error-banner" role="alert">{error}</div> : null}
      {message ? <div className="success-banner" role="status">{message}</div> : null}
      <form className="settings-form" onSubmit={(event) => { void save(event); }}>
        <label>Base URL<input aria-label="Base URL" required value={settings.base_url} onChange={(event) => setSettings({ ...settings, base_url: event.target.value })} /></label>
        <label>模型名<input aria-label="模型名" required value={settings.model} onChange={(event) => setSettings({ ...settings, model: event.target.value })} /></label>
        <label>API Key<input aria-label="API Key" autoComplete="off" type="password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder={settings.has_api_key ? "留空则保留已保存密钥" : "可选"} /><span>{settings.has_api_key ? "已保存密钥" : "未配置密钥"}</span></label>
        <div className="settings-row">
          <label>超时（秒）<input aria-label="超时" min="5" max="900" type="number" value={settings.timeout_seconds} onChange={(event) => setSettings({ ...settings, timeout_seconds: Number(event.target.value) })} /></label>
          <label>重试次数<input aria-label="重试次数" min="0" max="5" type="number" value={settings.max_retries} onChange={(event) => setSettings({ ...settings, max_retries: Number(event.target.value) })} /></label>
          <label>温度<input aria-label="温度" min="0" max="1" step="0.1" type="number" value={settings.temperature} onChange={(event) => setSettings({ ...settings, temperature: Number(event.target.value) })} /></label>
          <label>上下文长度<input aria-label="上下文长度" min="2048" type="number" value={settings.context_tokens ?? ""} onChange={(event) => setSettings({ ...settings, context_tokens: event.target.value ? Number(event.target.value) : null })} /></label>
        </div>
        <div className="footer-actions">
          <button className="text-action" onClick={() => { void testConnection(); }} type="button">测试连接</button>
          <button className="primary-action" type="submit">保存配置</button>
        </div>
      </form>
    </main>
  );
}
