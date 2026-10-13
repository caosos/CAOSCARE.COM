import { isRetryableBootstrapError, retryKioskBootstrap } from "../kioskBootstrapRetry";

test("retries transient 502s until bootstrap succeeds", async () => {
  const operation = jest.fn()
    .mockRejectedValueOnce({ response: { status: 502 } })
    .mockRejectedValueOnce({ response: { status: 502 } })
    .mockResolvedValue({ kiosk: { kiosk_id: "k1" } });
  const sleep = jest.fn(async () => {});
  await expect(retryKioskBootstrap(operation, { sleep })).resolves.toEqual({ kiosk: { kiosk_id: "k1" } });
  expect(sleep).toHaveBeenCalledWith(1000);
  expect(sleep).toHaveBeenCalledWith(2000);
});

test("retries network errors but not terminal 404", async () => {
  const network = jest.fn().mockRejectedValueOnce(new Error("network")).mockResolvedValue("ok");
  await expect(retryKioskBootstrap(network, { sleep: async () => {} })).resolves.toBe("ok");
  const missing = jest.fn().mockRejectedValue({ response: { status: 404 } });
  await expect(retryKioskBootstrap(missing, { sleep: async () => {} })).rejects.toEqual({ response: { status: 404 } });
  expect(missing).toHaveBeenCalledTimes(1);
  expect(isRetryableBootstrapError({ response: { status: 429 } })).toBe(true);
});

test("cancellation exits without another attempt", async () => {
  let stopped = false;
  const operation = jest.fn().mockRejectedValue({ response: { status: 503 } });
  const result = await retryKioskBootstrap(operation, {
    shouldStop: () => stopped,
    sleep: async () => { stopped = true; },
  });
  expect(result).toBeNull();
  expect(operation).toHaveBeenCalledTimes(1);
});
