import os
import streamlit as st
from groq import Groq
from supabase import create_client, Client

st.set_page_config(page_title="MailCraft AI", page_icon="✉️", layout="wide")

st.markdown("""
<style>
.stApp{background:#0b1020;color:#f5f7fb}
section[data-testid="stSidebar"]{background:#11182b;border-right:1px solid #26304a}
h1,h2,h3,p,label,span{color:#f5f7fb}
.mc-hero{padding:24px 28px;border:1px solid #2b3655;border-radius:18px;background:#151d33;margin-bottom:20px}
.mc-hero h1{margin:0 0 8px;font-size:42px}
.mc-hero p{margin:0;color:#b8c2d9}
div[data-testid="stTextArea"] textarea,div[data-testid="stTextInput"] input{color:#fff!important;background:#11182b!important;border:1px solid #33405f!important;caret-color:#fff!important}
div[data-testid="stTextArea"] textarea::placeholder,div[data-testid="stTextInput"] input::placeholder{color:#8994ad!important}
.stButton>button{border-radius:10px;border:1px solid #34415f;min-height:42px;font-weight:600}
.mc-tip{padding:12px 14px;border-radius:10px;background:#18213a;border:1px solid #2d3958;margin-bottom:8px;color:#cdd6e8;font-size:14px}
div[data-testid="stDownloadButton"] button{color:#fff!important;background:#1b2540!important;border:1px solid #3b496b!important}
div[data-testid="stDownloadButton"] button:hover{color:#fff!important;background:#1b2540!important;border-color:#3b496b!important}
</style>
""", unsafe_allow_html=True)

def secret(name):
    try:
        value = st.secrets.get(name)
        if value:
            return value
    except Exception:
        pass
    return os.getenv(name)

def supabase_client():
    url = secret("SUPABASE_URL")
    key = secret("SUPABASE_KEY")
    if not url or not key:
        return None
    return create_client(url, key)

def groq_key():
    return secret("GROQ_API_KEY")

def get_prompt(action, text, tone, language, purpose, length, audience, instructions):
    task = {
        "Generate Email":"Write a new email from the user's brief.",
        "Improve Email":"Improve the existing email while preserving its meaning.",
        "Edit Email":"Edit the email according to the additional instructions."
    }[action]
    return f"""You are MailCraft AI, an expert email-writing assistant.

TASK: {task}

INPUT:
{text}

SETTINGS:
Tone: {tone}
Language: {language}
Purpose: {purpose}
Length: {length}
Audience: {audience}
Additional instructions: {instructions or "None"}

Return ONLY the finished email.
Start with a Subject: line.
Do not add explanations or markdown fences.
Do not invent facts, names, dates, attachments or commitments."""

def generate(action, text, tone, language, purpose, length, audience, instructions):
    key = groq_key()
    if not key:
        raise RuntimeError("GROQ_API_KEY is missing. Add it in Streamlit Cloud → Settings → Secrets.")
    client = Groq(api_key=key)
    result = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {"role":"system","content":"You write accurate, polished emails."},
            {"role":"user","content":get_prompt(action,text,tone,language,purpose,length,audience,instructions)}
        ],
        temperature=0.5,
        max_tokens=1800
    )
    return result.choices[0].message.content.strip()

def current_user():
    return st.session_state.get("user")

def save_email(sb, user_id, content, action, tone, language, purpose, length):
    first, _, body = content.partition("\n")
    subject = first.replace("Subject:", "").strip()
    sb.table("emails").insert({
        "user_id": user_id,
        "subject": subject or "MailCraft Email",
        "body": body.strip() if body.strip() else content,
        "action": action,
        "tone": tone,
        "language": language,
        "purpose": purpose,
        "length": length,
    }).execute()

def login_ui(sb):
    st.sidebar.markdown("## 🔐 Account")
    mode = st.sidebar.radio("Choose", ["Login", "Sign Up"], horizontal=True)
    email = st.sidebar.text_input("Email", key="auth_email")
    password = st.sidebar.text_input("Password", type="password", key="auth_password")

    if mode == "Sign Up":
        if st.sidebar.button("Create Account", use_container_width=True):
            try:
                result = sb.auth.sign_up({"email": email, "password": password})
                if result.user:
                    st.sidebar.success("Account created. Check your email if confirmation is enabled.")
            except Exception as e:
                st.sidebar.error(str(e))
    else:
        if st.sidebar.button("Login", use_container_width=True):
            try:
                result = sb.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.user = result.user
                st.rerun()
            except Exception as e:
                st.sidebar.error(str(e))

