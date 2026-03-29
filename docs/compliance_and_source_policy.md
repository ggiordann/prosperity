# Compliance And Source Policy

## Core Rule
The internet is a prior, not the source of alpha. Public materials can inspire hypotheses, but generated submission code must come from internal specs, primitives, and templates.

## Source Classes
- `OFFICIAL_MECHANICS`
- `INTERNAL_CODE`
- `INTERNAL_RESULTS`
- `PUBLIC_IDEA`
- `PUBLIC_CODE_REFERENCE`
- `MANUAL_NOTES`

Each ingested document stores:
- `source_type`
- `source_uri_or_path`
- `fetched_at`
- `trust_level`
- `allowed_for_codegen`
- `allowed_for_mechanics`
- `allowed_for_strategy_hypotheses`
- `license_note`

## Allowed Uses
- `OFFICIAL_MECHANICS`: allowed for mechanics reasoning and compiler support
- `INTERNAL_CODE`: allowed
- `INTERNAL_RESULTS`: allowed
- `PUBLIC_IDEA`: allowed for hypothesis generation only
- `PUBLIC_CODE_REFERENCE`: never direct codegen input for submission compilation
- `MANUAL_NOTES`: allowed when authored by the team

## Quarantine Rules
- `.research_repos/` is read-only
- Summaries from `.research_repos/` are stored as motif notes, not raw prompt context for submission generation
- Public code similarity is checked before promotion and packaging

## Guardrails
- Hard block on high external code similarity
- Soft warning on high internal strategy similarity
- Behavioral similarity is tracked to avoid crowded strategy families
