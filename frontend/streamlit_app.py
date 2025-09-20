import streamlit as st
import requests
import json
import os
import time

# Backend API URL
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:5000")

st.set_page_config(
    page_title="Resume-JD Matcher",
    page_icon="📄",
    layout="wide"
)

st.title("📄 Resume-JD Matcher Dashboard")

# Helper function for retries
def call_backend_with_retry(method, url, files=None, json=None, data=None, retries=3, backoff_factor=1):
    st.info(f"Attempting to call backend: Method={method.upper()}, URL={url}")
    for i in range(retries):
        try:
            if method == "post":
                response = requests.post(url, files=files, json=json, data=data)
            elif method == "get":
                response = requests.get(url)
            response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
            return response
        except requests.exceptions.ConnectionError:
            if i < retries - 1:
                st.warning(f"Connection to backend failed. Retrying in {backoff_factor * (2 ** i)} seconds...")
                time.sleep(backoff_factor * (2 ** i))
            else:
                st.error(f"Backend not reachable at {BACKEND_URL}. Please ensure the backend is running and accessible.")
                st.stop()
        except requests.exceptions.RequestException as e:
            st.error(f"An unexpected error occurred: {e}")
            st.stop()
    return None # Should not be reached if st.stop() is called

# --- Sidebar Navigation ---
page = st.sidebar.radio("Navigation", ["Upload JD", "Upload Resume & Match", "View Results", "Search & Review"])

# --- Page Content ---
if page == "Upload JD":
    st.header("Upload Job Description")
    jd_text = st.text_area("Paste Job Description Here:", height=300)
    if st.button("Parse JD"):
        if jd_text:
            with st.spinner("Parsing Job Description..."):
                response = call_backend_with_retry("post", f"{BACKEND_URL}/upload_jd", json={"job_description": jd_text})
                if response:
                    if response.status_code == 200:
                        st.success("Job Description parsed successfully!")
                        st.json(response.json())
                    else:
                        st.error(f"Error parsing JD: {response.json().get('error', 'Unknown error')}")
        else:
            st.warning("Please paste a job description to parse.")

elif page == "Upload Resume & Match":
    st.header("Upload Resume and Match with JD")

    # Fetch existing JDs to allow selection. For now, we'll manually input JD ID/Text
    st.warning("Currently, you need to manually provide the Job Description Text or ID for matching.")

    uploaded_resume_file = st.file_uploader("Upload Resume (PDF/DOCX)", type=["pdf", "docx"])
    jd_text_for_match = st.text_area("Paste Job Description Text for Matching:", height=200)
    
    hard_match_weight = st.slider("Hard Match Weight", 0.0, 1.0, 0.5, 0.1)
    semantic_match_weight = st.slider("Semantic Match Weight", 0.0, 1.0, 0.5, 0.1)

    if st.button("Match Resume to JD"):
        if uploaded_resume_file and jd_text_for_match:
            with st.spinner("Matching Resume to Job Description..."):
                files = {"resume_file": (uploaded_resume_file.name, uploaded_resume_file.getvalue(), uploaded_resume_file.type)}
                data = {
                    "job_description_text": jd_text_for_match,
                    "hard_match_weight": hard_match_weight,
                    "semantic_match_weight": semantic_match_weight
                }
                response = call_backend_with_retry("post", f"{BACKEND_URL}/aggregate_match_results", files=files, data=data)
                
                if response:
                    if response.status_code == 200:
                        st.success("Matching completed successfully!")
                        st.json(response.json())
                        st.session_state['last_match_result'] = response.json()
                    else:
                        st.error(f"Error during matching: {response.json().get('error', 'Unknown error')}")
        else:
            st.warning("Please upload a resume and paste the job description text.")

elif page == "View Results":
    st.header("View All Evaluation Results")

    if st.button("Fetch All Results"):
        with st.spinner("Fetching results from database..."):
            response = call_backend_with_retry("get", f"{BACKEND_URL}/evaluations")
            if response:
                if response.status_code == 200:
                    evaluations = response.json()
                    if evaluations:
                        for eval_result in evaluations:
                            st.subheader(f"Evaluation ID: {eval_result['id']} (Score: {eval_result['final_relevance_score']}%)")
                            st.write(f"Suitability: {eval_result['suitability_verdict']}")
                            st.write(f"Resume Filename: {eval_result['resume_filename']}")
                            st.write(f"JD Role: {eval_result['jd_role_title']}")
                            with st.expander("Details"):
                                st.json(eval_result)
                            st.markdown("---")
                    else:
                        st.info("No evaluation results found yet.")
                else:
                    st.error(f"Error fetching results: {response.json().get('error', 'Unknown error')}")

elif page == "Search & Review":
    st.header("Search and Review Candidate Suggestions")

    search_query = st.text_input("Search by JD Role Title or Resume Filename:")
    
    if st.button("Search Evaluations"):
        if search_query:
            with st.spinner(f"Searching for '{search_query}'..."):
                # This would ideally be a dedicated search endpoint, but for simplicity
                # we'll fetch all and filter in frontend for now.
                # In a real app, optimize this with backend search.
                response = call_backend_with_retry("get", f"{BACKEND_URL}/evaluations")
                if response:
                    if response.status_code == 200:
                        all_evaluations = response.json()
                        search_results = [
                            e for e in all_evaluations 
                            if search_query.lower() in e.get('jd_role_title', '').lower() or \
                               search_query.lower() in e.get('resume_filename', '').lower()
                        ]

                        if search_results:
                            st.subheader(f"Found {len(search_results)} results for '{search_query}':")
                            for eval_result in search_results:
                                st.subheader(f"Evaluation ID: {eval_result['id']} (Score: {eval_result['final_relevance_score']}%)")
                                st.write(f"Suitability: {eval_result['suitability_verdict']}")
                                st.write(f"Resume Filename: {eval_result['resume_filename']}")
                                st.write(f"JD Role: {eval_result['jd_role_title']}")
                                with st.expander("Details and Suggestions"):
                                    st.json(eval_result)
                                    if eval_result.get('missing_elements'):
                                        st.write("**Missing Elements & Suggestions:**")
                                        for item in eval_result['missing_elements']:
                                            st.markdown(f"- **{item['element']}**: {item['suggestion']}")
                                st.markdown("---")
                        else:
                            st.info(f"No results found for '{search_query}'.")
                    else:
                        st.error(f"Error fetching evaluations for search: {response.json().get('error', 'Unknown error')}")
        else:
            st.warning("Please enter a search query.")
