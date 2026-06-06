import { useCallback, useMemo, useState } from "react";

export const LOG_RANGE_PRESETS = [
  { label: "2h", hours: 2 },
  { label: "8h", hours: 8 },
  { label: "1d", hours: 24 },
  { label: "3d", hours: 72 },
  { label: "7d", hours: 168 },
  { label: "30d", hours: 720 },
] as const;

export type LogTimeRange = number | "all" | "custom";

function toDatetimeLocalValue(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function parseSeverityParam(raw: string | null | undefined): Set<"critical" | "warning" | "info"> | null {
  if (!raw?.trim()) return null;
  const allowed = new Set<"critical" | "warning" | "info">(["critical", "warning", "info"]);
  const levels = raw
    .split(",")
    .map((s) => s.trim().toLowerCase())
    .filter((s): s is "critical" | "warning" | "info" => allowed.has(s as "critical" | "warning" | "info"));
  return levels.length ? new Set(levels) : null;
}

export function formatLogTimeRangeLabel(
  timeRange: LogTimeRange,
  rangeFrom: string,
  rangeTo: string,
): string {
  if (timeRange === "all") return "All time";
  if (timeRange === "custom") {
    if (rangeFrom || rangeTo) {
      const fmt = (v: string) =>
        v ? new Date(v).toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" }) : "…";
      return `${fmt(rangeFrom)} → ${fmt(rangeTo)}`;
    }
    return "Custom range";
  }
  const preset = LOG_RANGE_PRESETS.find((p) => p.hours === timeRange);
  return preset ? `Last ${preset.label}` : `Last ${timeRange}h`;
}

type LogFilterOptions = {
  defaultTimeRange?: LogTimeRange;
};

export function useLogFilters(
  defaultCluster: string,
  initialSeverity?: string | null,
  options?: LogFilterOptions,
) {
  const [clusterId, setClusterId] = useState(defaultCluster);
  const [node, setNode] = useState("all");
  const [severity, setSeverity] = useState(() => {
    const fromUrl = parseSeverityParam(initialSeverity);
    return fromUrl ?? new Set<"critical" | "warning" | "info">(["critical", "warning", "info"]);
  });
  const [patroni, setPatroni] = useState("include");
  const [postgres, setPostgres] = useState("include");
  const [etcd, setEtcd] = useState("include");
  const [osLog, setOsLog] = useState("include");
  const [search, setSearch] = useState("");
  const [suppressPeerNoise, setSuppressPeerNoise] = useState(false);
  const [timeRange, setTimeRangeState] = useState<LogTimeRange>(options?.defaultTimeRange ?? 24);
  const [rangeFrom, setRangeFrom] = useState("");
  const [rangeTo, setRangeTo] = useState("");

  const setTimeRange = useCallback(
    (next: LogTimeRange) => {
      if (next === "custom" && !rangeFrom && !rangeTo) {
        const now = new Date();
        const dayAgo = new Date(now.getTime() - 24 * 3600 * 1000);
        setRangeFrom(toDatetimeLocalValue(dayAgo));
        setRangeTo(toDatetimeLocalValue(now));
      }
      setTimeRangeState(next);
    },
    [rangeFrom, rangeTo],
  );

  const toggleSeverity = useCallback((level: "critical" | "warning" | "info") => {
    setSeverity((prev) => {
      const next = new Set(prev);
      if (next.has(level)) {
        next.delete(level);
        if (next.size === 0) return new Set(["critical", "warning", "info"]);
      } else {
        next.add(level);
      }
      return next;
    });
  }, []);

  const applySeverityParam = useCallback((raw: string | null | undefined) => {
    const parsed = parseSeverityParam(raw);
    if (parsed) setSeverity(parsed);
  }, []);

  const timeRangeLabel = useMemo(
    () => formatLogTimeRangeLabel(timeRange, rangeFrom, rangeTo),
    [timeRange, rangeFrom, rangeTo],
  );

  const params = useMemo(() => {
    const p = new URLSearchParams();
    p.set("node", node);
    p.set("severity", [...severity].join(","));
    p.set("patroni", patroni);
    p.set("postgres", postgres);
    p.set("etcd", etcd);
    p.set("os", osLog);
    p.set("search", search);
    p.set("suppress_peer_noise", String(suppressPeerNoise));
    if (timeRange === "custom") {
      if (rangeFrom) p.set("range_from", new Date(rangeFrom).toISOString());
      if (rangeTo) p.set("range_to", new Date(rangeTo).toISOString());
    } else if (timeRange !== "all") {
      p.set("hours", String(timeRange));
    }
    return p;
  }, [
    node,
    severity,
    patroni,
    postgres,
    etcd,
    osLog,
    search,
    suppressPeerNoise,
    timeRange,
    rangeFrom,
    rangeTo,
  ]);

  const applyPreset = useCallback((preset: "all" | "etcd" | "patroni" | "errors") => {
    if (preset === "etcd") {
      setPatroni("exclude");
      setPostgres("exclude");
      setEtcd("include");
      setOsLog("exclude");
      return;
    }
    if (preset === "patroni") {
      setPatroni("include");
      setPostgres("exclude");
      setEtcd("exclude");
      setOsLog("exclude");
      return;
    }
    if (preset === "errors") {
      setPatroni("errors");
      setPostgres("errors");
      setEtcd("errors");
      setOsLog("errors");
      return;
    }
    setPatroni("include");
    setPostgres("include");
    setEtcd("include");
    setOsLog("include");
  }, []);

  return {
    clusterId,
    setClusterId,
    node,
    setNode,
    severity,
    toggleSeverity,
    applySeverityParam,
    patroni,
    setPatroni,
    postgres,
    setPostgres,
    etcd,
    setEtcd,
    osLog,
    setOsLog,
    search,
    setSearch,
    suppressPeerNoise,
    setSuppressPeerNoise,
    timeRange,
    setTimeRange,
    rangeFrom,
    setRangeFrom,
    rangeTo,
    setRangeTo,
    timeRangeLabel,
    applyPreset,
    params,
  };
}
