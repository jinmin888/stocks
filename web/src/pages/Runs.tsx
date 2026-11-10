import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Run } from "../api";
import RunStatus from "../components/RunStatus";
import { fmtTime } from "../format";
import { MARKET_NAMES, useI18n, type Key } from "../i18n";

export default function Runs() {
  const { t, lang } = useI18n();
  const [runs, setRuns] = useState<Run[] | null>(null);

  useEffect(() => {
    const load = () => api.runs().then(setRuns).catch(() => {});
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="stack">
      <h1>{t("history")}</h1>
      <div className="panel table-wrap">
        {runs === null ? <div className="muted">{t("loading")}</div> : (
          <table>
            <thead>
              <tr>
                <th>{t("time")}</th><th>{t("task")}</th><th>{t("market")}</th>
                <th>{t("timeframe")}</th><th>{t("status")}</th><th></th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id}>
                  <td>{fmtTime(r.created_at, lang)} <span className="muted small">{t(`trigger_${r.trigger}` as Key)}</span></td>
                  <td>{r.task_name}</td>
                  <td>{MARKET_NAMES[r.market]?.[lang]}</td>
                  <td>{r.timeframe}</td>
                  <td><RunStatus run={r} /></td>
                  <td><Link to={`/runs/${r.id}`}>{t("view")}</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
