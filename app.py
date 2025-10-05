
import streamlit as st
import transformers
import openai
import langchain
import os

# If this file is executed directly with `python app.py` (instead of
# `streamlit run app.py`) Streamlit's ScriptRunContext and session state
# are not available which produces many noisy warnings and broken
# behavior. Detect that case and exit with a short instruction.
try:
    # streamlit's runtime API provides get_script_run_ctx(); when running
    # under `streamlit run` it returns a context object, otherwise None.
    from streamlit.runtime.scriptrunner import script_run_context as _script_ctx

    if _script_ctx.get_script_run_ctx() is None:
        print("This is a Streamlit app. Start it with: streamlit run app.py")
        import sys

        sys.exit(0)
except Exception:
    # If the internal API isn't available for some Streamlit versions,
    # skip the guard and allow Streamlit to run (it may still emit warnings).
    pass

st.title("AI-Powered Resume, Cover Letter, and Portfolio Generator")

st.subheader("Enter Your Information")
skills = st.text_area("Skills (comma-separated)", "")
projects = st.text_area("Projects (list each project on a new line)", "")
experience = st.text_area("Experience (list each job/role on a new line)", "")

st.subheader("Customization Options")
resume_template = st.selectbox("Select Resume Template", [
                               "Classic", "Modern", "Creative"])
tone = st.radio("Preferred Tone", ["Professional", "Creative", "Enthusiastic"])
# Workaround controls when OpenAI quota is exhausted
use_mock = st.checkbox("Use mock responses (no OpenAI calls)", value=False)
max_tokens = st.number_input(
    "Max tokens (for OpenAI requests)", min_value=50, max_value=2000, value=500, step=50)

st.subheader("Generated Content")
# Use st.empty() to create containers for the output
resume_output_container = st.empty()
cover_letter_output_container = st.empty()
portfolio_output_container = st.empty()


st.subheader("Portfolio Projects")

# Initialize a list to store project data in session state
if 'project_data' not in st.session_state:
    st.session_state.project_data = []

num_projects = st.number_input("Number of Projects", min_value=0, value=len(
    st.session_state.project_data), step=1)

# Adjust the length of project_data list based on num_projects
if num_projects > len(st.session_state.project_data):
    for _ in range(num_projects - len(st.session_state.project_data)):
        st.session_state.project_data.append({
            "title": "",
            "description": "",
            "link": "",
            "image": None
        })
elif num_projects < len(st.session_state.project_data):
    st.session_state.project_data = st.session_state.project_data[:num_projects]


for i in range(num_projects):
    st.markdown(f"#### Project {i+1}")
    st.session_state.project_data[i]["title"] = st.text_input(
        f"Project {i+1} Title", value=st.session_state.project_data[i]["title"], key=f"project_title_{i}")
    st.session_state.project_data[i]["description"] = st.text_area(
        f"Project {i+1} Description", value=st.session_state.project_data[i]["description"], key=f"project_description_{i}")
    st.session_state.project_data[i]["link"] = st.text_input(
        f"Project {i+1} Link (URL)", value=st.session_state.project_data[i]["link"], key=f"project_link_{i}")
    st.session_state.project_data[i]["image"] = st.file_uploader(
        f"Upload Image for Project {i+1} (Optional)", type=["png", "jpg", "jpeg"], key=f"project_image_{i}")


generate_button = st.button("Generate Content")

# Small utility: validate the OpenAI API key with a very cheap API call


def validate_api_key():
    """Validate the configured OpenAI API key using a low-cost API call.
    Returns (ok: bool, message: str).
    """
    # Reuse the same key resolution logic as generate_text
    key = os.getenv("OPENAI_API_KEY")
    try:
        if not key and hasattr(st, "secrets"):
            key = st.secrets.get("OPENAI_API_KEY")
    except Exception:
        pass

    if not key:
        return False, "No API key found in environment or Streamlit secrets."

    # Try new OpenAI client first (openai>=1.0.0)
    try:
        from openai import OpenAI

        client = OpenAI(api_key=key)
        # models.list is cheap and suitable for validation
        client.models.list()
        return True, "OpenAI API key is valid (new client)."
    except Exception as e_new:
        # Fallback to older openai package interfaces
        try:
            openai.api_key = key
            # older SDK exposes Model.list()
            openai.Model.list()
            return True, "OpenAI API key is valid (old client)."
        except Exception as e_old:
            # Prefer to return the newer exception message but include both
            msg = f"Validation failed. New client error: {e_new}; Fallback error: {e_old}"
            return False, msg


