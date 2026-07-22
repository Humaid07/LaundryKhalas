// Canonical LaundryKhalas service taxonomy — MIRROR of the backend single
// source of truth at apps/whatsapp-agent/config/laundry_services.json.
//
// Synced to the live website: https://laundrykhalas.com/en-ae/personal-laundry/
// scripts/verify_service_taxonomy.py fails the build if this file drifts from
// the backend catalog. When the backend catalog changes, update this file to
// match (same service_id order + display names).

export interface ServiceCatalogEntry {
  service_id: string;
  display_name: string;
  category: string;
  unit_type: "bag" | "item" | "pair" | "set" | "sqm";
  starting_price_aed: number;
  requires_manual_quote: boolean;
}

export const SERVICE_CATALOG: readonly ServiceCatalogEntry[] = [
  { service_id: "premium_wash_fold", display_name: "Premium Wash & Fold", category: "wash_and_fold", unit_type: "bag", starting_price_aed: 60, requires_manual_quote: false },
  { service_id: "boutique_clean_press", display_name: "Boutique Clean & Press", category: "dry_cleaning", unit_type: "item", starting_price_aed: 11, requires_manual_quote: false },
  { service_id: "steam_pressing_only", display_name: "Steam Pressing Only", category: "ironing", unit_type: "item", starting_price_aed: 6, requires_manual_quote: false },
  { service_id: "luxe_bed_bath_care", display_name: "Luxe Bed & Bath Care", category: "bed_and_bath", unit_type: "set", starting_price_aed: 29, requires_manual_quote: false },
  { service_id: "artisan_shoe_restoration", display_name: "Artisan Shoe Restoration", category: "shoe_care", unit_type: "pair", starting_price_aed: 35, requires_manual_quote: false },
  { service_id: "luxury_bag_spa", display_name: "Luxury Bag Spa", category: "bag_care", unit_type: "item", starting_price_aed: 60, requires_manual_quote: true },
  { service_id: "tailoring_alterations", display_name: "Tailoring & Alterations", category: "tailoring", unit_type: "item", starting_price_aed: 20, requires_manual_quote: true },
  { service_id: "deep_carpet_curtain_care", display_name: "Deep Carpet & Curtain Care", category: "carpet_curtain", unit_type: "sqm", starting_price_aed: 15, requires_manual_quote: true },
] as const;

// Display names in canonical order — the value used by dashboard Service filters
// and every mock Order.service field.
export const SERVICE_NAMES = SERVICE_CATALOG.map((s) => s.display_name);

export const SERVICE_IDS = SERVICE_CATALOG.map((s) => s.service_id);

// service_id -> display name (for rendering live backend orders that carry an id).
export const SERVICE_ID_TO_NAME: Record<string, string> = Object.fromEntries(
  SERVICE_CATALOG.map((s) => [s.service_id, s.display_name]),
);
