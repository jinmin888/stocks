import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, type KakaoStatus } from "../api";
import { fmtTime } from "../format";
import { useI18n } from "../i18n";

export default function Settings() {
  const { t, lang } = useI18n();
  const [params] = useSearchParams();
  const [st, setSt] = useState<KakaoStatus | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const load = () => api.kakaoStatus().then(setSt).catch((e) => setMsg({ ok: false, text: e.message }));
  useEffect(() => {
    load();
    const k = params.get("kakao");
    if (k === "connected") setMsg({ ok: true, text: t("kakaoConnected") });
    if (k === "error") setMsg({ ok: false, text: `${t("kakaoError")}: ${params.get("reason") ?? ""}` });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const act = async (fn: () => Promise<unknown>, okText?: string) => {
    setBusy(true);
    setMsg(null);
    try {
      await fn();
      if (okText) setMsg({ ok: true, text: okText });
      await load();
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack">
      <h1>{t("settings")}</h1>
      <div className="panel stack">
        <h2>{t("kakao")}</h2>
        {!st ? <div className="muted">{t("loading")}</div> : !st.configured ? (
          <div className="muted">{t("kakaoNotConfigured")}</div>
        ) : (
          <>
            <div className="row">
              <span className={`badge ${st.connected ? "done" : ""}`}>
                {st.connected ? t("kakaoConnected") : t("kakaoNotConnected")}
              </span>
              {st.connected && st.refresh_expires_at && (
                <span className="muted small">{t("kakaoRefreshExpires")}: {fmtTime(st.refresh_expires_at, lang)}</span>
              )}
            </div>
            <div className="row">
              {/* 授权需要整页跳转到 Kakao，不能用 fetch */}
              <a href="/api/kakao/login"><button className={st.connected ? "" : "primary"}>
                {st.connected ? t("kakaoReconnect") : t("kakaoConnect")}</button></a>
              {st.connected && (
                <>
                  <button disabled={busy} onClick={() => act(api.kakaoTest, t("kakaoTestSent"))}>{t("kakaoTest")}</button>
                  <button className="danger" disabled={busy} onClick={() => act(api.kakaoDisconnect)}>{t("kakaoDisconnect")}</button>
                </>
              )}
            </div>
          </>
        )}
        {msg && <div className={msg.ok ? "" : "error"}>{msg.text}</div>}
        {msg && !msg.ok && <div className="muted small">{t("kakaoErrors")}</div>}
        {st && (
          <div className="muted small stack" style={{ gap: 4 }}>
            <div>{t("kakaoLang")}: <code>{st.lang}</code></div>
          </div>
        )}
      </div>

      <div className="panel stack">
        <h2>{t("kakaoSetupTitle")}</h2>
        <ol className="stack" style={{ gap: 6, margin: 0, paddingLeft: 20 }}>
          <li>{t("kakaoStep1")}</li>
          <li>{t("kakaoStep2")}</li>
          <li>{t("kakaoStep3")}<br /><code className="copy">{st?.redirect_uri ?? "…"}</code></li>
          <li><strong>{t("kakaoStep4")}</strong></li>
          <li>{t("kakaoStep5")}<br /><code className="copy">{st ? new URL(st.redirect_uri).origin : "…"}</code></li>
          <li>{t("kakaoStep6")}</li>
        </ol>
        <div className="muted small">{t("kakaoConsentNote")}</div>
        <div className="muted small">{t("kakaoErrors")}</div>
      </div>
    </div>
  );
}
