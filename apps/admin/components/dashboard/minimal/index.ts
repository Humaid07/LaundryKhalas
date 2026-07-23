/**
 * Minimal dashboard component library — the shared building blocks for the
 * calm, progressive-disclosure UI. Import everything from here:
 *
 *   import { MinimalPageHeader, MinimalKpiStrip, WorkflowTabs, CompactRecordCard,
 *            RecordList, DataPreviewTable, DetailPageShell, DetailColumns,
 *            DetailSectionCard, Field, FieldGrid, Chip, EmptyState, StatusBadge,
 *            ActionMenu, ViewDetailsButton } from "@/components/dashboard/minimal";
 *
 * Design rules and the progressive-disclosure contract live in
 * docs/architecture/minimal-dashboard-design-system.md.
 */

// Page-level frame
export { MinimalPageHeader } from "./MinimalPageHeader";
export { MinimalKpiStrip, type MinimalKpi } from "./MinimalKpiStrip";

// Workflow/status filters for the current page (re-exported canonical source)
export { WorkflowTabs, type WorkflowTab } from "@/components/dashboard/operations/workspace/Workspace";

// Main-page records (light previews → click through)
export { CompactRecordCard, RecordList, type CompactField } from "./CompactRecordCard";
export { DataPreviewTable, type PreviewColumn } from "./DataPreviewTable";
export { ViewDetailsButton } from "./ViewDetailsButton";

// Detail pages (the heavy information + actions)
export { DetailPageShell, DetailColumns } from "./DetailPageShell";
export { DetailSectionCard, Field, FieldGrid, Chip } from "./DetailSectionCard";
export { ActionMenu, type MenuItem } from "./ActionMenu";

// Shared primitives (canonical sources)
export { StatusBadge, Eyebrow, DeltaChip } from "@/components/dashboard/ui/primitives";
export { EmptyState, LoadingState, Skeleton, FilteredEmptyState, SnapshotBadge } from "@/components/dashboard/ui/states";
