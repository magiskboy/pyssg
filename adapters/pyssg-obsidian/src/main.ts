import { FileSystemAdapter, Notice, Plugin, WorkspaceLeaf } from "obsidian";
import { build, outputDir, ServeProcess, type SiteContext } from "./pyssg";
import { Runtime } from "./runtime";
import { DEFAULT_SETTINGS, PyssgSettingTab, type PyssgSettings } from "./settings";
import { PREVIEW_VIEW_TYPE, PyssgPreviewView } from "./view";

interface ElectronShell {
	openExternal?: (url: string) => void;
	openPath?: (path: string) => void;
}

function electronShell(): ElectronShell | null {
	const req = (window as unknown as { require?: (m: string) => unknown }).require;
	if (!req) return null;
	return (req("electron") as { shell?: ElectronShell }).shell ?? null;
}

/** Open an external URL in the system browser (Electron shell, else window.open). */
function openExternal(url: string): void {
	const shell = electronShell();
	if (shell?.openExternal) {
		shell.openExternal(url);
		return;
	}
	window.open(url, "_blank");
}

/** Reveal a local folder in the OS file manager, if running under Electron. */
function openFolder(path: string): void {
	electronShell()?.openPath?.(path);
}

export default class PyssgPlugin extends Plugin {
	settings: PyssgSettings = DEFAULT_SETTINGS;
	private runtime!: Runtime;
	private serve: ServeProcess | null = null;

	async onload(): Promise<void> {
		await this.loadSettings();
		this.runtime = new Runtime(this.settings);

		this.registerView(PREVIEW_VIEW_TYPE, (leaf) => new PyssgPreviewView(leaf, openExternal));

		this.addRibbonIcon("globe", "PySSG: preview site", () => {
			void this.previewSite();
		});

		this.addCommand({
			id: "pyssg-build",
			name: "Build site",
			callback: () => void this.buildSite(),
		});
		this.addCommand({
			id: "pyssg-preview",
			name: "Preview site (live)",
			callback: () => void this.previewSite(),
		});
		this.addCommand({
			id: "pyssg-open-browser",
			name: "Open preview in browser",
			callback: () => void this.openInBrowser(),
		});
		this.addCommand({
			id: "pyssg-stop-preview",
			name: "Stop preview server",
			callback: () => this.stopPreview(),
		});
		this.addCommand({
			id: "pyssg-open-output",
			name: "Open output folder",
			callback: () => this.openOutputFolder(),
		});

		this.addSettingTab(new PyssgSettingTab(this.app, this));
	}

	onunload(): void {
		this.stopPreview();
	}

	async loadSettings(): Promise<void> {
		this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
	}

	async saveSettings(): Promise<void> {
		await this.saveData(this.settings);
		// Settings shape the runtime resolution; rebuild the helper so the next
		// action picks up an edited executable path or git ref.
		this.runtime = new Runtime(this.settings);
	}

	async resetRuntime(): Promise<void> {
		this.stopPreview();
		await this.runtime.reset();
		new Notice("PySSG: managed runtime removed; it will rebuild on next use.");
	}

	/** Absolute path + name of the current vault, or null if not a local folder. */
	private siteContext(): SiteContext | null {
		const adapter = this.app.vault.adapter;
		if (adapter instanceof FileSystemAdapter) {
			return { vaultPath: adapter.getBasePath(), vaultName: this.app.vault.getName() };
		}
		return null;
	}

	private requireContext(): SiteContext | null {
		const ctx = this.siteContext();
		if (!ctx) {
			new Notice("PySSG: this vault is not stored on the local filesystem.");
		}
		return ctx;
	}

	private async buildSite(): Promise<void> {
		const ctx = this.requireContext();
		if (!ctx) return;
		try {
			const pyssg = await this.runtime.resolve();
			const result = await build(pyssg, this.settings, ctx);
			if (result.ok) {
				new Notice(`PySSG: built ${result.pages ?? 0} page(s) -> ${outputDir(ctx)}`);
			} else {
				new Notice(`PySSG build failed: ${result.error ?? "unknown error"}`);
			}
		} catch (err) {
			new Notice(`PySSG: ${describe(err)}`);
		}
	}

	private async previewSite(): Promise<void> {
		const ctx = this.requireContext();
		if (!ctx) return;
		try {
			const pyssg = await this.runtime.resolve();
			if (!this.serve) {
				this.serve = new ServeProcess(pyssg, this.settings, ctx, (pages) => {
					new Notice(`PySSG: rebuilt ${pages} page(s).`, 1500);
				});
			}
			const url = await this.serve.start();
			await this.revealPreview(url);
		} catch (err) {
			new Notice(`PySSG: ${describe(err)}`);
		}
	}

	private async openInBrowser(): Promise<void> {
		if (this.serve?.url) {
			openExternal(this.serve.url);
			return;
		}
		const ctx = this.requireContext();
		if (!ctx) return;
		try {
			const pyssg = await this.runtime.resolve();
			this.serve ??= new ServeProcess(pyssg, this.settings, ctx);
			const url = await this.serve.start();
			openExternal(url);
		} catch (err) {
			new Notice(`PySSG: ${describe(err)}`);
		}
	}

	private stopPreview(): void {
		this.serve?.stop();
		this.serve = null;
		this.app.workspace.detachLeavesOfType(PREVIEW_VIEW_TYPE);
	}

	private openOutputFolder(): void {
		const ctx = this.requireContext();
		if (!ctx) return;
		openFolder(outputDir(ctx));
	}

	/** Open (or focus) the preview pane and point it at `url`. */
	private async revealPreview(url: string): Promise<void> {
		const existing = this.app.workspace.getLeavesOfType(PREVIEW_VIEW_TYPE);
		let leaf: WorkspaceLeaf | null = existing[0] ?? null;
		if (leaf) {
			const view = leaf.view;
			if (view instanceof PyssgPreviewView) {
				view.setUrl(url);
			}
		} else {
			leaf = this.app.workspace.getLeaf("split", "vertical");
			await leaf.setViewState({ type: PREVIEW_VIEW_TYPE, active: true });
			const view = leaf.view;
			if (view instanceof PyssgPreviewView) {
				view.setUrl(url);
			}
		}
		if (leaf) {
			this.app.workspace.revealLeaf(leaf);
		}
	}
}

function describe(err: unknown): string {
	return err instanceof Error ? err.message : String(err);
}
