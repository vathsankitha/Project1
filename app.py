
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

# Function to generate text using the OpenAI API


def generate_text(prompt):
    """Generates text using the OpenAI API."""
    openai_api_key = os.getenv(
        "OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")
    if not openai_api_key:
        st.error(
            "OpenAI API key not found. Please set the OPENAI_API_KEY environment variable or Streamlit secret.")
        return None

    try:
        # Configure the OpenAI package with the API key and call the ChatCompletion API
        openai.api_key = openai_api_key
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
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
        generated_resume = generate_text(resume_prompt)
        generated_cover_letter = generate_text(cover_letter_prompt)
        generated_portfolio = generate_text(portfolio_prompt)

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
