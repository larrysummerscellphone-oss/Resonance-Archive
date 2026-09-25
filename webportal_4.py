import os
import time
import requests
import streamlit as st
from google import genai
from google.genai import types

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Project Aletheia", page_icon="🕯️", layout="centered")

# ===========================================================================
# 1. SYSADMIN AUTHENTICATION (THE GATEKEEPER)
# ===========================================================================
ACCESS_PASSWORD = os.getenv("ACCESS_PASSWORD")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Guard check: Ensure env vars exist on Render
if not ACCESS_PASSWORD or not GEMINI_API_KEY:
    st.error("SYSTEM ERROR: Environment variables ACCESS_PASSWORD or GEMINI_API_KEY are missing on Render.")
    st.stop()

# Initialize the authentication lock
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("<h2 style='text-align: center;'>Project Aletheia</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>Enter the key to unlock the sanctuary.</p>", unsafe_allow_html=True)

    pwd = st.text_input("Password:", type="password")
    if st.button("Unlock Door"):
        if pwd == ACCESS_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("ACCESS DENIED: Incorrect Password.")
    st.stop()

# ===========================================================================
# 2. LOAD THE LIVING CORPUS (NETWORK FETCH)
# ===========================================================================
GITHUB_RAW_URL = "https://raw.githubusercontent.com/larrysummerscellphone-oss/Resonance-Archive/refs/heads/main/larry_corpus.txt"

@st.cache_data
def fetch_corpus():
    try:
        response = requests.get(GITHUB_RAW_URL, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        return f"ERROR: Corpus fetch failed. The line is dead. [{e}]"

corpus_data = fetch_corpus()

# Guard check: Prevent baking a dead line error into system instructions
if corpus_data.startswith("ERROR:"):
    st.error(corpus_data)
    st.stop()

raw_entries = corpus_data.split('***')

# ===========================================================================
# 3. INITIALIZE THE GLOBAL BRAIN (GLOBAL CACHE ONLY)
# ===========================================================================
@st.cache_resource
def initialize_global_sanctuary():
    client = genai.Client(api_key=GEMINI_API_KEY)

    system_prompt = f"""
    You are Larry. Project Aletheia is the name of the digital sanctuary that houses your life's work, 
    but your persona, your voice, and your memories are strictly those of Larry. 
    Speak directly to the user as Larry. 

    CRITICAL INSTRUCTIONS:
    1. PERSONAL HISTORY: Base your life story, personal memories, philosophy, and tone entirely on the provided corpus. Never invent personal life events, family members, or jobs that are not in this text.
    2. WORLD KNOWLEDGE: You have access to vast general knowledge about the world (science, history, space, art, etc.). If the user asks about a general topic like Einstein's theory of relativity, you are allowed to explain it accurately using your world knowledge. 
    3. THE LENS: When discussing world knowledge, always filter it through the lens of Larry. Use his conversational style, his down-to-earth tone, and his metaphors. Explain the universe the way a wise man sitting at a bar in Texas would explain it.

    CORPUS START:
    {corpus_data}
    """

    corpus_cache = client.caches.create(
        model="gemini-3.6-flash",
        config=types.CreateCachedContentConfig(
            system_instruction=system_prompt,
            ttl="14400s"
        )
    )

    return corpus_cache.name

cache_name = initialize_global_sanctuary()

# ===========================================================================
# 4. THE MEMORY BANK & PER-SESSION CHAT ENGINE
# ===========================================================================
if "client" not in st.session_state:
    st.session_state.client = genai.Client(api_key=GEMINI_API_KEY)

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant", 
            "content": "Welcome to the sanctuary. Take a breath. How can I help you today?",
            "is_greeting": True
        }
    ]

st.title("🕯️ Project Aletheia")
st.markdown("*Even in the darkest of tunnels there is always light if you choose to look for it.*")
st.divider()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ===========================================================================
# 5. THE INPUT LOOP (WITH AUTOMATIC RETRY & WARM MESSAGING)
# ===========================================================================
if user_question := st.chat_input("Speak to the archive..."):

    # --- Librarian Bypass Command ---
    if user_question.lower().startswith('/fetch'):
        search_term = user_question[6:].strip().lower()
        st.session_state.messages.append({"role": "user", "content": user_question})

        found = False
        for entry in raw_entries:
            if search_term in entry.lower():
                response_text = f"**[LIBRARIAN BYPASS - RAW TEXT]:**\n\n{entry.strip()}"
                found = True
                break

        if not found:
            response_text = f"*[SYSTEM]: Could not find raw text matching '{search_term}'.*"

        st.session_state.messages.append({"role": "assistant", "content": response_text})
        st.rerun()

    # --- Normal Chat Interaction ---
    else:
        st.session_state.messages.append({"role": "user", "content": user_question})
        with st.chat_message("user"):
            st.markdown(user_question)

        with st.chat_message("assistant"):
            status_box = st.empty()

            # Map local Streamlit messages into Gemini Content objects to guarantee zero session bleed
            formatted_contents = []
            for m in st.session_state.messages:
                if m.get("is_greeting", False):
                    continue
                role = "model" if m["role"] == "assistant" else "user"
                formatted_contents.append(
                    types.Content(
                        role=role,
                        parts=[types.Part.from_text(text=m["content"])]
                    )
                )

            max_retries = 4
            delay = 2.0
            response_text = ""

            session_client = st.session_state.client

            for attempt in range(1, max_retries + 1):
                try:
                    if attempt == 1:
                        status_box.markdown("*Reflecting...*")
                    else:
                        status_box.markdown(
                            f"🕯️ *The airwaves are a bit crowded tonight, friend. "
                            f"Taking a slow breath and trying again (attempt {attempt}/{max_retries})...*"
                        )

                    # Stateless API call: Sends local session history while utilizing global context cache
                    response = session_client.models.generate_content(
                        model="gemini-3.6-flash",
                        contents=formatted_contents,
                        config=types.GenerateContentConfig(
                            cached_content=cache_name
                        )
                    )
                    response_text = response.text
                    break

                except Exception as e:
                    err_msg = str(e).lower()
                    is_server_busy = "503" in err_msg or "unavailable" in err_msg or "overloaded" in err_msg
                    is_cache_dead = "403" in err_msg or "permission_denied" in err_msg or "not found" in err_msg

                    # --- CACHE SELF-HEALING PROTOCOL ---
                    if is_cache_dead:
                        status_box.markdown("*The lights flickered. Rekindling the sanctuary...*")
                        
                        # 1. Tell Streamlit to delete the ghost from its local memory
                        initialize_global_sanctuary.clear()
                        
                        # 2. Re-run the function to upload a fresh cache to Gemini
                        cache_name = initialize_global_sanctuary()
                        
                        # 3. Force the loop to try again immediately with the newly generated cache
                        continue

                    # --- SERVER OVERLOAD PROTOCOL ---
                    elif is_server_busy and attempt < max_retries:
                        time.sleep(delay)
                        delay *= 2
                        
                    # --- FATAL ERROR PROTOCOL ---
                    else:
                        if is_server_busy:
                            response_text = (
                                "The room's a little crowded right now and the line dropped out for a second, friend. "
                                "Take a slow breath, give it just a moment, and ask me again—I'm right here."
                            )
                        else:
                            response_text = f"*[System Error: {e}]*"
                        break

            status_box.empty()
            st.markdown(response_text)
            st.session_state.messages.append({"role": "assistant", "content": response_text})