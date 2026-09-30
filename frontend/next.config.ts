import type { NextConfig } from "next";

import { BASE_PATH } from "./lib/basePath";

// Static export, served by FastAPI. Mounted at /app until the voice loop is
// verified and approved to replace the old static/ UI at "/".
const nextConfig: NextConfig = {
  output: "export",
  basePath: BASE_PATH,
  images: { unoptimized: true },
};

export default nextConfig;
