/** Cooperative audio-owner watchdog. Its 30s deadline is shorter than
 * the server's 45s stale takeover. Rejection immediately tears down media.
 * Browser suspension/media behavior still requires physical verification.
 */
export function createLeaseWatchdog({ heartbeat, onLost, intervalMs = 10000, deadlineMs = 30000 }) {
  let closed = false, deadline, interval, inFlight = false;
  const lose = (reason) => {
    if (closed) return;
    close();
    onLost(reason);
  };
  const arm = () => {
    clearTimeout(deadline);
    deadline = setTimeout(() => lose("lease_heartbeat_expired"), deadlineMs);
  };
  async function beat() {
    if (closed || inFlight) return false;
    inFlight = true;
    try {
      const ok = await heartbeat();
      if (closed) return false;
      if (!ok) { lose("lease_rejected"); return false; }
      arm();
      return true;
    } catch {
      // Retain the existing deadline; failure must never extend ownership.
      return false;
    } finally { inFlight = false; }
  }
  function close() {
    closed = true;
    clearTimeout(deadline);
    clearInterval(interval);
  }
  arm();
  interval = setInterval(beat, intervalMs);
  return { beat, close };
}
