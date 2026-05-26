export type PanelId =
  | "search"
  | "timeline"
  | "health"
  | "dcs"
  | "topology"
  | "wal"
  | "incidents"
  | "notes";

/** Panels in the fixed dashboard grid (search is above the grid). */
export const GRID_PANELS: PanelId[] = [
  "topology",
  "health",
  "dcs",
  "timeline",
  "wal",
  "incidents",
  "notes",
];
