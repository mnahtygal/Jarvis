import { useCallback, useState } from "react";
import { checkHealth } from "../services/jarvisApi";

type PrependLogs = (entries: string[]) => void;
type RefreshDashboard = (logResult?: boolean) => void;

export function useApiHealth(
  refreshDashboard: RefreshDashboard,
  prependLogs: PrependLogs
) {
  const [apiOnline, setApiOnline] = useState(false);
  const [apiStatus, setApiStatus] = useState("Checking API...");

  const checkApi = useCallback(async () => {
    try {
      const res = await checkHealth();
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      setApiOnline(true);
      setApiStatus("API connected");
      prependLogs(["Backend health check passed"]);
    } catch (error) {
      console.error(error);
      setApiOnline(false);
      setApiStatus("API offline");
      prependLogs(["Backend health check failed"]);
    }

    refreshDashboard(true);
  }, [prependLogs, refreshDashboard]);

  return {
    apiOnline,
    apiStatus,
    checkApi,
  };
}
