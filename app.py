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

    sb = create_client(url, key)

    # Streamlit reruns the script, so a fresh Supabase client is created.
    # Re-attach the user's session AND explicitly attach the JWT to
    # PostgREST. The second step is important for RLS-protected inserts.
    stored = st.session_state.get("supabase_session")
    if stored:
        access_token = stored.get("access_token")
        refresh_token = stored.get("refresh_token")
        if access_token and refresh_token:
            # set_session can refresh an expired access token.
            sb.auth.set_session(access_token, refresh_token)

            # Always use the current token (possibly refreshed above).
            current_session = sb.auth.get_session()
            if current_session is not None:
                current_access = current_session.access_token
                current_refresh = current_session.refresh_token
                st.session_state.supabase_session = {
                    "access_token": current_access,
                    "refresh_token": current_refresh,
                }
                sb.postgrest.auth(current_access)

    return sb


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
        "supabase_session": None,
        "generated_email": "",
        "last_action": "",
        "auth_mode": "Login",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_state()



# -----------------------------
# Premium UI
# -----------------------------
st.markdown(r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root{--ink:#172033;--muted:#667085;--line:#e8eaf2}
.stApp{background:linear-gradient(135deg,#f7f8fc,#f1f4fb);font-family:Inter,sans-serif}
.block-container{max-width:1450px;padding:1.4rem 2rem 3rem}
section[data-testid="stSidebar"]{background:linear-gradient(180deg,#0e1b3d,#101936 55%,#17265a);border-right:0}
section[data-testid="stSidebar"]>div{padding:1.3rem 1rem}
section[data-testid="stSidebar"] *{color:#eef2ff!important}
.sidebar-logo{font-size:23px;font-weight:800;margin:3px 8px 2px}.sidebar-tag{color:#aebbe8!important;font-size:11px;margin:0 8px 25px}
.sidebar-card{margin-top:80px;padding:18px;border-radius:18px;background:linear-gradient(145deg,rgba(77,87,180,.35),rgba(35,49,103,.28));border:1px solid rgba(255,255,255,.1)}
.topbar{display:flex;justify-content:space-between;align-items:center;gap:20px;margin-bottom:18px}.eyebrow{color:#6d3df5;font-size:13px;font-weight:800;text-transform:uppercase;letter-spacing:.08em}.hero-title{font-size:40px;line-height:1.05;font-weight:800;color:var(--ink);letter-spacing:-1.5px;margin:3px 0 8px}.hero-sub{color:var(--muted);font-size:15px;margin:0}.user-pill{background:#fff;border:1px solid var(--line);border-radius:14px;padding:10px 14px;color:#344054;font-size:13px;box-shadow:0 6px 20px rgba(31,41,70,.05)}
.feature{background:#fff;border:1px solid var(--line);border-radius:18px;padding:17px 18px;height:100%;box-shadow:0 7px 25px rgba(31,41,70,.045)}.feature-icon{width:40px;height:40px;display:flex;align-items:center;justify-content:center;border-radius:12px;background:linear-gradient(135deg,#ece7ff,#e9f1ff);font-size:20px;margin-bottom:10px}.feature-title{color:#202b44;font-weight:750;font-size:14px}.feature-text{color:#7a849a;font-size:12px;line-height:1.45;margin-top:4px}
.app-card{background:#fff;border:1px solid var(--line);border-radius:20px;padding:22px;box-shadow:0 12px 35px rgba(31,41,70,.055)}.card-head{display:flex;align-items:center;gap:12px;margin-bottom:18px}.card-icon{width:44px;height:44px;border-radius:13px;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#5d73ff,#8b5cf6);color:white;font-size:21px}.card-title{color:#172033;font-size:21px;font-weight:800}.card-sub{color:#7a849a;font-size:12px;margin-top:3px}.result-empty{min-height:355px;border:1px dashed #d9dce8;border-radius:16px;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;background:linear-gradient(180deg,#fff,#fafbff)}.empty-icon{font-size:50px;margin-bottom:12px}.empty-title{color:#25304a;font-weight:750;font-size:16px}.empty-text{color:#8992a5;font-size:12px;max-width:280px;margin-top:5px}
.auth-wrap{max-width:1050px;margin:45px auto}.auth-brand{background:linear-gradient(160deg,#0d1b3f,#1a2d67);border-radius:24px 0 0 24px;min-height:590px;padding:45px 38px;color:white}.auth-brand h1{font-size:34px;line-height:1.08;margin:15px 0 12px}.auth-brand p{color:#c5cff1;line-height:1.6;font-size:14px}.auth-point{margin:20px 0;color:#e7ebff;font-size:13px}.auth-form{background:#fff;border:1px solid var(--line);border-radius:24px;min-height:590px;padding:40px 42px;box-shadow:0 20px 60px rgba(31,41,70,.08)}
/* The auth form is a real Streamlit bordered container so widgets stay inside it. */
[data-testid="stVerticalBlockBorderWrapper"]{border-radius:24px!important;border:1px solid #e8eaf2!important;background:#fff!important;box-shadow:0 20px 60px rgba(31,41,70,.08)!important}
[data-testid="stVerticalBlockBorderWrapper"] > div{padding:30px 34px!important}
.stTextInput input,.stTextArea textarea,.stSelectbox div[data-baseweb="select"]>div{border-radius:11px!important;border-color:#dfe3ee!important;background:#fff!important;color:#172033!important}.stButton>button,.stDownloadButton>button{border-radius:11px!important;font-weight:700!important;min-height:43px}.stButton>button[kind="primary"]{background:linear-gradient(90deg,#6939f5,#4d8df7)!important;border:0!important;color:white!important}.stDownloadButton>button{border:1px solid #dfe3ee!important;background:white!important;color:#344054!important}label,.stMarkdown p{color:#344054}.history-card{background:#fff;border:1px solid var(--line);border-radius:15px;padding:15px 17px;margin-bottom:10px;box-shadow:0 5px 18px rgba(31,41,70,.035)}.history-title{color:#202b44;font-weight:750;font-size:14px}.history-meta{color:#8992a5;font-size:11px;margin-top:5px}div[data-testid="stAlert"]{border-radius:12px}
@media(max-width:900px){.hero-title{font-size:31px}.block-container{padding:1rem}.auth-brand{border-radius:20px;min-height:auto}
[data-testid="stVerticalBlockBorderWrapper"]{border-radius:20px!important}.auth-brand{margin-bottom:12px}}
</style>
""",unsafe_allow_html=True)

# -----------------------------
# Auth helpers
# -----------------------------
def current_user():
    return st.session_state.get("user")


def sign_in(email: str, password: str):
    # Use a fresh client for login because no session exists yet.
    url = secret("SUPABASE_URL")
    key = secret("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL or SUPABASE_KEY is missing in Streamlit Secrets.")

    sb = create_client(url, key)
    result = sb.auth.sign_in_with_password({"email": email, "password": password})
    if result.user is None or result.session is None:
        raise ValueError("Login succeeded without a Supabase session. Please try again.")

    # Explicitly bind the JWT to PostgREST so RLS sees this request as
    # the authenticated user, not as anon.
    sb.postgrest.auth(result.session.access_token)

    st.session_state.user = result.user
    st.session_state.supabase_session = {
        "access_token": result.session.access_token,
        "refresh_token": result.session.refresh_token,
    }


def sign_up(email: str, password: str):
    sb = get_supabase()
    result = sb.auth.sign_up({"email": email, "password": password})
    if result.user is None:
        raise ValueError("Account could not be created.")
    # Depending on Supabase email-confirmation settings, session may be None.
    if result.session is not None:
        st.session_state.user = result.user
        st.session_state.supabase_session = {
            "access_token": result.session.access_token,
            "refresh_token": result.session.refresh_token,
        }
        return "Account created and logged in."
    return "Account created. Check your email if email confirmation is enabled, then log in."


def sign_out():
    try:
        get_supabase().auth.sign_out()
    except Exception:
        pass
    st.session_state.user = None
    st.session_state.supabase_session = None
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
    st.markdown('<div class="auth-wrap">', unsafe_allow_html=True)
    a1,a2=st.columns([1.05,1],gap="small")
    with a1:
        st.markdown('''<div class="auth-brand"><div style="font-size:28px">✉️ <b>MailCraft AI</b> ✨</div><h1>Turn your ideas into professional emails.</h1><p>Write, improve, edit and save polished emails with AI — in seconds.</p><div class="auth-point">✓ AI-powered email generation</div><div class="auth-point">✓ Save & revisit your email history</div><div class="auth-point">✓ Multiple tones, languages and purposes</div><div class="auth-point">✓ Secure personal workspace</div></div>''',unsafe_allow_html=True)
    with a2:
        # IMPORTANT: use a real Streamlit container for the auth panel.
        # Raw HTML <div> elements cannot wrap Streamlit widgets, which previously
        # caused the white panel to appear above the Login/Sign up controls.
        with st.container(border=True):
            st.markdown('<div class="eyebrow">Your workspace</div><h2 style="margin:4px 0 6px;color:#172033">Welcome to MailCraft AI</h2><p style="color:#667085;font-size:13px">Sign in or create your free account to continue.</p>',unsafe_allow_html=True)
            auth_choice=st.radio("Account",["Login","Sign up"],horizontal=True,key="auth_choice")
            if auth_choice=="Login":
                email=st.text_input("Email address",key="login_email",placeholder="you@example.com")
                password=st.text_input("Password",type="password",key="login_password",placeholder="Enter your password")
                if st.button("Login",type="primary",use_container_width=True):
                    if not email.strip() or not password: st.warning("Please enter email and password.")
                    else:
                        try: sign_in(email.strip(),password); st.rerun()
                        except Exception as e: st.error(f"Login failed: {e}")
                st.caption("Don't have an account? Select **Sign up** above.")
            else:
                email2=st.text_input("Email address",key="signup_email",placeholder="you@example.com")
                password2=st.text_input("Password",type="password",key="signup_password",placeholder="At least 6 characters")
                password3=st.text_input("Confirm password",type="password",key="signup_confirm",placeholder="Repeat your password")
                if st.button("Create account",type="primary",use_container_width=True):
                    if not email2.strip() or not password2: st.warning("Please enter email and password.")
                    elif password2!=password3: st.error("Passwords do not match.")
                    elif len(password2)<6: st.error("Password must be at least 6 characters.")
                    else:
                        try:
                            msg=sign_up(email2.strip(),password2); st.success(msg)
                            if current_user(): st.rerun()
                        except Exception as e: st.error(f"Signup failed: {e}")
                st.caption("Already have an account? Select **Login** above.")
    st.markdown('</div>',unsafe_allow_html=True); st.stop()

# -----------------------------
# Main dashboard
# -----------------------------
user=current_user()
with st.sidebar:
    st.markdown('<div class="sidebar-logo">✉️ MailCraft AI ✨</div><div class="sidebar-tag">Smart Emails, Better Opportunities</div>',unsafe_allow_html=True)
    st.markdown(f'<div style="padding:9px 8px;color:#dbe4ff!important;font-size:12px">👤 {html.escape(getattr(user,"email",None) or "Logged in")}</div>',unsafe_allow_html=True)
    st.markdown("---")
    st.markdown('<div style="font-size:11px;color:#9aa9d8!important;text-transform:uppercase;letter-spacing:.08em;margin:5px 8px 8px">Workspace</div>',unsafe_allow_html=True)
    action=st.radio("",["Generate Email","Improve Email","Edit Email"],label_visibility="collapsed")
    st.markdown('<div class="sidebar-card"><div style="font-size:20px">✦</div><b>Write better emails.</b><br><span style="color:#b8c5ed!important;font-size:12px">Open bigger opportunities with clear, professional communication.</span></div>',unsafe_allow_html=True)
    st.markdown("---")
    if st.button("↪ Logout",use_container_width=True): sign_out()

name=html.escape((getattr(user,"email",None) or "there").split("@")[0])
st.markdown(f'<div class="topbar"><div><div class="eyebrow">AI Email Workspace</div><div class="hero-title">Hello, {name}! 👋</div><p class="hero-sub">Your AI-powered email assistant is ready to help you craft the perfect email.</p></div><div class="user-pill">✉️ {html.escape(getattr(user,"email",None) or "Account")}</div></div>',unsafe_allow_html=True)

f1,f2,f3,f4=st.columns(4,gap="medium")
features=[("✨","AI Powered","Create polished emails in seconds"),("⚙️","Customizable","Tailor tone, language and purpose"),("🛡️","Secure & Private","Your personal workspace"),("☁️","Save & Access","Keep emails for future use")]
for col,(ic,ti,tx) in zip([f1,f2,f3,f4],features):
    with col: st.markdown(f'<div class="feature"><div class="feature-icon">{ic}</div><div class="feature-title">{ti}</div><div class="feature-text">{tx}</div></div>',unsafe_allow_html=True)
st.write("")

left,right=st.columns([1,1],gap="medium")
with left:
    st.markdown(f'<div class="app-card"><div class="card-head"><div class="card-icon">✉️</div><div><div class="card-title">{html.escape(action)}</div><div class="card-sub">Describe what you need and let AI craft it for you.</div></div></div>',unsafe_allow_html=True)
    c1,c2=st.columns(2)
    with c1: purpose=st.selectbox("Email Purpose",["Job Application","Internship Application","Leave Request","Meeting Request","Follow-up","Thank You","Complaint","Business Inquiry","Customer Support","Cold Outreach","Apology","General","Other"],index=1 if action=="Generate Email" else 0)
    with c2: tone=st.selectbox("Tone",["Professional","Formal","Friendly","Polite","Casual","Persuasive","Confident","Apologetic","Warm"])
    c3,c4=st.columns(2)
    with c3: language=st.selectbox("Language",["English","Urdu","Roman Urdu","Arabic","French","Spanish","German","Other"])
    with c4: length=st.selectbox("Length",["Very Short","Short","Medium","Detailed","Very Detailed"],index=2)
    audience=st.selectbox("Audience",["Manager / Supervisor","HR / Recruiter","Client / Customer","Teacher / Professor","Colleague","Friend / Personal","Business Partner","General"])
    input_label="What do you want to say?" if action=="Generate Email" else "Email to work on"
    email_text=st.text_area(input_label,height=150,placeholder="Example: I want to apply for a Python internship and ask about the application process.",key="email_input")
    extra=st.text_area("Additional instructions (optional)",height=75,placeholder="Example: Keep it concise and confident.",key="extra_input")
    generate_button=st.button("✨  Generate / Process Email",type="primary",use_container_width=True)
    st.markdown('</div>',unsafe_allow_html=True)

with right:
    st.markdown('<div class="app-card"><div class="card-head"><div class="card-icon">✦</div><div><div class="card-title">Your Email</div><div class="card-sub">Review, edit, save or download your result.</div></div></div>',unsafe_allow_html=True)
    if generate_button:
        if not email_text.strip(): st.warning("Please enter what you want the email to say.")
        else:
            with st.spinner("MailCraft is writing your email..."):
                try:
                    st.session_state.generated_email=generate_email(build_prompt(action,tone,language,purpose,length,audience,extra.strip(),email_text.strip()))
                    st.session_state.last_action=action
                    st.session_state.result_editor=st.session_state.generated_email
                    st.rerun()
                except Exception as e: st.error(f"Email generation failed: {e}")
    result=st.session_state.generated_email
    if result:
        edited=st.text_area("Final email",height=330,key="result_editor")
        st.session_state.generated_email=edited
        b1,b2=st.columns(2)
        with b1:
            if st.button("💾 Save to History",use_container_width=True):
                try:
                    save_email(edited,st.session_state.last_action,tone,language,purpose,length)
                    st.session_state.history_notice=True
                    st.rerun()
                except Exception as e: st.error(f"Could not save email: {e}")
        with b2: st.download_button("📥 Download .txt",data=edited,file_name="mailcraft_email.txt",mime="text/plain",use_container_width=True)
    else: st.markdown('<div class="result-empty"><div class="empty-icon">✉️</div><div class="empty-title">Your generated email will appear here</div><div class="empty-text">Fill in the details on the left and click “Generate / Process Email”.</div></div>',unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)

if st.session_state.pop("history_notice",False): st.success("✅ Email saved to your history.")

st.markdown("## My Email History")
st.markdown('<p style="color:#7a849a;font-size:13px">View and manage your saved emails. Your history is private to your account.</p>',unsafe_allow_html=True)
st.button("↻ Refresh History",key="refresh_history")
try:
    history=load_history()
    if not history: st.info("No saved emails yet. Generate an email and click Save to History.")
    else:
        for item in history:
            subject=item.get("subject") or "Untitled email"; created=item.get("created_at","")
            st.markdown('<div class="history-card">',unsafe_allow_html=True)
            hc1,hc2=st.columns([5,1])
            with hc1: st.markdown(f'<div class="history-title">{html.escape(subject)}</div><div class="history-meta">{html.escape(created[:19].replace("T"," "))} · {html.escape(item.get("purpose") or "General")} · {html.escape(item.get("tone") or "Professional")}</div>',unsafe_allow_html=True)
            with hc2:
                if st.button("🗑️ Delete",key=f"delete_{item['id']}"):
                    try: delete_email(item["id"]); st.rerun()
                    except Exception as e: st.error(f"Could not delete: {e}")
            with st.expander("View email"): st.text_area("Email",value=item.get("body","") ,height=190,key=f"history_body_{item['id']}")
            st.markdown('</div>',unsafe_allow_html=True)
except Exception as e: st.error(f"Could not load email history: {e}")
