import { existsSync } from "node:fs";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import process from "node:process";

function hasCommand(command, args = ["--version"]) {
  const result = spawnSync(command, args, { stdio: "ignore" });
  return result.status === 0;
}

function pythonCandidates() {
  const root = process.cwd();

  if (process.platform === "win32") {
    return [
      join(root, ".venv", "Scripts", "python.exe"),
      join(root, "venv", "Scripts", "python.exe"),
      "python3",
      "python"
    ];
  }

  return [
    join(root, ".venv", "bin", "python"),
    join(root, "venv", "bin", "python"),
    "python3",
    "python"
  ];
}

function resolvePython() {
  for (const candidate of pythonCandidates()) {
    const isPath = candidate.includes("/") || candidate.includes("\\");
    if (isPath && !existsSync(candidate)) {
      continue;
    }
    if (hasCommand(candidate)) {
      return candidate;
    }
  }
  return null;
}

const missing = [];

if (!hasCommand("cargo")) {
  missing.push("cargo");
}

if (!hasCommand("rustc")) {
  missing.push("rustc");
}

const python = resolvePython();

if (!python) {
  missing.push("python (.venv/bin/python, venv/bin/python, python3, or python)");
}

if (missing.length > 0) {
  console.error("Tauri preflight failed.");
  console.error(`Missing required tools: ${missing.join(", ")}`);
  console.error(
    "Install Rust via https://rustup.rs and ensure a project virtualenv or a Python interpreter is available."
  );
  process.exit(1);
}

console.log(`Using Python interpreter: ${python}`);
console.log("Tauri preflight passed.");
