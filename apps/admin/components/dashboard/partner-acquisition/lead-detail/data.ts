import { PIPELINE_STAGES, type PipelineStage } from "@/lib/dashboard/partner-acquisition-data";

export {
  getPartner,
  getComplianceForPartner,
  getMeetingsForPartner,
} from "@/lib/dashboard/partner-acquisition-data";

/** The happy-path pipeline ladder shown as a progress timeline on the lead
 *  detail page. "Rejected / Not Fit" is a terminal off-ramp, not a rung, so it
 *  is excluded here and handled as a callout instead. */
export const LEAD_LIFECYCLE: PipelineStage[] = PIPELINE_STAGES.filter(
  (s) => s !== "Rejected / Not Fit",
);
