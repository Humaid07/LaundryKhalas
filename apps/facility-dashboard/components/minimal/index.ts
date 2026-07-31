/**
 * Minimal dashboard component library — the shared building blocks for the calm,
 * progressive-disclosure UI. Import everything from here.
 */

// Page-level frame
export { MinimalKpiStrip, type MinimalKpi } from "./MinimalKpiStrip";

// Workflow/status filters for the current page
export { WorkflowTabs, type WorkflowTab } from "@/components/ui/Tabs";

// Main-page records (light previews → click through)
export { CompactRecordCard, RecordList, type CompactField } from "./CompactRecordCard";
export { DataPreviewTable, type PreviewColumn } from "./DataPreviewTable";
export { ViewDetailsButton } from "./ViewDetailsButton";

// Detail pages (the heavy information + actions)
export { DetailPageShell, DetailColumns } from "./DetailPageShell";
export { DetailSectionCard, Field, FieldGrid, Chip } from "./DetailSectionCard";
export { ActionMenu, type MenuItem } from "./ActionMenu";

// Shared primitives (canonical sources)
export { StatusBadge, Eyebrow, DeltaChip, Panel, PanelHeader } from "@/components/ui/primitives";
export { EmptyState, LoadingState, Skeleton, ErrorState } from "@/components/ui/states";
