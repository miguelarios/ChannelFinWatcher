# ChannelFinWatcher Documentation

Start here to find the right document.

## For users
- **[User Guide](user-guide.md)** — every feature and how to use it (dashboard,
  channels, history, settings, downloads, cookies, notifications, troubleshooting).
- **[Configuration Reference](configuration.md)** — all settings and where they
  live (web UI, `config.yaml`, environment variables).
- **[Deployment Guide](DEPLOYMENT.md)** — production install, volumes, ports,
  updates, backups.

## For developers / integrators
- **[API Reference](api-reference.md)** — every REST endpoint (also live at
  `/docs` and `/redoc` on a running instance).
- **[Technical Design Document](tdd.md)** — architecture, data model, algorithms,
  and future roadmap.
- **[Development Guide](development-guide.md)** — local dev workflow and tooling.
- **[Testing Guide](testing-guide.md)** — running and writing tests.
- **[Code Documentation Guide](code-documentation-guide.md)** — docstring/comment
  standards.
- **[CI/CD Explained](CI-CD-EXPLAINED.md)** — the pipeline.

## Product & planning
- **[PRD](prd.md)** — product requirements and goals.
- **[User Stories](stories/)** — original per-feature specs. Where the shipped
  implementation diverged from the plan, the story carries an **as-built note**
  at the top.
- **[Tech Docs](tech-docs/)** — focused technical notes (download behavior,
  metadata spec).

## Feature → documentation map

| Feature | Where it's documented |
|---------|----------------------|
| Adding & managing channels | [User Guide → Channels](user-guide.md#channels) |
| Status dashboard | [User Guide → Dashboard](user-guide.md#dashboard) |
| Download history & retry | [User Guide → History](user-guide.md#history) |
| Live download progress | [User Guide → Live progress](user-guide.md#live-progress) |
| Quality presets | [Configuration → Quality presets](configuration.md#quality-presets) |
| Scheduling (global + per-channel) | [Configuration → Scheduling](configuration.md#scheduling) |
| Failure notifications | [Configuration → Notifications](configuration.md#notifications) |
| YouTube cookies | [User Guide → Cookies](user-guide.md#youtube-cookies) |
| Storage monitoring | [User Guide → Dashboard](user-guide.md#dashboard) |
| Health checks & logs | [API Reference → System](api-reference.md#system) |
| REST API | [API Reference](api-reference.md) |
| Architecture & internals | [TDD](tdd.md) |
