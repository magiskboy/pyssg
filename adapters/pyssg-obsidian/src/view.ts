import { ItemView, WorkspaceLeaf } from "obsidian";

export const PREVIEW_VIEW_TYPE = "pyssg-preview";

/**
 * Minimal subset of Electron's `<webview>` API we drive. Unlike an `<iframe>`,
 * a webview hosts its own web contents, so navigation (back/forward/reload)
 * works across origins -- which an iframe cannot do from the Obsidian side.
 */
interface WebviewElement extends HTMLElement {
	src: string;
	goBack(): void;
	goForward(): void;
	reload(): void;
	getURL(): string;
}

/**
 * A workspace pane that embeds the live-preview dev server, with its own
 * back / forward / reload / home controls in the view header. The server's
 * injected live-reload script refreshes the view whenever a rebuild changes the
 * open page.
 *
 * Note: the back/forward arrows in Obsidian's own pane chrome navigate Obsidian's
 * view history, not the embedded site -- use the toolbar buttons this view adds.
 */
export class PyssgPreviewView extends ItemView {
	private url: string;
	private webview: WebviewElement | null = null;
	private readonly onOpenExternal: (url: string) => void;

	constructor(leaf: WorkspaceLeaf, onOpenExternal: (url: string) => void) {
		super(leaf);
		this.url = "about:blank";
		this.onOpenExternal = onOpenExternal;
	}

	getViewType(): string {
		return PREVIEW_VIEW_TYPE;
	}

	getDisplayText(): string {
		return "PySSG preview";
	}

	getIcon(): string {
		return "globe";
	}

	async onOpen(): Promise<void> {
		this.addAction("arrow-left", "Back", () => this.webview?.goBack());
		this.addAction("arrow-right", "Forward", () => this.webview?.goForward());
		this.addAction("rotate-ccw", "Reload", () => this.webview?.reload());
		this.addAction("home", "Home", () => this.navigate(this.url));
		this.addAction("external-link", "Open in browser", () =>
			this.onOpenExternal(this.currentUrl()),
		);
		this.render();
	}

	/** Point the pane at a (possibly new) server URL and load it. */
	setUrl(url: string): void {
		this.url = url;
		this.navigate(url);
	}

	private navigate(url: string): void {
		if (this.webview) {
			this.webview.src = url;
		} else {
			this.render();
		}
	}

	/** The URL currently shown (after in-page navigation), falling back to home. */
	private currentUrl(): string {
		try {
			return this.webview?.getURL() || this.url;
		} catch {
			return this.url;
		}
	}

	private render(): void {
		const container = this.contentEl;
		container.empty();
		container.addClass("pyssg-preview-container");
		// `createElement("webview")` rather than `createEl`: the tag is an Electron
		// extension and not in the standard HTML element map.
		const webview = document.createElement("webview") as unknown as WebviewElement;
		webview.addClass("pyssg-preview-frame");
		webview.setAttribute("src", this.url);
		container.appendChild(webview);
		this.webview = webview;
	}

	async onClose(): Promise<void> {
		this.webview = null;
		this.contentEl.empty();
	}
}