# Add a lightweight validate button so users can check their key without generating content
if st.button("Validate API Key"):
    with st.spinner("Validating API key..."):
        ok, message = validate_api_key()
        if ok:
            st.success(message)
        else:
            st.error(message)

# Function to generate text using the OpenAI API


def generate_text(prompt, max_tokens_override=None, mock=False):
    """Generates text using the OpenAI API."""
    # If mock mode is enabled, return a deterministic placeholder and avoid API calls
    if mock:
        return f"(MOCK) Generated content for prompt preview. Prompt starts: {prompt[:120]}..."
    # Respect a max_tokens override from the UI
    if max_tokens_override is None:
        max_tokens_override = 500
    # Try multiple locations for the API key: environment variable first, then Streamlit secrets
    openai_api_key = os.getenv("OPENAI_API_KEY")
    try:
        # st.secrets behaves like a dict and may not exist in some runtimes
        if not openai_api_key and hasattr(st, "secrets"):
            openai_api_key = st.secrets.get("OPENAI_API_KEY")
    except Exception:
        # If accessing st.secrets fails for any reason, ignore and continue
        openai_api_key = openai_api_key

    if not openai_api_key:
        # Provide actionable instructions for Windows PowerShell and Streamlit secrets
        st.error(
            "OpenAI API key not found. Please add your key as an environment variable or in Streamlit secrets.")
        # Diagnostic information (safe - does not reveal the key value)
        try:
            cwd = os.getcwd()
            st.markdown(f"- Current working directory: `{cwd}`")
        except Exception:
            pass

        # Show whether an env var exists (masked) to help debugging
        try:
            env_val = os.getenv("OPENAI_API_KEY")
            if env_val:
                masked = env_val[:4] + "..." + env_val[-4:]
                st.markdown(
                    f"- Environment variable `OPENAI_API_KEY` is set (masked): `{masked}`")
            else:
                st.markdown(
                    "- Environment variable `OPENAI_API_KEY` is not set")
        except Exception:
            pass

        # Show which top-level keys exist in st.secrets (if available)
        try:
            if hasattr(st, "secrets") and st.secrets:
                try:
                    secrets_keys = list(st.secrets.keys())
                except Exception:
                    secrets_keys = []
                st.markdown(
                    f"- Keys present in `st.secrets`: `{secrets_keys}`")
            else:
                st.markdown(
                    "- `st.secrets` is empty or not available in this runtime")
        except Exception:
            pass

        st.markdown("**Quick fix (temporary, PowerShell):**\n"
                    "Copy and run the following in the same PowerShell window before starting Streamlit:\n\n"
                    "```powershell\n$env:OPENAI_API_KEY=\"<your-key-here>\"\nstreamlit run app.py\n```")
        st.markdown("**Persistent fix (recommended):** create `.streamlit/secrets.toml` in your project root with:\n\n"
                    "```toml\nOPENAI_API_KEY=\"<your-key-here>\"\n```\n\n"
                    "Then run `streamlit run app.py`.")
        return None

    try:
        # Prefer the new OpenAI client (openai>=1.0.0)
        try:
            from openai import OpenAI

            client = OpenAI(api_key=openai_api_key)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens_override,
                temperature=0.7,
            )
        except Exception:
            # Fallback for older openai versions (pre-1.0.0)
            openai.api_key = openai_api_key
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens_override,
                n=1,
                stop=None,
                temperature=0.7,
            )

        # Response structure: response.choices[0].message.content
        if response and getattr(response, "choices", None):
            # Some clients return choices as a list of dicts
            choice = response.choices[0]
            # Support both dict-style and object-style responses
            content = None
            if isinstance(choice, dict):
                # OpenAI python client returns dict-like structures
                content = choice.get("message", {}).get("content")
            else:
                # Fallback for attribute access
                content = getattr(choice, "message", None)
                if content:
                    content = getattr(content, "content", None)

            if content:
                return content.strip()
        # Unexpected response format
        st.error("OpenAI returned an unexpected response format.")
        return None
    except Exception as e:
        st.error(f"Error generating text: {e}")
        return None


