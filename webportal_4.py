import os
import streamlit as st
import requests
import time
from google import genai
from google.genai import types

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Project Aletheia", page_icon="🕯️", layout="centered")

# ===========================================================================
# 1. SYSADMIN AUTHENTICATION (THE GATEKEEPER)
# ===========================================================================
# 1. Attempt to pull from System Environment Variables (Render Production)
ACCESS_PASSWORD = os.getenv("ACCESS_PASSWORD")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Initialize the lock
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("<h2 style='text-align: center;'>Project Aletheia</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>Enter the key to unlock the sanctuary.</p>", unsafe_allow_html=True)
    
    pwd = st.text_input("Password:", type="password")
    if st.button("Unlock Door"):
        if pwd == ACCESS_PASSWORD:
            st.session_state.authenticated = True
            st.rerun() # Reloads the page to bypass the gate
        else:
            st.error("ACCESS DENIED: Incorrect Password.")
    st.stop() # Halts the script so no unauthorized code runs

# ===========================================================================
# 2. LOAD THE LIVING CORPUS (NETWORK FETCH)
# ===========================================================================
# The direct pipe to the raw text file (No HTML UI)
GITHUB_RAW_URL = "https://raw.githubusercontent.com/larrysummerscellphone-oss/Resonance-Archive/refs/heads/main/larry_corpus.txt"

# Use cache_data for pure text strings instead of cache_resource
@st.cache_data
def fetch_corpus():
    try:
        response = requests.get(GITHUB_RAW_URL, timeout=10)
        response.raise_for_status() # Triggers an error if the connection fails
        return response.text
    except Exception as e:
        return f"ERROR: Corpus fetch failed. The line is dead. [{e}]"

corpus_data = fetch_corpus()
raw_entries = corpus_data.split('***')

# ===========================================================================
# 3. INITIALIZE THE BRAIN (SESSION STATE CACHING)
# ===========================================================================
# We only want to build the Google Cache once to save money and time
@st.cache_resource
def initialize_engine():
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
    
    # Upload to Google RAM
    corpus_cache = client.caches.create(
        model="gemini-3.6-flash",
        config=types.CreateCachedContentConfig(
            system_instruction=system_prompt,
            ttl="14400s"
        )
    )
    
    # Establish Chat Session
    chat = client.chats.create(
        model="gemini-3.6-flash",
        config=types.GenerateContentConfig(
            cached_content=corpus_cache.name
        )
    )
    
    # THE FIX: Return the client AND the chat so the bridge stays open forever
    return client, chat

# Unpack both the client and the chat engine into memory
google_client, chat_engine = initialize_engine()

# ===========================================================================
# 4. THE MEMORY BANK (CHAT HISTORY)
# ===========================================================================
if "messages" not in st.session_state:
    # First time loading, give them a greeting from Larry
    st.session_state.messages = [
        {"role": "assistant", "content": "Welcome to the sanctuary. Take a breath. How can I help you today?"}
    ]

# Draw the screen title
st.title("🕯️ Project Aletheia")
st.markdown("*Even in the darkest of tunnels there is always light if you choose to look for it.*")
st.divider()

# Redraw all past messages from the memory bank
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ===========================================================================
# 5. THE INPUT LOOP (WITH AUTOMATIC 503 RETRY & WARM MESSAGING)
# ===========================================================================
if user_question := st.chat_input("Speak to the archive..."):

    # --- The Librarian Bypass Command ---
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
        # 1. Record and display user message
        st.session_state.messages.append({"role": "user", "content": user_question})
        with st.chat_message("user"):
            st.markdown(user_question)

        # 2. Process AI Response with Retry Logic
        with st.chat_message("assistant"):
            status_box = st.empty()  # Dynamic container for status updates

            max_retries = 4
            delay = 2.0  # Initial sleep time in seconds
            success = False
            response_text = ""

            for attempt in range(1, max_retries + 1):
                try:
                    # Show initial loading message or warm retry update
                    if attempt == 1:
                        status_box.markdown("*Reflecting...*")
                    else:
                        status_box.markdown(
                            f"🕯️ *The airwaves are a bit crowded tonight, friend. "
                            f"Taking a slow breath and trying again (attempt {attempt}/{max_retries})...*"
                        )

                    # Send prompt to engine
                    response = chat_engine.send_message(user_question)
                    response_text = response.text
                    success = True
                    break  # Success! Break out of the retry loop

                except Exception as e:
                    err_msg = str(e).lower()
                    # Detect 503, unavailable, or rate/capacity overload errors
                    is_server_busy = "503" in err_msg or "unavailable" in err_msg or "overloaded" in err_msg

                    if is_server_busy and attempt < max_retries:
                        time.sleep(delay)
                        delay *= 2  # Exponential backoff (2s -> 4s -> 8s)
                    else:
                        # Final error message if retries are exhausted or it's a non-503 issue
                        if is_server_busy:
                            response_text = (
                                "The room's a little crowded right now and the line dropped out for a second, friend. "
                                "Take a slow breath, give it just a moment, and ask me again—I'm right here."
                            )
                        else:
                            response_text = f"*[System Error: {e}]*"
                        break

            # Clear status text and display final response
            status_box.empty()
            st.markdown(response_text)
            st.session_state.messages.append({"role": "assistant", "content": response_text})