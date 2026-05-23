export default function Bundles() {
  return (
    <>
      <h1>Bundles</h1>
      <p className="sub">Phase 2: automatic collect from nodes. Phase 1: use Live / Lets Check Logs for live tail.</p>
      <div className="card">
        <p>Manual bundle upload (.tar.gz) will be added in the next release.</p>
        <p className="pill">For now, all cluster logs are available via Live Monitor and Lets Check Logs (docker exec).</p>
      </div>
    </>
  );
}
