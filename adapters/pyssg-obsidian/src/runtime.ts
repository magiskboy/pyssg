import { existsSync } from "node:fs";
import { mkdir, rm } from "node:fs/promises";
import { homedir, platform } from "node:os";
import { join } from "node:path";
import { Notice } from "obsidian";
import { run } from "./process";
import type { PyssgSettings } from "./settings";

const PYSSG_REPO = "https://github.com/magiskboy/pyssg";

/** Whether we are on Windows (affects executable names and the uv installer). */
const isWindows = platform() === "win32";

/**
 * OS-appropriate shared data directory for the managed runtime. Kept outside any
 * vault so a single Python install is reused across vaults and never indexed by
 * Obsidian.
 */
export function runtimeRoot(): string {
	if (isWindows) {
		return join(process.env.APPDATA ?? join(homedir(), "AppData", "Roaming"), "pyssg-obsidian");
	}
	if (platform() === "darwin") {
		return join(homedir(), "Library", "Application Support", "pyssg-obsidian");
	}
	return join(process.env.XDG_DATA_HOME ?? join(homedir(), ".local", "share"), "pyssg-obsidian");
}

function uvBinPath(root: string): string {
	return join(root, "uv", isWindows ? "uv.exe" : "uv");
}

function venvPyssgPath(root: string): string {
	const venv = join(root, "venv");
	return isWindows
		? join(venv, "Scripts", "pyssg.exe")
		: join(venv, "bin", "pyssg");
}

/**
 * Provisions and locates a usable `pyssg` executable.
 *
 * Resolution order: an explicit path from settings, then a previously managed
 * runtime, then a fresh uv-managed install (download uv, install a managed
 * Python, create an isolated venv with pyssg from the pinned git ref). The first
 * provisioning shows progress; subsequent calls return the cached path instantly.
 */
export class Runtime {
	constructor(private readonly settings: PyssgSettings) {}

	/** Delete the managed runtime so the next `resolve()` rebuilds it. */
	async reset(): Promise<void> {
		await rm(runtimeRoot(), { recursive: true, force: true });
	}

	async resolve(): Promise<string> {
		if (this.settings.pyssgPath) {
			if (!existsSync(this.settings.pyssgPath)) {
				throw new Error(`configured pyssg executable not found: ${this.settings.pyssgPath}`);
			}
			return this.settings.pyssgPath;
		}
		const root = runtimeRoot();
		const pyssg = venvPyssgPath(root);
		if (existsSync(pyssg)) {
			return pyssg;
		}
		return this.provision(root);
	}

	private async provision(root: string): Promise<string> {
		const notice = new Notice("PySSG: preparing Python runtime (one-time setup)...", 0);
		try {
			await mkdir(root, { recursive: true });
			const uv = await this.ensureUv(root, notice);

			notice.setMessage("PySSG: installing Python " + this.settings.pythonVersion + "...");
			await this.runChecked(uv, ["python", "install", this.settings.pythonVersion], root);

			const venv = join(root, "venv");
			notice.setMessage("PySSG: creating isolated environment...");
			await this.runChecked(uv, ["venv", venv, "--python", this.settings.pythonVersion], root);

			notice.setMessage("PySSG: installing pyssg...");
			const spec = `git+${PYSSG_REPO}@${this.settings.pyssgGitRef}`;
			const python = isWindows
				? join(venv, "Scripts", "python.exe")
				: join(venv, "bin", "python");
			await this.runChecked(uv, ["pip", "install", "--python", python, spec], root);

			const pyssg = venvPyssgPath(root);
			if (!existsSync(pyssg)) {
				throw new Error("pyssg was installed but its executable was not found");
			}
			notice.setMessage("PySSG: runtime ready.");
			window.setTimeout(() => notice.hide(), 2000);
			return pyssg;
		} catch (err) {
			notice.hide();
			throw err;
		}
	}

	/** Ensure a uv binary exists under the runtime root; install it if missing. */
	private async ensureUv(root: string, notice: Notice): Promise<string> {
		const uv = uvBinPath(root);
		if (existsSync(uv)) {
			return uv;
		}
		notice.setMessage("PySSG: downloading uv...");
		const installDir = join(root, "uv");
		await mkdir(installDir, { recursive: true });
		// uv's official installer; UV_UNMANAGED_INSTALL drops the binary into our
		// directory without modifying PATH or shell profiles.
		const env = { UV_UNMANAGED_INSTALL: installDir };
		if (isWindows) {
			await this.runChecked(
				"powershell",
				[
					"-NoProfile",
					"-Command",
					"irm https://astral.sh/uv/install.ps1 | iex",
				],
				root,
				env,
			);
		} else {
			await this.runChecked(
				"sh",
				["-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"],
				root,
				env,
			);
		}
		if (!existsSync(uv)) {
			throw new Error("uv installation completed but the binary was not found");
		}
		return uv;
	}

	private async runChecked(
		cmd: string,
		args: string[],
		cwd: string,
		env?: NodeJS.ProcessEnv,
	): Promise<void> {
		const result = await run(cmd, args, { cwd, env });
		if (result.code !== 0) {
			const detail = result.stderr.trim() || result.stdout.trim();
			throw new Error(`${cmd} ${args.join(" ")} failed (exit ${result.code}): ${detail}`);
		}
	}
}
