const fs = require("fs");
const path = require("path");

for (const file of ["package-lock.json", "yarn.lock"]) {
  try {
    fs.unlinkSync(path.join(__dirname, "..", file));
  } catch {
    // ignore missing files
  }
}

const userAgent = process.env.npm_config_user_agent || "";
const execPath = process.env.npm_execpath || "";
const isPnpm =
  userAgent.includes("pnpm/") ||
  /pnpm(\.cjs|\.mjs)?$/i.test(execPath) ||
  execPath.replace(/\\/g, "/").includes("/pnpm");

if (!isPnpm && !fs.existsSync(path.join(__dirname, "..", "pnpm-lock.yaml"))) {
  console.error("Use pnpm instead of npm or yarn.");
  process.exit(1);
}
