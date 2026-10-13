const DEFAULT_DELAYS = [1000, 2000, 5000, 10000];

export function isRetryableBootstrapError(error) {
  const status = error?.response?.status;
  return status == null || status === 408 || status === 429 || status >= 500;
}

export const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/** Retry transient kiosk bootstrap failures until the page unmounts.
 * Ordinary 4xx responses remain terminal configuration errors.
 */
export async function retryKioskBootstrap(operation, {
  sleep = wait,
  shouldStop = () => false,
  delays = DEFAULT_DELAYS,
} = {}) {
  let attempt = 0;
  while (!shouldStop()) {
    try {
      return await operation();
    } catch (error) {
      if (!isRetryableBootstrapError(error)) throw error;
      const delay = delays[Math.min(attempt, delays.length - 1)];
      attempt += 1;
      await sleep(delay);
    }
  }
  return null;
}
