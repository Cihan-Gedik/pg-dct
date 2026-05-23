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
    return p;
  }, [node, severity, patroni, postgres, etcd, osLog, search]);

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
    params,
  };
}
