import { readFileSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { LineProcess, run } from "./process";
import { parseGlobList, type PyssgSettings } from "./settings";
import { runtimeRoot } from "./runtime";

/** Parsed `--json` summary from `pyssg build`. */
export interface BuildResult {
	ok: boolean;
	pages?: number;
	error?: string;
}

/** Inputs needed to build a site config for a vault. */
export interface SiteContext {
	vaultPath: string;
	vaultName: string;
}

/**
 * Per-vault working directory (outside the vault). Holds the generated
 * `pyssg.config.py` and the build output, so the vault itself stays pristine.
 */
export function workDir(ctx: SiteContext): string {
	let hash = 0;
	for (const ch of ctx.vaultPath) {
		hash = (hash * 31 + ch.charCodeAt(0)) | 0;
	}
	const slug = ctx.vaultName.replace(/[^A-Za-z0-9_-]+/g, "-").slice(0, 40);
	return join(runtimeRoot(), "sites", `${slug}-${(hash >>> 0).toString(16)}`);
}

export function outputDir(ctx: SiteContext): string {
	return join(workDir(ctx), "site");
}

function readJson(path: string): Record<string, unknown> | null {
	try {
		const parsed: unknown = JSON.parse(readFileSync(path, "utf8"));
		return typeof parsed === "object" && parsed !== null
			? (parsed as Record<string, unknown>)
			: null;
	} catch {
		return null;
	}
}

/**
 * Folders to exclude that pyssg cannot know about, discovered from the vault's
 * own Obsidian configuration: the core Templates and Daily-notes folders, plus
 * the Templater community plugin's folder. These hold template notes (often with
 * `{{date}}`-style placeholders), not publishable content. The `.obsidian`,
 * `.trash` and `.git` folders are excluded by the preset itself, so they are not
 * repeated here. Returned as vault-relative folder paths suitable as exclude
 * globs (matching a folder prunes its whole subtree).
 */
export function discoverVaultExcludes(vaultPath: string): string[] {
	const out = new Set<string>();
	const add = (folder: unknown): void => {
		if (typeof folder === "string") {
			const clean = folder.trim().replace(/^\/+|\/+$/g, "");
			if (clean) out.add(clean);
		}
	};
	const ob = join(vaultPath, ".obsidian");
	add(readJson(join(ob, "templates.json"))?.folder);
	add(readJson(join(ob, "daily-notes.json"))?.folder);
	add(readJson(join(ob, "plugins", "templater-obsidian", "data.json"))?.templates_folder);
	return [...out];
}

/**
 * Render a `pyssg.config.py` for the vault. The vault path is passed as an
 * absolute `content_dir` and the output is written outside the vault, so the
 * build never re-ingests its own output and no config file lands in the vault.
 * Excludes combine the user's setting with folders discovered from the vault's
 * Obsidian configuration (unless a content subfolder is in use, where the user
 * manages excludes explicitly).
 */
export function generateConfigPy(settings: PyssgSettings, ctx: SiteContext): string {
	const contentPath = settings.contentSubdir
		? join(ctx.vaultPath, settings.contentSubdir)
		: ctx.vaultPath;
	const include = parseGlobList(settings.include);
	const discovered = settings.contentSubdir ? [] : discoverVaultExcludes(ctx.vaultPath);
	const exclude = [...new Set([...parseGlobList(settings.exclude), ...discovered])];
	const lines = [
		"from __future__ import annotations",
		"",
		"from pyssg.presets import obsidian",
		"",
		"config = obsidian(",
		`    site=${JSON.stringify({ title: ctx.vaultName })},`,
		`    base_url=${JSON.stringify(settings.baseUrl)},`,
		`    content_dir=${JSON.stringify(contentPath)},`,
		`    output_dir=${JSON.stringify(outputDir(ctx))},`,
		`    publish_required=${settings.publishRequired ? "True" : "False"},`,
	];
	if (include.length > 0) {
		lines.push(`    include=${JSON.stringify(include)},`);
	}
	if (exclude.length > 0) {
		lines.push(`    exclude=${JSON.stringify(exclude)},`);
	}
	lines.push(")", "");
	return lines.join("\n");
}

/** Write the generated config into the per-vault work dir and return its path. */
export async function writeConfig(settings: PyssgSettings, ctx: SiteContext): Promise<string> {
	const dir = workDir(ctx);
	await mkdir(dir, { recursive: true });
	await writeFile(join(dir, "pyssg.config.py"), generateConfigPy(settings, ctx), "utf8");
	return dir;
}

/** Run a one-shot build and return the parsed JSON summary. */
export async function build(
	pyssgPath: string,
	settings: PyssgSettings,
	ctx: SiteContext,
): Promise<BuildResult> {
	const dir = await writeConfig(settings, ctx);
	const result = await run(pyssgPath, ["--site", dir, "build", "--json"]);
	const line = lastJsonLine(result.stdout);
	if (line) {
		return JSON.parse(line) as BuildResult;
	}
	return { ok: false, error: result.stderr.trim() || `build exited ${result.code}` };
}

function lastJsonLine(text: string): string | null {
	const lines = text
		.split("\n")
		.map((l) => l.trim())
		.filter((l) => l.startsWith("{"));
	return lines.length > 0 ? lines[lines.length - 1]! : null;
}

/**
 * Manages the lifecycle of a `pyssg serve --json` process. Resolves `start()`
 * once the server emits its `ready` event (carrying the served URL).
 */
export class ServeProcess {
	private proc: LineProcess | null = null;
	private servedUrl: string | null = null;

	constructor(
		private readonly pyssgPath: string,
		private readonly settings: PyssgSettings,
		private readonly ctx: SiteContext,
		private readonly onRebuild?: (pages: number) => void,
	) {}

	get url(): string | null {
		return this.servedUrl;
	}

	get running(): boolean {
		return this.proc?.running ?? false;
	}

	async start(): Promise<string> {
		if (this.servedUrl && this.running) {
			return this.servedUrl;
		}
		const dir = await writeConfig(this.settings, this.ctx);
		return new Promise<string>((resolve, reject) => {
			let settled = false;
			const errLines: string[] = [];
			const fail = (message: string) => {
				if (settled) return;
				settled = true;
				const detail = errLines.join("\n").trim();
				reject(new Error(detail ? `${message}: ${detail}` : message));
			};
			const proc = new LineProcess(
				this.pyssgPath,
				[
					"--site",
					dir,
					"serve",
					"--json",
					"--host",
					this.settings.host,
					"--port",
					String(this.settings.port),
				],
				{
					onStdoutLine: (line) => {
						const event = parseEvent(line);
						if (!event) return;
						if (event.event === "ready" && typeof event.url === "string") {
							this.servedUrl = event.url;
							if (!settled) {
								settled = true;
								resolve(event.url);
							}
						} else if (event.event === "rebuild" && typeof event.pages === "number") {
							this.onRebuild?.(event.pages);
						}
					},
					onStderrLine: (line) => {
						// Keep the tail so a crash report stays bounded but useful.
						errLines.push(line);
						if (errLines.length > 20) errLines.shift();
					},
					onError: (err) => fail(`could not start pyssg (${this.pyssgPath})`),
					onClose: (code) => fail(`pyssg serve exited (code ${code ?? "?"})`),
				},
			);
			proc.start();
			this.proc = proc;
			// Fallback if the server starts but never reports ready.
			window.setTimeout(() => fail("preview server did not report ready in time"), 30000);
		});
	}

	stop(): void {
		this.proc?.stop();
		this.proc = null;
		this.servedUrl = null;
	}
}

interface ServeEvent {
	event?: string;
	url?: string;
	pages?: number;
}

function parseEvent(line: string): ServeEvent | null {
	const trimmed = line.trim();
	if (!trimmed.startsWith("{")) return null;
	try {
		return JSON.parse(trimmed) as ServeEvent;
	} catch {
		return null;
	}
}
