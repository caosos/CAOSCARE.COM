/** One poll coordinator per mounted kiosk. Cycles, not alert IDs, identify
 * new invitations. Failed connections retry with bounded backoff; a
 * completed invitation never queues the presses it already served.
 */
export function createActivationPollGate({ now = Date.now } = {}) {
  let cycle = null, attempts = 0, retryAt = null, pressCount = 0, ended = false;
  return {
    accept(alert, idle) {
      if (!alert?.activation_id || !idle) return false;
      const key = `${alert.alert_id}:${alert.activation_id}`;
      if (key !== cycle) {
        cycle = key; attempts = 0; retryAt = null; ended = false;
        pressCount = alert.press_count || 1;
        return true;
      }
      if (ended) return false;
      const freshPress = (alert.press_count || 1) > pressCount;
      if (retryAt === null || (!freshPress && (attempts >= 6 || now() < retryAt))) return false;
      if (freshPress) attempts = 0;
      pressCount = alert.press_count || pressCount;
      retryAt = null;
      return true;
    },
    finish({ retry = false } = {}) {
      ended = !retry;
      retryAt = retry ? now() + Math.min(3000 * 2 ** attempts++, 30000) : null;
    },
  };
}
