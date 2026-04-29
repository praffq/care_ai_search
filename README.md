# care_ai

A basic AI search plugin for [OHC CARE](https://github.com/ohcnetwork/care). Given a CARE encounter id and a natural-language prompt, it lets an OpenAI model fetch read-only data about the patient and encounter (demographics, allergies, diagnoses, symptoms, medications, observations, prior encounters) via a small set of tools, and returns a structured JSON response that conforms to a JSON Schema you supply.

## Endpoint

```
POST /api/care_ai/v1/run/
```

Auth: superuser only

## Installation

1. Add the plugin to `care/plug_config.py`:

   ```python
   from plugs.manager import PlugManager
   from plugs.plug import Plug

   care_ai_plug = Plug(
       name="care_ai",
       package_name="git+https://github.com/praffq/care_ai.git",
       version="@main",
       configs={},
   )

   plugs = [care_ai_plug]
   manager = PlugManager(plugs)
   ```

2. Set the required environment variables in `docker/.local.env` (or your prod env):

   ```env
   AI_API_KEY=sk-...
   AI_BASE_URL=https://api.openai.com/v1
   AI_DEFAULT_MODEL=gpt-5.4
   AI_MAX_TOOL_CALLS=10
   AI_TIMEOUT_SECONDS=30
   AI_PROMPT_MAX_CHARS=2000
   ```

3. Rebuild and restart CARE so the plugin is installed into the image:

   ```bash
   make down
   make build
   make up
   ```

## Configuration

| Setting | Default | Notes |
|---|---|---|
| `AI_API_KEY` | — (required) | OpenAI-compatible API key |
| `AI_BASE_URL` | `https://api.openai.com/v1` | Swap for Azure / Ollama / vLLM |
| `AI_DEFAULT_MODEL` | `gpt-5.4` | Model used when the request does not pin one |
| `AI_ALLOWED_MODELS` | `["gpt-5.4", "gpt-5.4-mini", "gpt-5.2", "gpt-5-mini", "gpt-4.1", "gpt-4.1-mini", "gpt-4o", "gpt-4o-mini"]` | Allow-list enforced on the request |
| `AI_MAX_TOOL_CALLS` | `10` | Per-request tool-call budget |
| `AI_TIMEOUT_SECONDS` | `30` | Hard wall-clock timeout for the agent loop |
| `AI_PROMPT_MAX_CHARS` | `8000` | Max length for `prompt` |

## License

MIT.
