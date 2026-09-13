"""Phase 10-H: clean-clone reproducibility check, as far as practical on one machine.

  python scripts/final/h_clean_env_check.py [--skip-frontend] [--keep] [--targeted] [--base-dir DIR]

--targeted re-checks the committable file set only. It uses the current interpreter and copies the existing .cache/embeddings instead
of creating a fresh virtual environment and re-embedding the knowledge base. Use it after a full run has proven the install path;
the report records the mode and what was reused. --base-dir places the copy under DIR instead of the system temp directory.

1. Copy exactly the files git would commit (tracked + untracked-not-ignored) into a new temporary directory outside the repository. The
   copy has no .env, no .cache (embeddings, model responses), no traces, no node_modules and no data/raw.
2. Create a fresh virtual environment there and install requirements-dev.txt (which includes requirements.txt). HF_HOME points inside
   the temporary directory, so the embedding model is downloaded again instead of reused. Model credentials and API tokens are removed
   from the child environment.
3. In the copy, with no model key:
   - `python -m pytest -q`;
   - `python -m resolveai demo --no-llm`;
   - `python scripts/final/f_final_verification.py` (golden hash, frozen artifacts, cached evaluation, security scan).
4. Frontend (unless --skip-frontend): `npm ci`, lint, typecheck, test, build.
5. Start the API from the copy, wait for /api/v1/ready, send one message, and stop it.
Writes artifacts/final/clean_env_check.json (commands, exit codes, durations, last output lines). The temporary directory is deleted
unless --keep.
Stated limits: same operating system and base Python interpreter; pip's and npm's download caches may be reused; network access required.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "final" / "clean_env_check.json"
SECRET_VARS = ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "GEMINI_API_KEY", "GEMINI_BASE_URL", "GROQ_API_KEY", "GROQ_BASE_URL", "OPENAI_API_KEY",
               "RESOLVEAI_API_TOKEN", "RESOLVEAI_READ_TOKEN")


def committable() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT, capture_output=True, check=True).stdout
    return sorted({p for p in out.decode("utf-8").split("\0") if p})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-frontend", action="store_true")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--targeted", action="store_true", help="reuse the current interpreter and embedding cache; re-check the file set only")
    ap.add_argument("--base-dir", default=None, help="directory in which to create the clean copy (default: system temp)")
    a = ap.parse_args()
    t0 = time.perf_counter()
    scratch = Path(tempfile.mkdtemp(prefix="resolveai_clean_", dir=a.base_dir))
    clone = scratch / "resolveai"
    files = committable()
    for rel in files:
        src = ROOT / rel
        if src.is_file():
            dst = clone / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    env = {k: v for k, v in os.environ.items() if k not in SECRET_VARS}
    env.update({"HF_HOME": str(scratch / "hf_home"), "PYTHONUNBUFFERED": "1", "PYTHONUTF8": "1"})
    if not a.targeted:
        env["PYTHONNOUSERSITE"] = "1"   # a fresh virtual environment must not see this machine's user site-packages
    report: dict = {"mode": "targeted re-check (current interpreter, existing embedding cache)" if a.targeted else "full (fresh virtual environment)",
                    "base_dir": str(scratch.parent), "copied_files": len(files), "env_file_present": (clone / ".env").exists(), "cache_dir_present": (clone / ".cache").exists(),
                    "hf_home_isolated": True, "model_credentials_in_env": False, "base_python": sys.version.split()[0], "os": platform.platform(), "steps": []}

    def step(name: str, cmd: list[str] | str, cwd: Path, timeout: int) -> bool:
        t = time.perf_counter()
        try:
            res = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, shell=isinstance(cmd, str))
            rc, text = res.returncode, (res.stdout or "") + (res.stderr or "")
        except subprocess.TimeoutExpired:
            rc, text = "timeout", ""
        tail = [line for line in text.strip().splitlines() if line.strip()][-6:]
        report["steps"].append({"step": name, "command": cmd if isinstance(cmd, str) else " ".join(Path(c).name if i == 0 else c for i, c in enumerate(cmd)),
                                "exit_code": rc, "seconds": round(time.perf_counter() - t, 1), "tail": tail})
        print(f"{'OK  ' if rc == 0 else 'FAIL'} {name} ({time.perf_counter() - t:.0f}s)", *tail[-2:], sep="\n    ", flush=True)
        return rc == 0

    step("git init (lets .gitignore classify local-only files)", ["git", "init", "-q"], clone, 120)
    if a.targeted:
        vpy = sys.executable
        shutil.copytree(ROOT / ".cache" / "embeddings", clone / ".cache" / "embeddings")
        report["reused"] = ["the current Python interpreter and its installed packages (no fresh virtual environment)",
                            ".cache/embeddings (derived knowledge-base vectors)"]
    else:
        step("create virtual environment", [sys.executable, "-m", "venv", ".venv"], clone, 600)
        vpy = str(clone / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
        step("pip install -r requirements-dev.txt", [vpy, "-m", "pip", "install", "-r", "requirements-dev.txt"], clone, 3600)
    step("pytest", [vpy, "-m", "pytest", "-q", "-p", "no:cacheprovider"], clone, 5400)
    step("demo without a model key", [vpy, "-m", "resolveai", "demo", "--no-llm"], clone, 1800)
    step("final verification (golden, frozen artifacts, cached evaluation, security scan)", [vpy, "scripts/final/f_final_verification.py"], clone, 3600)
    if not a.skip_frontend:
        fe = clone / "frontend"
        for name, cmd in (("npm ci", "npm ci"), ("npm run lint", "npm run lint"), ("npm run typecheck", "npm run typecheck"), ("npm test", "npm test"), ("npm run build", "npm run build")):
            step(name, cmd, fe, 3600)

    api = {"started": False}
    log = (scratch / "api.log").open("w", encoding="utf-8")
    proc = subprocess.Popen([vpy, "-m", "resolveai", "serve", "--port", str(a.port)], cwd=clone, env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        t = time.perf_counter()
        for _ in range(900):
            if proc.poll() is not None:
                break
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{a.port}/api/v1/ready", timeout=5) as r:
                    if r.status == 200:
                        api.update({"started": True, "ready_after_seconds": round(time.perf_counter() - t, 1)})
                        break
            except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
                pass
            time.sleep(1)
        if api["started"]:
            body = json.dumps({"conversation": [{"role": "customer", "text": "my iphone battery drains fast since the update"}]}).encode("utf-8")
            req = urllib.request.Request(f"http://127.0.0.1:{a.port}/api/v1/resolve", data=body, method="POST", headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=300) as r:
                res = json.loads(r.read().decode("utf-8"))
            api.update({"resolve_status": 200, "action": res.get("action"), "reason_code": res.get("outcome", {}).get("reason_code"),
                        "llm_configured": False, "safe_action_without_model": res.get("action") in ("CLARIFICATION_REQUIRED", "HUMAN_HANDOFF", "AUTO_HANDLE")})
    except Exception as e:  # noqa: BLE001 - recorded, not hidden
        api["error"] = type(e).__name__
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()
    report["api"] = api
    report["passed"] = all(s["exit_code"] == 0 for s in report["steps"]) and bool(api.get("safe_action_without_model"))
    report["failed_steps"] = [s["step"] for s in report["steps"] if s["exit_code"] != 0]
    report["wall_seconds"] = round(time.perf_counter() - t0, 1)
    report["limits"] = ["same operating system and base Python interpreter as the development machine",
                        "pip and npm download caches on this machine may be reused (the installed environment itself is new)",
                        "network access is required for pip, npm and the embedding-model download",
                        "no model key: live drafting, the risk model and the second opinion are not exercised; the agent's deterministic fallbacks are"]
    if not a.keep:
        shutil.rmtree(scratch, ignore_errors=True)
        report["temporary_directory"] = "deleted"
    else:
        report["temporary_directory"] = str(scratch)
    OUT.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "steps"}, indent=1))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
