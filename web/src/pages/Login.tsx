import { useState, type FormEvent } from "react";
import { api } from "../api";
import { useI18n } from "../i18n";

export default function Login({ onLogin }: { onLogin: (u: string) => void }) {
  const { t, lang, setLang } = useI18n();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      onLogin((await api.login(username, password)).user);
    } catch {
      setError(t("loginFailed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="panel login stack" onSubmit={submit}>
      <div className="row">
        <h1 style={{ margin: 0 }}>{t("appName")}</h1>
        <span className="spacer" />
        <select value={lang} onChange={(e) => setLang(e.target.value as "zh" | "ko")} aria-label="language">
          <option value="zh">中文</option>
          <option value="ko">한국어</option>
        </select>
      </div>
      <label className="field"><span>{t("username")}</span>
        <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
      </label>
      <label className="field"><span>{t("password")}</span>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password" autoFocus />
      </label>
      {error && <div className="error">{error}</div>}
      <button className="primary" disabled={busy}>{t("login")}</button>
    </form>
  );
}
