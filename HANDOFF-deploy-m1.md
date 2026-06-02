# Handoff — Deploy subsystem, milestone 1

Mục tiêu cuối cùng của tính năng deploy: `pyssg deploy <target>` push trực
tiếp site đã build lên một trong các nhà cung cấp hosting tĩnh (GitHub Pages,
Cloudflare Pages, Netlify). Triết lý đã chốt: **push-from-local** (không
sinh CI yaml). Tất cả cấu hình đi qua `pyssg.config.py`, output friendly.

Tài liệu này tóm tắt những gì đã có sau M1, các quyết định thiết kế đã chốt,
và mô tả các milestone còn lại để người tiếp theo có thể vào việc ngay mà
không cần đọc lại lịch sử thảo luận.

## Quyết định đã chốt (không đổi nếu không thảo luận lại)

1. **Push-from-local**, không sinh CI yaml.
2. **Targets MVP**: `github-pages`, `cloudflare`, `netlify` (theo thứ tự).
3. **HTTP**: dùng `httpx` async, đi qua optional extras `pyssg[deploy]`.
   GitHub Pages dùng `git` subprocess, không cần extras.
4. **Async upload** với semaphore concurrency cap (mặc định 10).
5. **Không auto-load `.env`** — user tự `export` env var.
6. **CLI naming**: dùng dấu gạch ngang (`github-pages`), khớp tên registry.
7. **Cấu hình**: toàn bộ trong `pyssg.config.py` qua field `Config.deploy`.
   Secrets KHÔNG nằm trong file này; chỉ đọc qua env var.
8. **State persistence**: `.pyssg-cache/deploy/<target>.json`
   (cùng cache với build; `pyssg clean` xóa luôn).
9. **Validate config**: **không** validate khi `load_config()` — chỉ validate
   khi user gõ `pyssg deploy <target>` (option (b) khi thảo luận).
10. **Atomicity**: cả 3 provider đều atomic phía họ → pipeline không tự
    triển khai atomicity, chỉ fail-cleanly và in error chi tiết.

## Kiến trúc thực tế đang có (sau M1)

```
pyssg/deploy/
  base.py              DeployTarget Protocol, DeployContext, DeployResult, DeployError
  __init__.py          Registry: TARGETS, register(), get_target(), list_targets()
  _hash.py             hash_tree() sha256 tree-stable; file_count_and_size()
  _output.py           Console: step/detail/ok/skip/error/summary (==> prefix)
  state.py             DeployRecord + read_record/write_record
  pipeline.py          run_deploy() orchestrator (sync, gọi async target.deploy)

pyssg/cli/deploy.py    argparse subcommand: list, status, <target>
pyssg/cli/__init__.py  Wired (deploy_cli.add_subparser + dispatcher)

pyssg/config/__init__.py  Config.deploy: dict[str, dict[str, object]] mới
pyssg/presets/docs.py     +tham số deploy=...
pyssg/presets/blog.py     +tham số deploy=...

tests/unit/test_deploy_hash.py        determinism, rename, order independence
tests/unit/test_deploy_state.py       round-trip, corrupt, multi-target
tests/unit/test_deploy_registry.py    unknown, double-register, sorted
tests/unit/test_deploy_output.py      step/detail/error/summary
tests/unit/test_deploy_pipeline.py    happy, skip, force, dry-run, missing env/key, empty
tests/integration/test_deploy_cli.py  CLI dispatch + list + status
```

Không file nào trong `pyssg/core/` bị đụng đến. Deploy là periphery thuần.

## Pipeline flow (tham chiếu nhanh khi đọc code)

`run_deploy(site_dir, target_name, *, dry_run, force, skip_build, skip_check, targets=None, console=None)`:

1. `load_config(site_dir)` → lấy `config.deploy[target_name]`. Thiếu → DeployError.
2. `get_target(target_name, targets=registry)`. Thiếu → DeployError có liệt kê available.
3. Validate `required_env()` và `required_config_keys()`. Thiếu → DeployError.
4. Build full (`no_cache=True`) trừ khi `skip_build`. Nếu `skip_build` mà
   `out_dir` không tồn tại → DeployError.