def history_ui(sb):
    user = current_user()
    if not user:
        return
    st.subheader("📚 My Email History")
    try:
        rows = sb.table("emails").select("*").eq("user_id", user.id).order("created_at", desc=True).execute().data
        if not rows:
            st.info("No saved emails yet.")
            return
        for row in rows:
            with st.expander(f"{row.get('subject') or 'Untitled'} • {row.get('created_at','')[:10]}"):
                st.text_area("Saved email", row.get("body",""), height=180, key=f"hist_{row['id']}")
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        "⬇️ Download",
                        data=row.get("body",""),
                        file_name="mailcraft_saved_email.txt",
                        mime="text/plain",
                        key=f"download_{row['id']}",
                        use_container_width=True
                    )
                with col2:
                    if st.button("🗑️ Delete", key=f"delete_{row['id']}", use_container_width=True):
                        sb.table("emails").delete().eq("id", row["id"]).eq("user_id", user.id).execute()
                        st.rerun()
    except Exception as e:
        st.error(f"Could not load history: {e}")

if "result" not in st.session_state:
    st.session_state.result = ""
if "user" not in st.session_state:
    st.session_state.user = None

sb = supabase_client()

with st.sidebar:
    st.markdown("## ✉️ MailCraft AI")
    st.caption("AI Email Writer & Editor")
    st.divider()

    if sb:
        if current_user():
            st.success(f"Logged in as {current_user().email}")
            if st.button("Logout", use_container_width=True):
                try:
                    sb.auth.sign_out()
                except Exception:
                    pass
                st.session_state.user = None
                st.rerun()
        else:
            login_ui(sb)
    else:
        st.warning("Supabase is not configured. Writer mode is available, but login/history are disabled.")

    st.divider()
    tone=st.selectbox("Tone",["Professional","Formal","Friendly","Polite","Casual","Persuasive","Confident","Apologetic","Warm"])
    language=st.selectbox("Language",["English","Urdu","Roman Urdu","Arabic","French","Spanish","German","Other"])
    purpose=st.selectbox("Purpose",["Job Application","Internship Application","Leave Request","Meeting Request","Follow-up","Thank You","Complaint","Business Inquiry","Customer Support","Cold Outreach","Apology","General","Other"])
    length=st.selectbox("Length",["Very Short","Short","Medium","Detailed","Very Detailed"],index=2)
    audience=st.selectbox("Audience",["Manager / Supervisor","HR / Recruiter","Client / Customer","Teacher / Professor","Colleague","Friend / Personal","Business Partner","General"])
    instructions=st.text_input("Additional instructions",placeholder="e.g. sound confident but not pushy")

    st.divider()
    st.markdown("### 💡 Quick Tips")
    st.markdown('<div class="mc-tip">Be specific about the goal.</div>',unsafe_allow_html=True)
    st.markdown('<div class="mc-tip">Mention important context.</div>',unsafe_allow_html=True)
    st.markdown('<div class="mc-tip">Use Improve Email for an existing draft.</div>',unsafe_allow_html=True)

st.markdown('<div class="mc-hero"><h1>✉️ MailCraft AI</h1><p>Generate, improve, edit and save professional emails with AI.</p></div>',unsafe_allow_html=True)

left,right=st.columns(2,gap="large")
with left:
    st.subheader("📝 Your Email")
    action=st.radio("Choose an action",["Generate Email","Improve Email","Edit Email"],horizontal=True)
    placeholders={
        "Generate Email":"Example: Write an email to HR asking about my internship application status.",
        "Improve Email":"Paste your existing email here.",
        "Edit Email":"Paste your email and describe what you want changed."
    }
    source=st.text_area("Input",height=330,placeholder=placeholders[action],label_visibility="collapsed")
    if st.button("✨ Generate / Process Email",use_container_width=True):
        if not source.strip():
            st.warning("Please enter an email request or draft.")
        else:
            with st.spinner("MailCraft AI is writing..."):
                try:
                    st.session_state.result=generate(action,source,tone,language,purpose,length,audience,instructions)
                except Exception as e:
                    st.error(str(e))

with right:
    st.subheader("🤖 AI Result")
    st.caption("Edit the result before saving or downloading.")
    st.session_state.result=st.text_area("AI Result",value=st.session_state.result,height=330,key="result_editor",label_visibility="collapsed",placeholder="Your generated email will appear here...")
    if st.session_state.result.strip():
        c1,c2=st.columns(2)
        with c1:
            st.download_button("⬇️ Download .txt",st.session_state.result,"mailcraft_email.txt","text/plain",use_container_width=True)
        with c2:
            if sb and current_user():
                if st.button("💾 Save Email",use_container_width=True):
                    try:
                        save_email(sb,current_user().id,st.session_state.result,action,tone,language,purpose,length)
                        st.success("Email saved to your history.")
                    except Exception as e:
                        st.error(f"Could not save email: {e}")
            else:
                st.button("💾 Save Email",disabled=True,use_container_width=True)

        if st.button("🗑️ Clear Result",use_container_width=True):
            st.session_state.result=""
            st.rerun()

if sb and current_user():
    st.divider()
    history_ui(sb)

st.divider()
st.caption("MailCraft AI V3 • Supabase persistence + Groq AI")
