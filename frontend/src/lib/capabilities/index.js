// Every public capability panel, by id, for pages that mix audiences
// (for example /experience).
import { RESIDENT_CAPABILITIES } from "./resident";
import { COMMUNITY_WORKFLOWS } from "./community";

export const ALL_CAPABILITIES = [...RESIDENT_CAPABILITIES, ...COMMUNITY_WORKFLOWS];
export const CAPABILITIES_BY_ID = Object.fromEntries(ALL_CAPABILITIES.map((c) => [c.id, c]));
