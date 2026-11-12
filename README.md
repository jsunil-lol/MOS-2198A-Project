# Supplier Rescue AI

An AI-powered assistant that helps small manufacturers respond to unexpected supplier
delays. It identifies affected orders, evaluates alternative suppliers, and recommends
the most cost-effective recovery strategy.

This is a class prototype. All data is fictional.

## Run it

You need a Mac or Linux machine with Python 3 (it comes preinstalled on macOS).

```bash
./run.sh
```

The first run creates a virtual environment (`.venv`), installs dependencies, and
creates a `.env` file. The app then opens at http://localhost:8501.

To stop it, press `Ctrl+C` in the terminal.

## Add your Claude API key

1. Get an API key at https://console.anthropic.com.
2. Open the `.env` file in this folder. If it doesn't exist yet, run `./run.sh` once or
   copy `.env.example` to `.env`.
3. Paste the key after `ANTHROPIC_API_KEY=`.
4. Restart the app, then click **Test Claude connection** in the sidebar.

Never commit or share the `.env` file. It's already listed in `.gitignore`.

## Project layout

| File | What it does |
|---|---|
| `app.py` | The Streamlit web app (the pages you see) |
| `claude_client.py` | Every Claude API call goes through here |
| `data/` | Fictional demo data: orders, suppliers, sample email |
| `requirements.txt` | Python packages |
| `run.sh` | One-command launcher |
| `.env.example` | Template for your API key |

## Changing the model

The app uses `claude-opus-5-5` by default. To use a different model, set `CLAUDE_MODEL`
in `.env`.