# CSS Styling
css_style = """
<style>
body {
    font-family: 'Arial', sans-serif;
    line-height: 1.6;
    color: #333;
    background: linear-gradient(to right, #f0f4f8, #e8f0fe);
    transition: background 0.5s ease-in-out;
}

.generated-content h3 {
    color: #0056b3;
    margin-top: 20px;
    margin-bottom: 10px;
    border-bottom: 2px solid #0056b3;
    padding-bottom: 5px;
    position: relative;
    animation: slideIn 0.6s ease-out;
}

.generated-content h3::after {
    content: '';
    position: absolute
</style>
"""

st.markdown(css_style, unsafe_allow_html=True)


if generate_button:
    # Capture user input
    user_skills = skills
    user_projects_text = projects  # Renamed to avoid conflict with project_data list
    user_experience = experience

    # Basic cleaning and formatting for text areas
    processed_skills = [skill.strip()
                        for skill in user_skills.split(',') if skill.strip()]
    processed_projects_text_list = [
        project.strip() for project in user_projects_text.split('\n') if project.strip()]
    processed_experience = [exp.strip()
                            for exp in user_experience.split('\n') if exp.strip()]

    # Combine text area projects and structured project data for the AI prompt
    all_projects_for_ai = processed_projects_text_list + \
        [f"{p['title']}: {p['description']}" for p in st.session_state.project_data if p["title"] or p["description"]]

    # Define prompts for the AI model
    resume_prompt = f"""Generate a professional resume summary based on the following information:
Skills: {', '.join(processed_skills)}
Projects: {'; '.join(all_projects_for_ai)}
Experience: {'; '.join(processed_experience)}
Resume Template Style: {resume_template}
Tone: {tone}
Format the output using markdown or basic HTML for structure (e.g., headings, bullet points).
"""

    cover_letter_prompt = f"""Write a compelling cover letter introduction and body based on the following information:
Skills: {', '.join(processed_skills)}
Projects: {'; '.join(all_projects_for_ai)}
Experience: {'; '.join(processed_experience)}
Desired Tone: {tone}
Format the output using markdown or basic HTML for structure (e.g., paragraphs).
"""

    portfolio_prompt = f"""Create a concise portfolio summary highlighting key projects and skills based on the following information:
Skills: {', '.join(processed_skills)}
Experience: {'; '.join(processed_experience)}
Projects:
{'; '.join(all_projects_for_ai)}
Desired Tone: {tone}
Format the output using markdown or basic HTML for structure (e.g., headings, lists).
"""

    # Generate content using the AI model
    with st.spinner("Generating content..."):
        generated_resume = generate_text(
            resume_prompt, max_tokens_override=max_tokens, mock=use_mock)
        generated_cover_letter = generate_text(
            cover_letter_prompt, max_tokens_override=max_tokens, mock=use_mock)
        generated_portfolio = generate_text(
            portfolio_prompt, max_tokens_override=max_tokens, mock=use_mock)

    # Update the output sections using the containers created earlier
    if generated_resume:
        styled_resume = f'<div class="generated-content resume-section"><h3>Generated Resume</h3>{generated_resume}</div>'
        resume_output_container.markdown(styled_resume, unsafe_allow_html=True)
        # Add download button for resume (text format for simplicity initially)
        st.download_button(
            label="Download Resume (Text)",
            data=generated_resume,
            file_name="resume.txt",
            mime="text/plain"
        )
        # Placeholder for PDF/DOCX download
        st.info("More download options (PDF, DOCX) coming soon!")

    if generated_cover_letter:
        styled_cover_letter = f'<div class="generated-content cover-letter-section"><h3>Generated Cover Letter</h3>{generated_cover_letter}</div>'
        cover_letter_output_container.markdown(
            styled_cover_letter, unsafe_allow_html=True)
        # Add download button for cover letter (text format for simplicity initially)
        st.download_button(
            label="Download Cover Letter (Text)",
            data=generated_cover_letter,
            file_name="cover_letter.txt",
            mime="text/plain"
        )
        # Placeholder for PDF/DOCX download
        st.info("More download options (PDF, DOCX) coming soon!")

    if generated_portfolio:
        styled_portfolio = f'<div class="generated-content portfolio-section"><h3>Generated Portfolio Summary</h3>{generated_portfolio}</div>'
        portfolio_output_container.markdown(
            styled_portfolio, unsafe_allow_html=True)
        # Placeholder for portfolio share/export options
        st.info("Portfolio share and export options coming soon!")
