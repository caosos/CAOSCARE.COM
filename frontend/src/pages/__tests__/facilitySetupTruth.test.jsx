import React, { act } from "react";
import { createRoot } from "react-dom/client";

jest.mock("@/lib/utils", () => ({ cn: (...values) => values.filter(Boolean).join(" ") }), { virtual: true });

import FacilitySetupBanner from "../FacilitySetupBanner";
import { fetchFacilitySnapshot } from "../../lib/facilityLoad";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

test("facility loader distinguishes empty success from request failure", async () => {
  const empty = await fetchFacilitySnapshot({ get: jest.fn().mockResolvedValue({ data: [] }) });
  const failed = await fetchFacilitySnapshot({ get: jest.fn().mockRejectedValue(new Error("down")) });
  const invalid = await fetchFacilitySnapshot({ get: jest.fn().mockResolvedValue({ data: {} }) });

  expect(empty).toEqual({ loadState: "ready", facilities: [] });
  expect(failed).toEqual({ loadState: "error", facilities: null });
  expect(invalid).toEqual({ loadState: "error", facilities: null });
});

async function renderBanner(props) {
  const element = document.createElement("div");
  const root = createRoot(element);
  await act(async () => {
    root.render(
      <FacilitySetupBanner
        facilities={[]}
        loadState="loading"
        isOwner
        onSetup={() => {}}
        onRetry={() => {}}
        {...props}
      />,
    );
  });
  return { element, root };
}

test("a failed facility read is never presented as no community", async () => {
  const onRetry = jest.fn();
  const { element, root } = await renderBanner({ loadState: "error", onRetry });

  expect(element.querySelector("[data-testid=facility-load-error]")).not.toBeNull();
  expect(element.querySelector("[data-testid=facility-setup-banner]")).toBeNull();
  expect(element.textContent).toContain("This does not mean no community exists");

  await act(async () => {
    element.querySelector("[data-testid=facility-load-retry]").click();
  });
  expect(onRetry).toHaveBeenCalledTimes(1);
  await act(async () => root.unmount());
});

test("only a successful empty response offers community setup", async () => {
  const onSetup = jest.fn();
  const { element, root } = await renderBanner({ loadState: "ready", onSetup });

  expect(element.querySelector("[data-testid=facility-setup-banner]")).not.toBeNull();
  expect(element.querySelector("[data-testid=facility-load-error]")).toBeNull();
  await act(async () => {
    element.querySelector("[data-testid=facility-setup-cta]").click();
  });
  expect(onSetup).toHaveBeenCalledTimes(1);
  await act(async () => root.unmount());
});

test.each([
  ["loading", []],
  ["ready", [{ facility_id: "fac_existing" }]],
  ["error", [{ facility_id: "fac_last_known" }]],
])("%s with known state does not claim an empty community", async (loadState, facilities) => {
  const { element, root } = await renderBanner({ loadState, facilities });
  expect(element.querySelector("[data-testid=facility-setup-banner]")).toBeNull();
  expect(element.querySelector("[data-testid=facility-load-error]")).toBeNull();
  await act(async () => root.unmount());
});
