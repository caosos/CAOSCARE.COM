import React from "react";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Building2, ArrowRight } from "lucide-react";

// Blueprint section 1: "If a prerequisite is missing, CAOSCARE should show
// a clear setup action rather than silently displaying empty operational
// screens." No facility/community record is the root prerequisite - every
// downstream tab (residents, departments, requests, menu, schedule) can
// render today with zero facilities configured, which is exactly the gap
// the 2026-08-23 admin visual audit flagged as severe. This banner sits on
// the main "Community administration" screen itself (not two clicks deep
// in Facility & Staff -> Facilities) so it can't be missed.
export default function FacilitySetupBanner({ facilities, loaded, isOwner, onSetup }) {
  if (!loaded || facilities.length > 0) return null;

  return (
    <Card
      className="p-5 mb-6 border-2 border-caos-terracotta bg-caos-terracotta/5 flex items-center justify-between flex-wrap gap-4"
      data-testid="facility-setup-banner"
    >
      <div className="flex items-start gap-3">
        <Building2 className="w-6 h-6 text-caos-terracotta mt-0.5 shrink-0" />
        <div>
          <h2 className="font-display text-xl text-caos-forest">No community set up yet</h2>
          <p className="text-caos-mute text-sm mt-1 max-w-xl">
            Residents, departments, requests, and schedules all exist, but no facility record
            owns them yet. Set up your community first so this data is properly scoped.
          </p>
        </div>
      </div>
      {isOwner ? (
        <Button
          onClick={onSetup}
          className="bg-caos-terracotta hover:bg-caos-terracotta-dark rounded-full shrink-0"
          data-testid="facility-setup-cta"
        >
          Set up your community <ArrowRight className="w-4 h-4 ml-2" />
        </Button>
      ) : (
        <span className="text-sm text-caos-mute italic shrink-0">Ask an owner to set up the community.</span>
      )}
    </Card>
  );
}
