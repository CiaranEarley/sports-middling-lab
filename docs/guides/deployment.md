# Deployment

This guide publishes Sports Middling Lab as a hosted Streamlit app while keeping
The Odds API key out of GitHub.

## Streamlit Cloud Settings

Use these settings when creating the app:

```text
Repository: CiaranEarley/sports-middling-lab
Branch: main
Main file path: app.py
Dependency file: requirements.txt
```

The app installs from `requirements.txt`, so no build command is needed.

## Secrets

Add secrets in the Streamlit Cloud app settings:

```toml
THE_ODDS_API_KEY = "your-key-here"
SPORTS_MIDDLING_PUBLIC_DEMO = true
SPORTS_MIDDLING_PUBLIC_MAX_CREDITS_PER_CLICK = 3
SPORTS_MIDDLING_PUBLIC_BUDGET = 500
SPORTS_MIDDLING_PUBLIC_RESERVE = 100
```

Do not commit `.streamlit/secrets.toml`. The repository only contains
`.streamlit/secrets.example.toml`.

## Visitor Safety

`SPORTS_MIDDLING_PUBLIC_DEMO = true` locks the credit controls so visitors
cannot raise the per-click API cap from the interface. The app still starts with
live calls disarmed, and no API request is made on page load or refresh.

Recommended public settings for a free 500-credit monthly plan:

- `SPORTS_MIDDLING_PUBLIC_MAX_CREDITS_PER_CLICK = 3`
- `SPORTS_MIDDLING_PUBLIC_RESERVE = 100`
- keep live API calls disarmed until the user intentionally scans
- keep event counts small in screenshots and demos

## Persistence

The local SQLite Research Log is suitable for local research and lightweight
demos. On hosted Streamlit, local files can reset when the app restarts and may
not behave like durable per-user storage.

For a production public app, use a hosted database and user-aware sessions.

## Publish Checklist

1. Confirm `main` is pushed to GitHub.
2. Create the Streamlit app from `CiaranEarley/sports-middling-lab`.
3. Set `app.py` as the main file.
4. Add the secrets above.
5. Deploy.
6. Open the app and confirm the API key message says the server-side key loaded.
7. Confirm live calls are disarmed on first load.
8. Run a one-event scan and check the API remaining-credit metric.
