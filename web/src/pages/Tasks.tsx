import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, type Task } from "../api";
import { fmtTime } from "../format";
import { MARKET_NAMES, UNIVERSE_NAMES, useI18n } from "../i18n";
import RunStatus from "../components/RunStatus";

export default function Tasks() {
  const { t, lang } = useI18n();
  const nav = useNavigate();
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => api.tasks().then(setTasks).catch((e) => setError(e.message)), []);
  useEffect(() => {
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, [load]);

  const run = async (task: Task) => {
    const { run_id } = await api.runTask(task.id);
    nav(`/runs/${run_id}`);
  };
  const remove = async (task: Task) => {
    if (!confirm(t("confirmDelete"))) return;
    await api.deleteTask(task.id);
    load();
  };

  return (
    <div className="stack">
      <div className="row">
        <h1 style={{ margin: 0 }}>{t("tasks")}</h1>
        <span className="spacer" />
        <Link to="/tasks/new"><button className="primary">{t("newTask")}</button></Link>
      </div>
      {error && <div className="error">{error}</div>}
      {tasks === null ? <div className="muted">{t("loading")}</div>
        : tasks.length === 0 ? <div className="panel muted">{t("noTasks")}</div>
        : tasks.map((task) => (
          <div className="panel task-card" key={task.id}>
            <div className="stack" style={{ gap: 6 }}>
              <div className="row">
                <strong>{task.name}</strong>
                <span className="badge">{task.timeframe}</span>
                {task.markets.map((m) => {
                  const syms = task.symbols_by_market[m] ?? [];
                  const uni = task.universes[m] ?? "";
                  return (
                    <span className="badge" key={m}>
                      {MARKET_NAMES[m][lang]} · {syms.length ? `${t("customSymbols")} ${syms.length}`
                        : UNIVERSE_NAMES[uni]?.[lang] ?? uni}
                    </span>
                  );
                })}
              </div>
              <div className="meta">
                <span>{t("nextRun")}: {task.enabled && task.cron ? fmtTime(task.next_run, lang) : t("manualOnly")}</span>
                {task.cron && <span><code>{task.cron}</code> ({task.timezone})</span>}
                <span>{t("lastRun")}: {task.last_run ? (
                  <Link to={`/runs/${task.last_run.id}`}>
                    {fmtTime(task.last_run.created_at, lang)} · <RunStatus run={task.last_run} />
                  </Link>) : "—"}
                </span>
              </div>
            </div>
            <div className="row">
              <button onClick={() => run(task)}>{t("runNow")}</button>
              <Link to={`/tasks/${task.id}`}><button>{t("edit")}</button></Link>
              <button className="danger" onClick={() => remove(task)}>{t("delete")}</button>
            </div>
          </div>
        ))}
    </div>
  );
}