5. Sanity check: `file_count >= 1` trừ khi `skip_check`.
6. `hash_tree(out_dir)` → so với `read_record(...).hash`. Trùng và không
   `force` → trả về `DeployResult(skipped=True)`, không gọi target.
7. Nếu `dry_run` → in "would upload N files", trả về `DeployResult(deployment_id="dry-run")`,
   không persist record.
8. `asyncio.run(target.deploy(ctx))`.
9. `write_record(...)` với hash + deployment_id + url + timestamp ISO-8601 UTC.
10. `console.summary(result)`.

Lưu ý: pipeline sync, chỉ `target.deploy` async — vì targets thật (CF/Netlify)
cần parallel uploads. Pipeline owns clock access; targets phải pure trừ
network calls.

## Contract của `DeployTarget` (cho người implement target mới)

```python
class DeployTarget(Protocol):
    name: str                                                   # registry key + CLI name
    def required_env(self) -> list[str]: ...                    # env vars bắt buộc
    def required_config_keys(self) -> list[str]: ...            # config keys bắt buộc
    async def deploy(self, ctx: DeployContext) -> DeployResult: ...
```

Yêu cầu khi implement:
- Đọc `ctx.target_config` cho options của riêng target.
- Honor `ctx.dry_run` (không push, nhưng vẫn validate auth và compute counters).
- Mọi lỗi user-actionable raise `DeployError` (KHÔNG bare `Exception`).
- Phải ship test + mypy --strict 0 lỗi + pure (state qua pipeline, không
  global mutable state).
- Đăng ký bằng `register(MyTarget())` trong module của chính target.

## Schema config trong `pyssg.config.py`

```python
config = docs(
    site={"title": "My Docs"},
    base_url="https://example.com",
    deploy={
        "github-pages": {
            "repo": "user/my-docs",         # bắt buộc (hoặc auto-detect ở M2)
            "branch": "gh-pages",           # optional, default gh-pages
            "cname": "docs.example.com",    # optional
            "commit_message": "Deploy {sha}",  # optional, template
        },
        "cloudflare": {
            "account_id": "abc123...",      # bắt buộc
            "project": "my-docs",           # bắt buộc
            "branch": "main",               # optional
            "concurrency": 10,              # optional, upload parallelism
        },
        "netlify": {
            "site_id": "xyz-789",           # bắt buộc
            "production": True,             # optional, False = preview deploy
        },
    },
)
```

Schema cụ thể của mỗi target chốt khi implement target đó (M2/M3/M4).

## Roadmap còn lại

### M2: github-pages target

- Module: `pyssg/deploy/github_pages.py`
- Backend: `git` subprocess (`git`, `git remote`, `git push --force`).
  Không cần `pyssg[deploy]`.
- Required env: `[]` (dùng git stored credentials hoặc SSH key của user).
  Có thể đọc `GITHUB_TOKEN` nếu có để dùng HTTPS auth — optional.
- Required config keys: `["repo"]`. Optional: `branch`, `cname`, `commit_message`.
- Flow:
  1. Tạo tmp worktree, clone shallow branch đích (hoặc init nếu chưa tồn tại).
  2. Clear worktree, rsync `out_dir/*` vào, viết `.nojekyll` và `CNAME` nếu có.
  3. `git add -A && git commit -m "<message>"` (deterministic author/email
     phải set qua env hoặc options để byte-identical build → byte-identical
     commit nội dung, nhưng SHA sẽ khác vì timestamp; ổn).
  4. `git push --force` lên branch đích.
  5. Trả về `DeployResult(deployment_id=<sha>, url=https://<user>.github.io/<repo>/, ...)`.
- Tests: tmp bare repo (`git init --bare`) local làm remote.

### M3: optional dep `pyssg[deploy]` + `_http.py` + cloudflare

