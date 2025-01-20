import streamlit as st
from supabase import create_client
import os

def init_supabase():
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
    return create_client(supabase_url, supabase_key)

def init_auth():
    if 'supabase' not in st.session_state:
        st.session_state.supabase = init_supabase()
    if 'user' not in st.session_state:
        st.session_state.user = None

def login(email: str, password: str):
    try:
        auth = st.session_state.supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        st.session_state.user = auth.user
        return True
    except Exception as e:
        st.error(f"Error logging in: {str(e)}")
        return False

def signup(email: str, password: str):
    try:
        auth = st.session_state.supabase.auth.sign_up({
            "email": email,
            "password": password
        })
        st.session_state.user = auth.user
        return True
    except Exception as e:
        st.error(f"Error signing up: {str(e)}")
        return False

def logout():
    try:
        st.session_state.supabase.auth.sign_out()
        st.session_state.user = None
        return True
    except Exception as e:
        st.error(f"Error logging out: {str(e)}")
        return False

def is_logged_in():
    return st.session_state.user is not None

def login_signup_page():
    st.title("Welcome to Crawl4AI")
    
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")
            
            if submit:
                if login(email, password):
                    st.success("Logged in successfully!")
                    st.rerun()
    
    with tab2:
        with st.form("signup_form"):
            new_email = st.text_input("Email")
            new_password = st.text_input("Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            submit = st.form_submit_button("Sign Up")
            
            if submit:
                if new_password != confirm_password:
                    st.error("Passwords do not match!")
                else:
                    if signup(new_email, new_password):
                        st.success("Signed up successfully! Please log in.")
                        st.rerun()
