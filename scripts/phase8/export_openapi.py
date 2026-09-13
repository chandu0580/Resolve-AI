"""Phase 8: export the FastAPI OpenAPI document for the frontend's generated TypeScript types.
  python scripts/phase8/export_openapi.py        (npm run gen:api runs this, then openapi-typescript)
Does not load the agent: the schema comes from the route and pydantic models only."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from resolveai.api.app import create_app  # noqa: E402
from resolveai.api.settings import ApiSettings  # noqa: E402

OUT = ROOT / "frontend" / "lib" / "api" / "openapi.json"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    spec = create_app(ApiSettings.for_profile("test")).openapi()
    OUT.write_text(json.dumps(spec, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(spec['paths'])} paths, {len(spec.get('components', {}).get('schemas', {}))} schemas)")


if __name__ == "__main__":
    main()
