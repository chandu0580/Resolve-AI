# Final browser smoke

Results of `frontend/scripts/smoke.mjs`, run against release 1.0.0 in three modes. The run used the installed Microsoft Edge with
axe-core (WCAG 2.1 A/AA) and the orchestration in `docs/REPRODUCIBILITY.md`.

| File | Mode | Result |
|---|---|---|
| `smoke_results.json` | Console with the server-side token → API with authentication required | 29 routes, 7 of 7 scenarios matched their expectations, 0 failed interactions, 0 axe violations, 0 overflowing pages. The single console error is the deliberate 404 page. |
| `smoke_unauthorized.json` | Console without a token → same API | 3 routes show "Not authorized"; 0 failures, 0 console errors |
| `smoke_api_down.json` | Console with the API stopped | 4 routes show "ResolveAI API unavailable"; 0 failures. The 4 console errors are the forwarder's intended 502 responses. |

**Screenshots.** Only 10 representative screenshots are kept, to keep the repository small:
- overview, simulation result, conversation workspace, trace timeline, injection trace, handoff packet and evaluation;
- mobile workspace;
- unauthorized and API-down states.

The JSON files still list every screenshot the run captured (45). Run the smoke again to regenerate the full set. Screenshots from
earlier phases remain in `artifacts/phase8/screenshots` and `artifacts/phase9/smoke/screenshots`.
