import { useCallback, useEffect, useState } from "react";
import { appConfig } from "../config/appConfig";
import { getDashboardStatus } from "../services/jarvisApi";
import type { DashboardStatus } from "../types/dashboard";

type PrependLogs = (entries: string[]) => void;

export function useDashboardStatus(prependLogs: PrependLogs) {
  const [dashboard, setDashboard] = useState<DashboardStatus | null>(null);
  const [dashboardStatus, setDashboardStatus] = useState("Checking dashboard...");

  const refreshDashboard = useCallback(async (logResult = false) => {
    try {
      const res = await getDashboardStatus();
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const data: DashboardStatus = await res.json();
      setDashboard(data);
      setDashboardStatus("Dashboard connected");

      if (logResult) {
        prependLogs(["Dashboard status refreshed"]);
      }
    } catch (error) {
      console.error(error);
      setDashboardStatus("Dashboard offline");
      if (logResult) {
        prependLogs(["Dashboard status refresh failed"]);
      }
    }
  }, [prependLogs]);

  useEffect(() => {
    const dashboardTimer = setInterval(
      () => refreshDashboard(false),
      appConfig.dashboardRefreshMs
    );
    return () => clearInterval(dashboardTimer);
  }, [refreshDashboard]);

  return {
    dashboard,
    dashboardStatus,
    refreshDashboard,
  };
}