- Cập nhật `pyproject.toml`:
  ```toml
  [project.optional-dependencies]
  deploy = ["httpx>=0.27"]
  ```
- Module mới `pyssg/deploy/_http.py`: lazy import `httpx`, AsyncClient wrapper
  với retry exponential backoff (cho 429/5xx), semaphore concurrency cap.
  Khi import `httpx` fail → DeployError với hint cài `pyssg[deploy]`.
- Module: `pyssg/deploy/cloudflare.py`
- API: Cloudflare Pages Direct Upload
  (`https://api.cloudflare.com/client/v4/accounts/{account_id}/pages/projects/{project}/deployments`).
  Flow: tạo deployment → upload manifest (sha1 list) → upload missing files
  song song → finalize.
- Required env: `["CLOUDFLARE_API_TOKEN"]`. Scope: `Cloudflare Pages:Edit`.
- Required config keys: `["account_id", "project"]`. Optional: `branch`, `concurrency`.
- Tests: mock httpx transport (httpx hỗ trợ `MockTransport`).

### M4: netlify target

- Module: `pyssg/deploy/netlify.py`
- API: Netlify Deploy API (`POST https://api.netlify.com/api/v1/sites/{site_id}/deploys`)
  — digest-based (gửi sha1 file list, upload thiếu).
- Required env: `["NETLIFY_AUTH_TOKEN"]`.
- Required config keys: `["site_id"]`. Optional: `production` (bool, default True).
- Reuse `_http.py` từ M3.

### M5: docs + polish

- Tài liệu trang docs cho deploy subsystem.
- Cải tiến `deploy list` / `deploy status` (nếu cần).
- Cập nhật README + presets docstrings.

## Acceptance criteria mỗi milestone

Theo CLAUDE.md, mỗi milestone phải:
- Implement + test → check suite green → STOP, summarize, wait for approval.
- Code 100% English, no emoji.
- `mypy --strict pyssg` 0 errors.
- `ruff check .` và `ruff format --check .` đều pass.
- `python -m unittest discover -s tests -t .` xanh.

## Trạng thái check suite cho M1

Local trên máy maintainer cần chạy:
```bash
uv run mypy --strict pyssg
uv run ruff check .
uv run ruff format --check .
uv run python -m unittest discover -s tests -t .
```

Trong sandbox phát triển M1, đã verify được:
- `ruff check .`: clean (143/143 files)
- `ruff format --check .`: clean
- `ast.parse(feature_version=3.13)`: clean trên file mới
- `mypy --strict --python-version 3.13 --follow-imports=skip` trên file mới:
  clean (có 2 false positives do `--follow-imports=skip` không thấy class
  thật — không liên quan code)
- Không chạy được `mypy --strict pyssg` đầy đủ và `unittest` đầy đủ vì
  sandbox chỉ có Python 3.10, không tải được Python 3.13 từ github.com.

**Người tiếp theo: chạy 4 lệnh trên trên macOS với .venv hiện có để xác nhận
trước khi merge M1.**

## Câu hỏi mở (chốt khi vào M2/M3)

1. **Auto-detect `repo` cho github-pages từ git remote**? Tiện nhưng implicit;
   tôi đề xuất giữ tường minh trong config, log warning nếu lệch với `git remote`.
2. **Per-target `--profile`** (staging/production) trong cùng target? Cloudflare có
   "preview" vs "production" branch — đủ chưa, hay cần `--profile staging` riêng?
3. **`deploy logs <target>`** subcommand (hỏi provider về deployment history)?
   Có lợi nhưng tăng surface. Tôi nghiêng skip cho v1, mở khi user yêu cầu.
4. **`commit_message` template** cho github-pages: cho phép placeholder gì
   (`{sha}`, `{timestamp}`, `{site_title}`)?
5. **Hash skip cho từng provider**: pipeline đã skip nếu tree-hash trùng. CF/Netlify
   còn có per-file content-addressed upload (skip files server đã có). Hai cơ chế
   này độc lập; document rõ để user không nhầm.
