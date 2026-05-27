# The Odds API Setup

The app supports manual analysis without an API key. Live scanning requires a
The Odds API key.

![API key prompt](../assets/sports-middling-api-prompt-wide.png)

## Local Secrets

```powershell
New-Item -ItemType Directory -Force .streamlit
Copy-Item .streamlit/secrets.example.toml .streamlit/secrets.toml
notepad .streamlit/secrets.toml
```

Set:

```toml
THE_ODDS_API_KEY = "your-key-here"
```

`.streamlit/secrets.toml` is ignored by git.

## Public Deployment

A server-side key gives a smoother public demo because visitors do not need to
enter their own key. Add the key through hosted Streamlit secrets, never through
GitHub.

For a public deployment, enable the built-in demo guardrails:

```toml
THE_ODDS_API_KEY = "your-key-here"
SPORTS_MIDDLING_PUBLIC_DEMO = true
SPORTS_MIDDLING_PUBLIC_MAX_CREDITS_PER_CLICK = 3
SPORTS_MIDDLING_PUBLIC_BUDGET = 500
SPORTS_MIDDLING_PUBLIC_RESERVE = 100
```

See [Deployment](deployment.md) for the full publish checklist.

![Live scan controls](../assets/sports-middling-live-results-wide.png)
