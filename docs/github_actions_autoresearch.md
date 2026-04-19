# GitHub Actions Autoresearch

The repository includes `.github/workflows/autoresearch.yml`, which runs one autoresearch cycle every 5 minutes.

## Required GitHub Secret

Add this repository secret:

```text
DISCORD_BOT_TOKEN
```

Use the bot token from the Discord developer portal. Do not commit it.

## Optional Repository Variables

These can be set under repository settings:

```text
DISCORD_CHANNEL_ID=1487759408711729192
DISCORD_PROMOTE_PING_USER_ID=1487799311113650316
AUTORESEARCH_EXPERIMENTS=6
PROSPERITY_DEFAULT_DATASET=round2
```

If unset, the workflow uses the values above.

## Behavior

- Runs on GitHub-hosted Ubuntu every 5 minutes.
- Installs Python dependencies.
- Warms the Rust backtester build using the cache.
- Restores `data/autoresearch/` from cache so the recipe rotation keeps moving.
- Runs `python -m prosperity.cli autoresearch cycle`.
- Sends the full cycle detail to Discord.
- Does not write markdown/json reports.
- Does not auto-promote or push code.
- If a candidate clears the promotion gate, the generated candidate file is uploaded as a short-lived GitHub Actions artifact.

## Manual Run

Open the workflow in GitHub Actions and choose **Run workflow**. You can override the experiment count for a single run.

## Notes

GitHub scheduled workflows are not guaranteed to start exactly on the minute, but the cron is set to the minimum practical cadence: every 5 minutes.
