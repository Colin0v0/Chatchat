# Model Config Quickstart

This project uses a single model catalog: `backend/model_catalog.json`.

## Design

- `providers`: shared connection settings (provider/base_url/api_key)
- `models`: per-model settings (id/display_name/upstream_model/thinking_mode/context_window/native_multimodal/enabled)

This avoids repeated `base_url` and `api_key_env` blocks for each model.

## Add a new model

1. Pick a provider in `providers`, or add one.
2. Add one row under `models`:

```json
{
  "id": "openai_local:my-new-model",
  "display_name": "My New Model",
  "provider_ref": "openai_local_router",
  "upstream_model": "my-new-model",
  "thinking_mode": "default_on",
  "context_window": 65536,
  "native_multimodal": false,
  "enabled": true
}
```

3. Restart backend.

Important:
`id` is the stable primary key used for routing and persisted conversations.
Use `display_name` when you only want to change UI text.

`native_multimodal` means whether attachments should be uploaded to the upstream model service directly:

- `true`: upload files and let the upstream multimodal model handle them
- `false`: keep using local attachment parsing / OCR before sending text to the model

## Disable a model

Set `"enabled": false` on that model row.

## Thinking policy

- `force_on`: always on
- `force_off`: always off
- `default_on`: on unless user explicitly disables
- `default_off`: off unless user explicitly enables

## Strict mode

`MODEL_CATALOG_STRICT=true` in `.env` means:

- invalid catalog -> startup fails
- unknown model id in request -> request rejected

This keeps model management deterministic in production.
