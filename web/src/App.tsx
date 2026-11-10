import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { api, type Meta } from "./api";
import { useI18n } from "./i18n";
import Login from "./pages/Login";
import RunView from "./pages/RunView";
import Runs from "./pages/Runs";
import Settings from "./pages/Settings";
import TaskEdit from "./pages/TaskEdit";
import Tasks from "./pages/Tasks";

export default function App() {
  const { t, lang, setLang } = useI18n();
  const [user, setUser] = useState<string | null | undefined>(undefined);
  const [meta, setMeta] = useState<Meta | null>(null);

  useEffect(() => {
    api.me().then((r) => setUser(r.user)).catch(() => setUser(null));
    const onUnauth = () => setUser(null);
    window.addEventListener("unauthorized", onUnauth);
    return () => window.removeEventListener("unauthorized", onUnauth);
  }, []);
  useEffect(() => {
    if (user) api.meta().then(setMeta).catch(() => {});
  }, [user]);

  if (user === undefined) return <div className="container muted">{t("loading")}</div>;
  if (user === null) return <Login onLogin={setUser} />;

  return (
    <>
      <header className="topbar">
        <span className="brand">{t("appName")}</span>
        <nav>
          <NavLink to="/tasks">{t("tasks")}</NavLink>
          <NavLink to="/runs">{t("history")}</NavLink>
          <NavLink to="/settings">{t("settings")}</NavLink>
        </nav>
        <select value={lang} onChange={(e) => setLang(e.target.value as "zh" | "ko")} aria-label="language">
          <option value="zh">中文</option>
          <option value="ko">한국어</option>
        </select>
        <button className="link" onClick={() => api.logout().finally(() => setUser(null))}>{t("logout")}</button>
      </header>
      <main className="container">
        {!meta ? <div className="muted">{t("loading")}</div> : (
          <Routes>
            <Route path="/" element={<Navigate to="/tasks" replace />} />
            <Route path="/tasks" element={<Tasks />} />
            <Route path="/tasks/new" element={<TaskEdit meta={meta} />} />
            <Route path="/tasks/:id" element={<TaskEdit meta={meta} />} />
            <Route path="/runs" element={<Runs />} />
            <Route path="/runs/:id" element={<RunView />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/tasks" replace />} />
          </Routes>
        )}
      </main>
    </>
  );
}
