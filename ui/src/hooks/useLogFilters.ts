import { useCallback, useMemo, useState } from "react";

export function useLogFilters(defaultCluster: string) {
  const [clusterId, setClusterId] = useState(defaultCluster);
  const [node, setNode] = useState("all");
  const [severity, setSeverity] = useState(
    () => new Set<"critical" | "warning" | "info">(["critical", "warning", "info"]),
  );
  const [patroni, setPatroni] = useState("include");
  const [postgres, setPostgres] = useState("include");
  const [etcd, setEtcd] = useState("include");
  const [osLog, setOsLog] = useState("include");
  const [search, setSearch] = useState("");
  const [suppressPeerNoise, setSuppressPeerNoise] = useState(false);

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
    return p;
  }, [node, severity, patroni, postgres, etcd, osLog, search, suppressPeerNoise]);

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
    applyPreset,
    params,
  };
}
