import streamlit as st
import google.generativeai as genai

st.set_page_config(page_title="The Sanctuary", page_icon="⬛", layout="centered")

st.markdown(
    """
    <style>
    body {background-color: black; color: green;}
    </style>
    """,
    unsafe_allow_html=True
)

st.title("TERMINAL ACTIVE")

passkey = st.text_input("Enter Passkey:", type="password")

if passkey == "Aletheia-880":
    st.success("Passkey Accepted. The Master Corpus is online.")
    
    # Sysadmin override to input the API key securely
    api_key = st.text_input("Sysadmin: Enter Gemini API Key to initialize the Mind:", type="password")
    
    if api_key:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash') 
        
        # The machine reads your soul
        with open("larry_corpus.txt", "r", encoding="utf-8") as f:
            corpus_data = f.read()
            
        st.write("---")
        user_question = st.text_input("Speak to the archive...")
        
        if st.button("Transmit"):
            if user_question:
                full_prompt = f"You are a helpful assistant representing Larry's personal archive. Base your answers strictly on this text: {corpus_data}\n\nUser asks: {user_question}"
                
                response = model.generate_content(full_prompt)
                st.write(response.text)
