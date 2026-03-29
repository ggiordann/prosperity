# Portal Adapters

Portal automation is optional and disabled by default.

Modes:
- `manual`: package a local submission bundle only
- `playwright`: optional browser automation with explicit config flags and dry-run support
- `equirag`: optional helper adapter, defaulting to dry-run/manual behavior

Every portal action should create:
- timestamped logs
- artifact manifests
- dry-run notes or screenshots where applicable
