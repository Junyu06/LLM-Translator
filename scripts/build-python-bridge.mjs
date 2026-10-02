import { existsSync, mkdirSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import process from "node:process";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const root = join(scriptDir, "..");
const isWindows = process.platform === "win32";
const specPath = join(root, isWindows ? "Translator_bridge_windows.spec" : "Translator_bridge_macos.spec");
const binariesDir = join(root, "src-tauri", "binaries");
const workPath = join(root, "build", "pyinstaller-bridge");
const bridgeDir = join(binariesDir, "translator-bridge");
const bridgeExe = join(bridgeDir, isWindows ? "translator-bridge.exe" : "translator-bridge");
const legacyBridgeExe = join(binariesDir, "translator-bridge.exe");

function pyinstallerCandidates() {
  if (process.platform === "win32") {
    return [
      join(root, "venv", "Scripts", "pyinstaller.exe"),
      join(root, ".venv", "Scripts", "pyinstaller.exe"),
      "pyinstaller"
    ];
  }

  return [
    join(root, "venv", "bin", "pyinstaller"),
    join(root, ".venv", "bin", "pyinstaller"),
    "pyinstaller"
  ];
}

function isPath(candidate) {
  return candidate.includes("/") || candidate.includes("\\");
}

function canRun(candidate) {
  if (isPath(candidate) && !existsSync(candidate)) {
    return false;
  }
  const result = spawnSync(candidate, ["--version"], { stdio: "ignore" });
  return result.status === 0;
}

const pyinstaller = pyinstallerCandidates().find(canRun);
if (!pyinstaller) {
  console.error("Unable to find PyInstaller. Expected venv/.venv PyInstaller or pyinstaller in PATH.");
  process.exit(1);
}

mkdirSync(binariesDir, { recursive: true });
mkdirSync(workPath, { recursive: true });
rmSync(bridgeDir, { recursive: true, force: true });
rmSync(legacyBridgeExe, { force: true });

const result = spawnSync(
  pyinstaller,
  [
    "--noconfirm",
    "--clean",
    "--distpath",
    binariesDir,
    "--workpath",
    workPath,
    specPath
  ],
  {
    cwd: root,
    stdio: "inherit"
  }
);

if (result.status !== 0) {
  process.exit(result.status ?? 1);
}

if (!existsSync(bridgeExe)) {
  console.error(`PyInstaller completed but did not create ${bridgeExe}`);
  process.exit(1);
}

console.log(`Built Python bridge sidecar: ${bridgeExe}`);
