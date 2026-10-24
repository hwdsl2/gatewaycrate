# Changelog

Notable changes to GatewayCrate are documented here.

## 2026-10-24

Release: `2026.10.1`

### Changed

- Established the first tagged source release. Docker images continue to update
  independently through existing moving tags.

## 2026-10-09

### Changed

- Rebranded as GatewayCrate (formerly `docker-litellm`); the Docker image name
  remains `hwdsl2/litellm-server`.

## 2026-07-09

### Added

- Added anonymous aggregate deployment/upgrade counts. Opt out with
  `LITELLM_DISABLE_USAGE_COUNTS=1`.

## 2026-06-23

### Added

- Added the `ollama-chat/llama3.2:3b` alias using LiteLLM's chat provider while
  retaining `ollama/llama3.2:3b` for compatibility.
- Added `--supports-function-calling` to `litellm_manage --addmodel` to mark
  models as supporting tool calls.

## 2026-06-22

### Changed

- Fresh Compose installs now generate a PostgreSQL password and store it in
  the `litellm-secrets` volume. Existing default databases retain the legacy
  password for compatibility.

### Compatibility

- Back up `litellm-secrets` with `litellm-db`. If the database password was
  customized, set `LITELLM_POSTGRES_PASSWORD` to that password before starting
  the updated Compose stack, or retain a `LITELLM_DATABASE_URL` override.
- Pull the updated image before recreating services so it supports the new
  password-file configuration.

## Earlier notable changes

- Added an OpenAI-compatible proxy for local and remote model providers,
  automatic master-key generation, and persistent configuration.
- Added authenticated MCP integration, shared-key volumes for stack services,
  and PostgreSQL-backed state and virtual-key management.
