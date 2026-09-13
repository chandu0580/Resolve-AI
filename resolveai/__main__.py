"""ResolveAI command line.

    python -m resolveai resolve "my battery drains fast" [--history h.json] [--json] [--no-llm]
    python -m resolveai "my battery drains fast"                 # same as resolve
    python -m resolveai demo [--no-llm] [--json] [--save]        # scripted scenarios A-G
    python -m resolveai serve [--host 127.0.0.1] [--port 8000] [--env development|demo|test]

Every command uses the same ResolveAI orchestrator as the API; there is no second pipeline.
"""
from __future__ import annotations

import argparse
import os
import sys


def serve(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m resolveai serve")
    ap.add_argument("--host", default="127.0.0.1", help="bind address (default: loopback only)")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--env", default=os.getenv("RESOLVEAI_ENV", "development"), type=lambda s: s.strip().casefold(), choices=["development", "demo", "test", "production"])
    a = ap.parse_args(argv)
    os.environ["RESOLVEAI_ENV"] = a.env
    os.environ.setdefault("RESOLVEAI_EAGER_LOAD", "true")   # a served app must load its agent; only tests inject one (test profile default is false)
    import uvicorn

    uvicorn.run("resolveai.api.app:app_factory", factory=True, host=a.host, port=a.port, log_level="info")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if args[0] == "serve":
        return serve(args[1:])
    if args[0] == "demo":
        from resolveai.demo import main as demo_main

        return demo_main(args[1:])
    if args[0] == "resolve":
        args = args[1:]
    from resolveai.agent.__main__ import main as agent_main

    return agent_main(args)


if __name__ == "__main__":
    sys.exit(main())
