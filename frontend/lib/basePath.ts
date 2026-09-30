// Next's own basePath is applied automatically to next/link and _next/*
// assets, but NOT to files in public/ - those need it prepended by hand.
// Shared with next.config.ts so the two can't drift apart.
//
// Served at "/" now (Phase 5). The old static/ UI moved to /classic. If
// this ever needs to move to a sub-path again, change this one constant
// and rebuild - next.config.ts reads it too.
export const BASE_PATH = "";
