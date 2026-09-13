# LLM smoke-test results

Dev set: 30 hand-labelled examples x 4 tasks (intent, evidence extraction, grounded reply, escalation) = 120 calls per model.

| provider | model | failure_rate | schema_valid_rate | intent_accuracy | evidence_grounded_rate | reply_compliance | reply_evidence_overlap | escalation_accuracy | latency_p50_ms | latency_p95_ms | tokens_out | cost_usd_per_100_msgs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| primary | glm-5.2 | 0.0 | 0.95 | 0.867 | 0.933 | 1 | 0.454 | 0.567 | 5173.735 | 10292.53 | 37535 | 0.492 |
| gemini | gemini-2.5-flash | 1.0 |  |  |  |  |  |  |  |  |  |  |
| gemini | gemini-3.5-flash-lite | 1.0 |  |  |  |  |  |  |  |  |  |  |
| gemini | gemini-3.8-flash | 1.0 |  |  |  |  |  |  |  |  |  |  |
| groq | openai/gpt-oss-120b | 0.083 | 0.917 | 0.733 | 0.993 | 0.7 | 0.186 | 0.8 | 4166.769 | 5918.181 | 30575 | 0.094 |
| groq | openai/gpt-oss-20b | 0.175 | 0.825 | 0.7 | 0.933 | 0.367 | 0.285 | 0.867 | 4770.617 | 6102.586 | 30674 | 0.062 |
| groq | qwen/qwen3.8-27b | 0.008 | 0.992 | 0.833 | 1.0 | 1 | 0.573 | 0.667 | 2478.076 | 6584.272 | 6545 | None |

Errors (first 3 per model):

- gemini:gemini-2.5-flash: ["PermissionDeniedError: Error code: 403 - [{'error': {'code': 403, 'message': 'Your project has been denied access. Please contact support.', 'status': 'PERMISSION_DENIED'}}]"]
- gemini:gemini-3.5-flash-lite: ["PermissionDeniedError: Error code: 403 - [{'error': {'code': 403, 'message': 'Your project has been denied access. Please contact support.', 'status': 'PERMISSION_DENIED'}}]"]
- gemini:gemini-3.8-flash: ["PermissionDeniedError: Error code: 403 - [{'error': {'code': 403, 'message': 'Your project has been denied access. Please contact support.', 'status': 'PERMISSION_DENIED'}}]"]
- groq:openai/gpt-oss-120b: ['BadRequestError: Error code: 400 - {\'error\': {\'message\': "Failed to generate JSON. Please adjust your prompt. See \'failed_generation\' for more details.", \'type\': \'invalid_request_error\', \'code\': \'json_validate_failed\', \'failed_generation\': \'max completion tokens reached before generating a valid doc', "RateLimitError: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-120b` in organization `org_01m0wk1pa4eb0thz7ypnkjfxsj` service tier `on_demand` on tokens per minute (TPM): Limit 8000, Used 7193, Requested 838. Please try again in 232.499999ms. Need more tokens? ", 'BadRequestError: Error code: 400 - {\'error\': {\'message\': "Failed to validate JSON. Please adjust your prompt. See \'failed_generation\' for more details.", \'type\': \'invalid_request_error\', \'code\': \'json_validate_failed\', \'failed_generation\': \'\'}}']
- groq:openai/gpt-oss-20b: ['BadRequestError: Error code: 400 - {\'error\': {\'message\': "Failed to validate JSON. Please adjust your prompt. See \'failed_generation\' for more details.", \'type\': \'invalid_request_error\', \'code\': \'json_validate_failed\', \'failed_generation\': \'\'}}', 'BadRequestError: Error code: 400 - {\'error\': {\'message\': "Failed to validate JSON. Please adjust your prompt. See \'failed_generation\' for more details.", \'type\': \'invalid_request_error\', \'code\': \'json_validate_failed\', \'failed_generation\': \'\'}}', 'BadRequestError: Error code: 400 - {\'error\': {\'message\': "Failed to validate JSON. Please adjust your prompt. See \'failed_generation\' for more details.", \'type\': \'invalid_request_error\', \'code\': \'json_validate_failed\', \'failed_generation\': \'\'}}']
- groq:qwen/qwen3.8-27b: ["RateLimitError: Error code: 429 - {'error': {'message': 'Rate limit reached for model `qwen/qwen3.8-27b` in organization `org_01m0wk1pa4eb0thz7ypnkjfxsj` service tier `on_demand` on output tokens per minute (OTPM): Limit 1000, Used 894, Requested 118. Please try again in 720ms. Need more tokens? Upg"]