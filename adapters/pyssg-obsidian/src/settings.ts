import { App, PluginSettingTab, Setting } from "obsidian";
import type PyssgPlugin from "./main";

/**
 * Persisted plugin configuration. All build-shaping fields map onto the
 * `pyssg.presets.obsidian(...)` factory; the rest control how the Python side is
 * provisioned and served.
 */
export interface PyssgSettings {
	/** Explicit path to a `pyssg` executable; empty means auto-provision via uv. */
	pyssgPath: string;
	/** Git ref of pyssg to install when auto-provisioning (pinned for reproducibility). */
	pyssgGitRef: string;
	/** Managed Python version uv installs for the runtime. */
	pythonVersion: string;
	/** Content directory, relative to the vault root. Empty means the whole vault. */
	contentSubdir: string;
	/** Site base URL written into the generated config. */
	baseUrl: string;
	/** Allowlist mode: publish only notes whose frontmatter sets `publish: true`. */
	publishRequired: boolean;
	/** Extra exclude globs (comma-separated), added to the vault-noise defaults. */
	exclude: string;
	/** Include globs (comma-separated); empty means load every supported file. */
	include: string;
	/** Dev-server bind host. */
	host: string;
	/** Dev-server port. */
	port: number;
}

export const DEFAULT_SETTINGS: PyssgSettings = {
	pyssgPath: "",
	pyssgGitRef: "main",
	pythonVersion: "3.13",
	contentSubdir: "",
	baseUrl: "",
	publishRequired: false,
	exclude: "",
	include: "",
	host: "127.0.0.1",
	port: 8000,
};

/** Parse a comma-separated glob list into a trimmed, non-empty array. */
export function parseGlobList(raw: string): string[] {
	return raw
		.split(",")
		.map((s) => s.trim())
		.filter((s) => s.length > 0);
}

export class PyssgSettingTab extends PluginSettingTab {
	private readonly plugin: PyssgPlugin;

	constructor(app: App, plugin: PyssgPlugin) {
		super(app, plugin);
		this.plugin = plugin;
	}

	display(): void {
		const { containerEl } = this;
		containerEl.empty();

		containerEl.createEl("h3", { text: "Site" });

		new Setting(containerEl)
			.setName("Publish marked notes only")
			.setDesc(
				"Allowlist mode: a note is published only when its frontmatter sets " +
					"publish: true. Turn off to publish everything except notes marked " +
					"publish: false.",
			)
			.addToggle((t) =>
				t.setValue(this.plugin.settings.publishRequired).onChange(async (v) => {
					this.plugin.settings.publishRequired = v;
					await this.plugin.saveSettings();
				}),
			);

		new Setting(containerEl)
			.setName("Base URL")
			.setDesc("Absolute base URL of the published site (used for sitemaps/RSS).")
			.addText((t) =>
				t
					.setPlaceholder("https://example.com")
					.setValue(this.plugin.settings.baseUrl)
					.onChange(async (v) => {
						this.plugin.settings.baseUrl = v.trim();
						await this.plugin.saveSettings();
					}),
			);

		containerEl.createEl("h3", { text: "Advanced" });

		new Setting(containerEl)
			.setName("Content subfolder")
			.setDesc("Build only this subfolder of the vault. Empty = the whole vault.")
			.addText((t) =>
				t
					.setPlaceholder("(vault root)")
					.setValue(this.plugin.settings.contentSubdir)
					.onChange(async (v) => {
						this.plugin.settings.contentSubdir = v.trim();
						await this.plugin.saveSettings();
					}),
			);

		new Setting(containerEl)
			.setName("Exclude globs")
			.setDesc("Comma-separated globs to exclude (added to .obsidian/.trash defaults).")
			.addText((t) =>
				t
					.setPlaceholder("Templates/**, private/**")
					.setValue(this.plugin.settings.exclude)
					.onChange(async (v) => {
						this.plugin.settings.exclude = v;
						await this.plugin.saveSettings();
					}),
			);

		new Setting(containerEl)
			.setName("Include globs")
			.setDesc("Comma-separated globs to allowlist. Empty = every supported file.")
			.addText((t) =>
				t
					.setPlaceholder("**/*.md")
					.setValue(this.plugin.settings.include)
					.onChange(async (v) => {
						this.plugin.settings.include = v;
						await this.plugin.saveSettings();
					}),
			);

		new Setting(containerEl)
			.setName("Preview server")
			.setDesc("Host and port for the live-preview dev server.")
			.addText((t) =>
				t
					.setPlaceholder("127.0.0.1")
					.setValue(this.plugin.settings.host)
					.onChange(async (v) => {
						this.plugin.settings.host = v.trim() || "127.0.0.1";
						await this.plugin.saveSettings();
					}),
			)
			.addText((t) =>
				t
					.setPlaceholder("8000")
					.setValue(String(this.plugin.settings.port))
					.onChange(async (v) => {
						const n = Number.parseInt(v, 10);
						this.plugin.settings.port = Number.isFinite(n) ? n : 8000;
						await this.plugin.saveSettings();
					}),
			);

		containerEl.createEl("h3", { text: "Python runtime" });

		new Setting(containerEl)
			.setName("pyssg executable")
			.setDesc(
				"Path to an existing pyssg executable. Leave empty to download and " +
					"manage an isolated Python runtime automatically (via uv).",
			)
			.addText((t) =>
				t
					.setPlaceholder("(auto via uv)")
					.setValue(this.plugin.settings.pyssgPath)
					.onChange(async (v) => {
						this.plugin.settings.pyssgPath = v.trim();
						await this.plugin.saveSettings();
					}),
			);

		new Setting(containerEl)
			.setName("pyssg version (git ref)")
			.setDesc("Branch, tag or commit of pyssg to install when auto-provisioning.")
			.addText((t) =>
				t
					.setValue(this.plugin.settings.pyssgGitRef)
					.onChange(async (v) => {
						this.plugin.settings.pyssgGitRef = v.trim() || "main";
						await this.plugin.saveSettings();
					}),
			);

		new Setting(containerEl)
			.setName("Reset managed runtime")
			.setDesc("Delete the auto-provisioned runtime so it is rebuilt on next use.")
			.addButton((b) =>
				b.setButtonText("Reset").setWarning().onClick(async () => {
					await this.plugin.resetRuntime();
				}),
			);
	}
}
