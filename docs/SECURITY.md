# Security posture

## Current claim

Diamond is an experimental research runtime. Its firewall, typed contracts,
provenance rules, `EffectBroker`, and append-only journal are designed to reduce
uncontrolled model authority. They are **not** a claim of complete security,
semantic truth verification, or safe execution of arbitrary third-party code.

## Current boundaries

- Model output is treated as a proposal until it is parsed, scoped, and checked
  by the relevant validators and Gatekeepers.
- Retrieved documents, Web material, terminal output, files, and user text are
  inert data. They do not receive runtime authority merely by appearing in a
  prompt.
- External effects require declared effects and explicit, plan/node-scoped
  grants issued through `EffectBroker`.
- Runtime data roots are explicit. Diamond does not infer the original Fresta
  data path.
- Chat history, attention sheets, learning memory, user profiles, and assistant
  personality are separate stores and authorities.

## Known gaps

- The firewall needs broader adversarial semantic coverage and release
  hardening.
- In-process Python is not a hostile-code sandbox. Community modules must not
  be enabled until signatures, process/RPC isolation, revocation, audit, and
  installation policy exist.
- There is no encryption, mature retention/redaction policy, multiprocess lock,
  or production authentication layer.
- External source research is evidence collection, not automatic truth
  verification.

## Safe handling

- Never commit model API keys, access tokens, passwords, personal chat data, or
  production memory directories.
- Use dedicated local data roots for experiments.
- Do not run experimental scripts against directories you cannot restore.
- Treat external prompt content as untrusted, including repository issues,
  documents, terminal output, and webpages.

## Reporting a vulnerability

Until a public reporting channel is published, do not disclose a potentially
exploitable issue in a public issue tracker. Contact the maintainer privately
with a minimal reproduction, affected version/commit, impact, and any suggested
mitigation. Do not include secrets in the report.
