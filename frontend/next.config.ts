import type { NextConfig } from "next";

import { BASE_PATH } from "./lib/basePath";

// Static export, served by FastAPI at "/". The old static/ UI now lives at
// /classic for rollback safety.
const nextConfig: NextConfig = {
  output: "export",
  // FastAPI's StaticFiles(html=True) only maps a directory to its
  // index.html, not "route.html" to "/route" - trailingSlash makes every
  // route export as its own directory with an index.html, so /replay works
  // the same way / does.
  trailingSlash: true,
  ...(BASE_PATH ? { basePath: BASE_PATH } : {}),
  images: { unoptimized: true },
};

export default nextConfig;
