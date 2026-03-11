import { spawnSync } from "node:child_process";
import process from "node:process";

function hasCommand(command, args = ["--version"]) {
  const result = spawnSync(command, args, { stdio: "ignore" });
  return result.status === 0;
}

const missing = [];

if (!hasCommand("cargo")) {
  missing.push("cargo");
}

if (!hasCommand("rustc")) {
  missing.push("rustc");
}

if (!hasCommand("python3")) {
  missing.push("python3");
}

if (missing.length > 0) {
  console.error("Tauri preflight failed.");
  console.error(`Missing required tools: ${missing.join(", ")}`);
  console.error("Install Rust via https://rustup.rs and ensure python3 is available in PATH.");
  process.exit(1);
}

console.log("Tauri preflight passed.");
