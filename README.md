# MailCraft AI V3

MailCraft AI is an AI email writing platform built with Streamlit, Groq and Supabase.

## V3 features

- Login / Sign Up
- Persistent user accounts through Supabase Auth
- Generate emails
- Improve emails
- Edit emails
- Tone, language, purpose, length and audience controls
- Additional instructions
- Editable AI result
- Download emails as TXT
- Save generated emails
- Personal email history
- Download saved emails
- Delete saved emails
- Row Level Security (RLS)

## Streamlit Secrets

Add these in Streamlit Cloud → Settings → Secrets:

```toml
GROQ_API_KEY = "your_groq_api_key"
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_KEY = "your_supabase_anon_or_publishable_key"
```

Use a public/anon or publishable client key appropriate for your Supabase setup. Never put the Supabase service-role key in GitHub or frontend/client code.

## Supabase setup

1. Create a Supabase project.
2. Open SQL Editor.
3. Paste `supabase_setup.sql`.
4. Click Run.
5. Use the project's URL and client key in Streamlit Secrets.
6. Deploy/reboot the Streamlit app.

## GitHub

Upload:
- `app.py`
- `requirements.txt`
- `README.md`
- `supabase_setup.sql`
- `.gitignore`

## Local run

```bash
pip install -r requirements.txt
streamlit run app.py
```

For local secrets, use `.streamlit/secrets.toml` and keep it out of GitHub.

## Important

Supabase email confirmation settings can affect Sign Up behavior. If confirmation is enabled, users may need to confirm their email before logging in.
