import { spawn } from "node:child_process";

/** Result of a finished child process. */
export interface RunResult {
	code: number;
	stdout: string;
	stderr: string;
}

export interface RunOptions {
	cwd?: string;
	env?: NodeJS.ProcessEnv;
	/** Called for each complete stdout line as it arrives. */
	onStdoutLine?: (line: string) => void;
	/** Called for each complete stderr line as it arrives. */
	onStderrLine?: (line: string) => void;
	/** Called if the process cannot be spawned (e.g. executable not found). */
	onError?: (err: Error) => void;
	/** Called when the process exits, with its exit code. */
	onClose?: (code: number | null) => void;
}

/**
 * Spawn a command, stream its output line-by-line, and resolve once it exits.
 *
 * Rejects only if the process cannot be spawned at all; a non-zero exit resolves
 * normally with the captured code so callers can inspect `stderr`.
 */
export function run(cmd: string, args: string[], opts: RunOptions = {}): Promise<RunResult> {
	return new Promise((resolve, reject) => {
		const child = spawn(cmd, args, {
			cwd: opts.cwd,
			env: { ...process.env, ...opts.env },
		});
		let stdout = "";
		let stderr = "";
		let outBuf = "";
		let errBuf = "";

		const pump = (
			chunk: string,
			buf: string,
			onLine: ((line: string) => void) | undefined,
		): string => {
			let acc = buf + chunk;
			let nl = acc.indexOf("\n");
			while (nl >= 0) {
				const line = acc.slice(0, nl).replace(/\r$/, "");
				onLine?.(line);
				acc = acc.slice(nl + 1);
				nl = acc.indexOf("\n");
			}
			return acc;
		};

		child.stdout.setEncoding("utf8");
		child.stderr.setEncoding("utf8");
		child.stdout.on("data", (c: string) => {
			stdout += c;
			outBuf = pump(c, outBuf, opts.onStdoutLine);
		});
		child.stderr.on("data", (c: string) => {
			stderr += c;
			errBuf = pump(c, errBuf, opts.onStderrLine);
		});
		child.on("error", reject);
		child.on("close", (code) => {
			if (outBuf) opts.onStdoutLine?.(outBuf);
			if (errBuf) opts.onStderrLine?.(errBuf);
			resolve({ code: code ?? -1, stdout, stderr });
		});
	});
}

/** A long-lived child process whose stdout is consumed line-by-line. */
export class LineProcess {
	private child: ReturnType<typeof spawn> | null = null;

	constructor(
		private readonly cmd: string,
		private readonly args: string[],
		private readonly opts: RunOptions = {},
	) {}

	start(): void {
		const child = spawn(this.cmd, this.args, {
			cwd: this.opts.cwd,
			env: { ...process.env, ...this.opts.env },
		});
		let outBuf = "";
		let errBuf = "";
		child.stdout?.setEncoding("utf8");
		child.stderr?.setEncoding("utf8");
		child.stdout?.on("data", (c: string) => {
			outBuf += c;
			let nl = outBuf.indexOf("\n");
			while (nl >= 0) {
				this.opts.onStdoutLine?.(outBuf.slice(0, nl).replace(/\r$/, ""));
				outBuf = outBuf.slice(nl + 1);
				nl = outBuf.indexOf("\n");
			}
		});
		child.stderr?.on("data", (c: string) => {
			errBuf += c;
			let nl = errBuf.indexOf("\n");
			while (nl >= 0) {
				this.opts.onStderrLine?.(errBuf.slice(0, nl).replace(/\r$/, ""));
				errBuf = errBuf.slice(nl + 1);
				nl = errBuf.indexOf("\n");
			}
		});
		child.on("error", (err) => this.opts.onError?.(err));
		child.on("close", (code) => {
			if (errBuf) this.opts.onStderrLine?.(errBuf.replace(/\r$/, ""));
			this.opts.onClose?.(code);
		});
		this.child = child;
	}

	get running(): boolean {
		return this.child !== null && this.child.exitCode === null;
	}

	stop(): void {
		this.child?.kill();
		this.child = null;
	}
}
