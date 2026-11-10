import type { Run } from "../api";
import { useI18n, type Key } from "../i18n";

export default function RunStatus({ run }: { run: Run }) {
  const { t } = useI18n();
  return (
    <>
      <span className={`badge ${run.status}`}>{t(`status_${run.status}` as Key)}</span>
      {run.status === "done" && <> · {t("results")} {run.result_count}</>}
      {run.status === "running" && run.total > 0 && <> · {run.done}/{run.total}</>}
    </>
  );
}
