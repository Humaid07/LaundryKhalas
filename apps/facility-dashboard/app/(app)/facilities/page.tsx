"use client";

import { Building2 } from "lucide-react";
import { MobilePageHeader } from "@/components/shared/MobilePageHeader";
import { FacilityManager } from "@/components/facilities/FacilityManager";

export default function FacilitiesPage() {
  return (
    <div className="lk-enter space-y-5">
      <MobilePageHeader
        eyebrow="Facilities"
        title="Your facility"
        description="Manage your facility profile, coverage, capacity, accepted services and operating status."
        icon={Building2}
      />
      <FacilityManager />
    </div>
  );
}
