from __future__ import annotations

import html
import os
import streamlit as st
from groq import Groq
from supabase import create_client, Client

st.set_page_config(page_title="MailCraft AI", page_icon="✉️", layout="wide")

# -----------------------------
# Secrets / clients
# -----------------------------
def secret(name: str) -> str:
    try:
        value = st.secrets.get(name, "")
        if value:
            return str(value).strip()
    except Exception:
        pass
    return os.getenv(name, "").strip()


def get_supabase() -> Client:
    url = secret("SUPABASE_URL")
    key = secret("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL or SUPABASE_KEY is missing in Streamlit Secrets.")
    return create_client(url, key)


def get_groq() -> Groq:
    key = secret("GROQ_API_KEY")
    if not key:
        raise ValueError("GROQ_API_KEY is missing in Streamlit Secrets.")
    return Groq(api_key=key)


# -----------------------------
# Session state
# -----------------------------
def init_state():
    defaults = {
        "user": None,
        "generated_email": "",
        "last_action": "",
        "auth_mode": "Login",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_state()


# -----------------------------
# CSS
# -----------------------------
st.markdown(
    """
<style>
.stApp { background: #f7f8fc; }
.block-container { max-width: 1200px; padding-top: 2rem; }
.hero { padding: 10px 0 22px; }
.hero h1 { font-size: 42px; margin: 0; color: #172033; }
.hero p { color: #667085; font-size: 16px; margin-top: 7px; }
.card { background: white; border: 1px solid #e4e7ec; border-radius: 16px; padding: 22px; }
.section-title { font-size: 21px; font-weight: 700; color: #172033; margin-bottom: 5px; }
.section-subtitle { color: #667085; font-size: 13px; margin-bottom: 18px; }
.small-muted { color: #667085; font-size: 13px; }
.history-item { background: white; border: 1px solid #e4e7ec; border-radius: 12px; padding: 14px; margin-bottom: 10px; }
</style>
""",
    unsafe_allow_html=True,
)


# -----------------------------
# Auth helpers
# -----------------------------
def current_user():
    return st.session_state.get("user")


def sign_in(email: str, password: str):
    sb = get_supabase()
    result = sb.auth.sign_in_with_password({"email": email, "password": password})
    st.session_state.user = result.user


def sign_up(email: str, password: str):
    sb = get_supabase()
    result = sb.auth.sign_up({"email": email, "password": password})
    if result.user is None:
        raise ValueError("Account could not be created.")
    # Depending on Supabase email-confirmation settings, session may be None.
    if result.session is not None:
        st.session_state.user = result.user
        return "Account created and logged in."
    return "Account created. Check your email if email confirmation is enabled, then log in."


def sign_out():
    try:
        get_supabase().auth.sign_out()
    except Exception:
        pass
    st.session_state.user = None
    st.session_state.generated_email = ""
    st.session_state.last_action = ""
    st.rerun()


# -----------------------------
# Groq generation
# -----------------------------
def build_prompt(action, tone, language, purpose, length, audience, extra, email_text):
    if action == "Generate Email":
        task = f"Create a new email from this request:\n{email_text}"
    elif action == "Improve Email":
        task = f"Improve this email while preserving its meaning and facts:\n{email_text}"
    else:
        task = f"Edit/rewrite this email according to the settings:\n{email_text}"

    return f"""You are MailCraft AI, a professional email writing assistant.

Action: {action}
Tone: {tone}
Language: {language}
Purpose: {purpose}
Length: {length}
Audience: {audience}
Additional instructions: {extra or 'None'}

{task}

Output rules:
1. Start with a clear line: Subject: ...
2. Then provide the complete email.
3. Follow the selected language, tone, purpose, audience, and length.
4. Preserve facts supplied by the user.
5. Do not invent names, dates, companies, attachments, credentials, promises, or other facts.
6. Do not explain your changes; output only the email.
"""


def generate_email(prompt: str) -> str:
    client = get_groq()

    # GPT-OSS 20B supports max_completion_tokens and include_reasoning=False.
    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {
                "role": "system",
                "content": "You are MailCraft AI. Write polished, natural, concise professional emails.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.5,
        max_completion_tokens=1400,
        include_reasoning=False,
        stream=False,
    )

    content = response.choices[0].message.content
    if not content or not content.strip():
        raise RuntimeError("Groq returned an empty response. Please try again.")
    return content.strip()


# -----------------------------
# Database helpers
# -----------------------------
def save_email(body, action, tone, language, purpose, length):
    user = current_user()
    if not user:
        raise ValueError("You must be logged in to save an email.")

    sb = get_supabase()
    sb.table("emails").insert(
        {
            "user_id": user.id,
            "subject": extract_subject(body),
            "body": body,
            "action": action,
            "tone": tone,
            "language": language,
            "purpose": purpose,
            "length": length,
        }
    ).execute()


def extract_subject(text: str) -> str:
    for line in text.splitlines():
        if line.strip().lower().startswith("subject:"):
            return line.split(":", 1)[1].strip()[:500]
    return ""


def load_history():
    user = current_user()
    if not user:
        return []
    sb = get_supabase()
    result = (
        sb.table("emails")
        .select("id,subject,body,action,tone,language,purpose,length,created_at")
        .eq("user_id", user.id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


def delete_email(email_id):
    user = current_user()
    if not user:
        return
    get_supabase().table("emails").delete().eq("id", email_id).eq("user_id", user.id).execute()


# -----------------------------
# Login / Signup
# -----------------------------
if not current_user():
    st.markdown('<div class="hero"><h1>✉️ MailCraft AI</h1><p>Write better emails, your way.</p></div>', unsafe_allow_html=True)

    tab_login, tab_signup = st.tabs(["Login", "Sign up"])

    with tab_login:
        st.markdown("### Welcome back")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login", type="primary", use_container_width=True):
            if not email.strip() or not password:
                st.warning("Please enter email and password.")
            else:
                try:
                    sign_in(email.strip(), password)
                    st.success("Login successful.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Login failed: {e}")

    with tab_signup:
        st.markdown("### Create your account")
        email2 = st.text_input("Email", key="signup_email")
        password2 = st.text_input("Password", type="password", key="signup_password")
        password3 = st.text_input("Confirm password", type="password", key="signup_confirm")
        if st.button("Create account", type="primary", use_container_width=True):
            if not email2.strip() or not password2:
                st.warning("Please enter email and password.")
            elif password2 != password3:
                st.error("Passwords do not match.")
            else:
                try:
                    msg = sign_up(email2.strip(), password2)
                    st.success(msg)
                    if current_user():
                        st.rerun()
                except Exception as e:
                    st.error(f"Signup failed: {e}")

    st.stop()


# -----------------------------
# Main app
# -----------------------------
user = current_user()

with st.sidebar:
    st.markdown("## ✦ MailCraft AI")
    st.caption(user.email if getattr(user, "email", None) else "Logged in")
    if st.button("Logout", use_container_width=True):
        sign_out()

    st.markdown("---")
    action = st.radio(
        "Choose an action",
        ["Generate Email", "Improve Email", "Edit Email"],
    )

st.markdown(
    '<div class="hero"><h1>Write emails your way.</h1><p>Generate, improve, edit, save and revisit your emails.</p></div>',
    unsafe_allow_html=True,
)

left, right = st.columns([1, 1], gap="large")

with left:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(f'<div class="section-title">{html.escape(action)}</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-subtitle">Customize your email and let AI do the writing.</div>', unsafe_allow_html=True)

    tone = st.selectbox(
        "Tone",
        ["Professional", "Formal", "Friendly", "Polite", "Casual", "Persuasive", "Confident", "Apologetic", "Warm"],
    )
    language = st.selectbox(
        "Language",
        ["English", "Urdu", "Roman Urdu", "Arabic", "French", "Spanish", "German", "Other"],
    )
    purpose = st.selectbox(
        "Purpose",
        ["Job Application", "Internship Application", "Leave Request", "Meeting Request", "Follow-up", "Thank You", "Complaint", "Business Inquiry", "Customer Support", "Cold Outreach", "Apology", "General", "Other"],
    )
    length = st.selectbox("Length", ["Very Short", "Short", "Medium", "Detailed", "Very Detailed"], index=2)
    audience = st.selectbox(
        "Audience",
        ["Manager / Supervisor", "HR / Recruiter", "Client / Customer", "Teacher / Professor", "Colleague", "Friend / Personal", "Business Partner", "General"],
    )

    input_label = "What do you want to say?" if action == "Generate Email" else "Email to work on"
    email_text = st.text_area(
        input_label,
        height=180,
        placeholder="Example: I want to apply for a Python internship. Mention my AI and Streamlit projects and ask about the application process.",
    )
    extra = st.text_area(
        "Additional instructions (optional)",
        height=90,
        placeholder="Example: Keep it concise and confident.",
    )

    generate_button = st.button("✨ Generate / Process Email", type="primary", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with right:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">AI Result</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-subtitle">Edit the result before saving or downloading.</div>', unsafe_allow_html=True)

    if generate_button:
        if not email_text.strip():
            st.warning("Please enter what you want the email to say.")
        else:
            prompt = build_prompt(action, tone, language, purpose, length, audience, extra.strip(), email_text.strip())
            with st.spinner("MailCraft is generating your email..."):
                try:
                    st.session_state.generated_email = generate_email(prompt)
                    st.session_state.last_action = action
                    st.success("Email generated successfully.")
                except Exception as e:
                    # Show the actual API error so deployment issues are diagnosable.
                    st.error(f"Email generation failed: {e}")

    result = st.session_state.generated_email

    if result:
        edited = st.text_area(
            "Final email",
            value=result,
            height=360,
            key="editable_result",
        )
        st.session_state.generated_email = edited

        c1, c2 = st.columns(2)
        with c1:
            if st.button("💾 Save to History", use_container_width=True):
                try:
                    save_email(edited, st.session_state.last_action, tone, language, purpose, length)
                    st.success("Email saved to your history.")
                except Exception as e:
                    st.error(f"Could not save email: {e}")
        with c2:
            st.download_button(
                "📥 Download .txt",
                data=edited,
                file_name="mailcraft_email.txt",
                mime="text/plain",
                use_container_width=True,
            )
    else:
        st.info("Your generated email will appear here.")

    st.markdown('</div>', unsafe_allow_html=True)


# -----------------------------
# History
# -----------------------------
st.markdown("## My Email History")
try:
    history = load_history()
    if not history:
        st.info("No saved emails yet. Generate an email and click Save to History.")
    else:
        for item in history:
            subject = item.get("subject") or "Untitled email"
            created = item.get("created_at", "")
            with st.expander(f"{subject} — {created[:19].replace('T', ' ')}"):
                st.text_area(
                    "Email",
                    value=item.get("body", ""),
                    height=220,
                    key=f"history_body_{item['id']}",
                )
                st.caption(
                    f"Action: {item.get('action','')} • Tone: {item.get('tone','')} • "
                    f"Language: {item.get('language','')} • Purpose: {item.get('purpose','')}"
                )
                if st.button("🗑️ Delete", key=f"delete_{item['id']}"):
                    try:
                        delete_email(item["id"])
                        st.success("Deleted.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Could not delete: {e}")
except Exception as e:
    st.error(f"Could not load email history: {e}")
