import { useCallback, useEffect, useRef, useState } from "react";
import { appConfig } from "../config/appConfig";
import { checkHealth } from "../services/jarvisApi";

type PrependLogs = (entries: string[]) => void;
type RefreshDashboard = (logResult?: boolean) => void;

export function useApiHealth(
  refreshDashboard: RefreshDashboard,
  prependLogs: PrependLogs
) {
  const [apiOnline, setApiOnline] = useState(false);
  const [apiStatus, setApiStatus] = useState("Checking API...");
  const mountedRef = useRef(true);
  const activeProbeRef = useRef<AbortController | null>(null);

  const probeApi = useCallback(async (logResult: boolean) => {
    if (activeProbeRef.current) return;
    const controller = new AbortController();
    activeProbeRef.current = controller;
    const timeout = window.setTimeout(() => controller.abort(), 5000);
    try {
      const res = await checkHealth(controller.signal);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      if (!mountedRef.current) return;
      setApiOnline(true);
      setApiStatus("API connected");
      if (logResult) prependLogs(["Backend health check passed"]);
    } catch (error) {
      console.error(error);
      if (!mountedRef.current) return;
      setApiOnline(false);
      setApiStatus("API offline");
      if (logResult) prependLogs(["Backend health check failed"]);
    } finally {
      window.clearTimeout(timeout);
      if (activeProbeRef.current === controller) activeProbeRef.current = null;
    }
  }, [prependLogs]);

  const checkApi = useCallback(async () => {
    await probeApi(true);
    refreshDashboard(true);
  }, [probeApi, refreshDashboard]);

  useEffect(() => {
    mountedRef.current = true;
    const timer = window.setInterval(
      () => void probeApi(false),
      appConfig.healthRefreshMs
    );
    return () => {
      mountedRef.current = false;
      window.clearInterval(timer);
      activeProbeRef.current?.abort();
    };
  }, [probeApi]);

  return {
    apiOnline,
    apiStatus,
    checkApi,
  };
}
