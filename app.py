import streamlit as st
import openai
import os
import sys
# --- Replaced ReportLab imports with xhtml2pdf imports ---
from xhtml2pdf import pisa
from io import BytesIO

# Define constants for styling (used within the generated HTML/CSS)
BLUE = '#007bff'
DARK_BLUE = '#0056b3'
TEAL = '#00cba9'
GREY = '#646464'

# --- Configuration and Utility Functions ---

# If this file is executed directly... (Existing code block)
try:
    from streamlit.runtime.scriptrunner import script_run_context as _script_ctx
    if _script_ctx.get_script_run_ctx() is None:
        print("This is a Streamlit app. Start it with: streamlit run app.py")
        sys.exit(0)
except Exception:
    pass

# Small utility: validate the OpenAI API key


def validate_api_key():
    """Validate the configured OpenAI API key using a low-cost API call.
    Returns (ok: bool, message: str).
    """
    # Key fetching logic remains the same
    key = os.getenv("OPENAI_API_KEY")
    try:
        if not key and hasattr(st, "secrets"):
            key = st.secrets.get("OPENAI_API_KEY")
    except Exception:
        pass

    if not key:
        return False, "No API key found in environment or Streamlit secrets."

    try:
        # Prioritize new SDK
        from openai import OpenAI
        client = OpenAI(api_key=key)
        client.models.list()
        return True, "OpenAI API key is valid (new client)."
    except Exception as e:
        # Fallback to old SDK
        try:
            openai.api_key = key
            openai.Model.list()
            return True, "OpenAI API key is valid (old client)."
        except Exception as e_old:
            msg = f"Validation failed. Error: {e if 'openai' in str(e) else e_old}"
            return False, msg

# Function to generate text using the OpenAI API


def generate_text(prompt, max_tokens_override=None, mock=False):
    """Generates text using the OpenAI API."""
    if mock:
        return f"(MOCK) Generated content for prompt preview. Prompt starts: {prompt[:120]}..."

    if max_tokens_override is None:
        max_tokens_override = 1000

    openai_api_key = os.getenv("OPENAI_API_KEY")
    try:
        if not openai_api_key and hasattr(st, "secrets"):
            openai_api_key = st.secrets.get("OPENAI_API_KEY")
    except Exception:
        openai_api_key = openai_api_key

    if not openai_api_key:
        st.error(
            "OpenAI API key not found. Please add your key as an environment variable or in Streamlit secrets.")
        # Removed detailed key debugging instructions to keep code focused and clean
        return None

    try:
        # API call logic remains the same (handles both old and new SDK)
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
            openai.api_key = openai_api_key
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens_override,
                n=1,
                stop=None,
                temperature=0.7,
            )

        if response and getattr(response, "choices", None):
            choice = response.choices[0]
            content = None
            if isinstance(choice, dict):
                content = choice.get("message", {}).get("content")
            else:
                content = getattr(
                    getattr(choice, "message", None), "content", None)

            if content:
                return content.strip()

        st.error("OpenAI returned an unexpected response format.")
        return None
    except Exception as e:
        st.error(f"Error generating text: {e}")
        return None


# PDF Generator using xhtml2pdf (HTML to PDF)
def create_full_pdf(user_info, generated_content, structured_projects):
    """
    Generates a comprehensive PDF byte stream by converting styled HTML using xhtml2pdf.
    This method is highly compatible and avoids native library issues.
    """

    # --- CSS Styles (Embedded in HTML) ---
    css = f"""
    @page {{
        size: letter;
        margin: 0.75in;
    }}
    body {{ 
        font-family: Helvetica, sans-serif; 
        font-size: 11pt; 
        color: #2c3e50; 
        line-height: 1.4;
    }}
    h1 {{ 
        color: {BLUE}; 
        font-size: 18pt; 
        text-align: center; 
        margin-bottom: 5pt; 
    }}
    .contact {{ 
        font-size: 10pt; 
        color: {GREY}; 
        text-align: center; 
        margin-bottom: 15pt; 
    }}
    .separator {{ 
        border-bottom: 2px solid {BLUE}; 
        margin-top: 10pt; 
        margin-bottom: 10pt; 
    }}
    .section-title {{
        color: {DARK_BLUE};
        font-size: 14pt;
        font-weight: bold;
        margin-top: 15pt;
        margin-bottom: 5pt;
        border-bottom: 1px solid #ddd;
        padding-bottom: 3pt;
    }}
    .project-title {{
        color: {TEAL};
        font-size: 12pt;
        font-weight: bold;
        margin-top: 10pt;
    }}
    .project-link {{ font-style: italic; color: #0000ff; font-size: 10pt; }}
    /* Important for Unicode bullet points and standard text */
    ul {{ list-style-type: disc; margin-left: 15pt; margin-top: 5pt; padding-left: 0; }}
    ul li {{ margin-bottom: 5px; }}
    p {{ margin-top: 0; margin-bottom: 5pt; }}
    """

    # --- Header Construction ---
    header_html = f"""
    <h1>{user_info['name']}</h1>
    <p class="contact">{user_info['contact']}</p>
    <div class="separator"></div>
    """

    # --- Content Assembly ---
    content_html = ""

    # Helper to convert AI markdown content (which uses *, -, and # for headings/lists) to HTML
    def markdown_to_html(markdown_text):
        parts = []
        in_list = False

        for line in markdown_text.split('\n'):
            line = line.strip()
            if not line:
                if in_list:
                    parts.append('</ul>')
                    in_list = False
                continue

            if line.startswith('*') or line.startswith('-'):
                item_text = line.lstrip('*- ').strip()
                if not in_list:
                    parts.append('<ul>')
                    in_list = True
                parts.append(f'<li>{item_text}</li>')
            elif line.startswith('###'):
                if in_list:
                    parts.append('</ul>')
                    in_list = False
                parts.append(
                    f'<div class="project-title">{line.lstrip("# ").strip()}</div>')
            elif line.startswith('##') or line.startswith('#'):
                if in_list:
                    parts.append('</ul>')
                    in_list = False
                # Use standard section title style defined in CSS
                parts.append(
                    f'<div class="section-title">{line.lstrip("# ").strip()}</div>')
            else:
                if in_list:
                    parts.append('</ul>')
                    in_list = False
                parts.append(f'<p>{line}</p>')

        if in_list:
            parts.append('</ul>')

        return '\n'.join(parts)

    # 1. AI Generated Portfolio Summary (HTML from markdown)
    content_html += '<div class="section-title" style="margin-top: 5pt;">AI-Generated Portfolio Summary</div>'
    if generated_content.get('portfolio'):
        content_html += markdown_to_html(generated_content['portfolio'])

    # 2. Core Experience and Skills (Raw User Input)
    content_html += '<div class="section-title">Core Skills & Experience Summary</div>'

    # Skills
    skills_list = ', '.join(user_info["skills"])
    content_html += f'<p><b>Skills:</b> {skills_list}</p>'

    # Experience
    content_html += '<p><b>Experience:</b></p>'
    experience_list_items = "".join([
        f'<li>{exp}</li>' for exp in user_info['experience']
    ])
    if experience_list_items:
        content_html += f'<ul class="experience-list">{experience_list_items}</ul>'

    # 3. Detailed Portfolio Projects (Structured Data)
    if structured_projects:
        content_html += '<div class="section-title">Detailed Projects</div>'
        for p in structured_projects:
            if p['title']:
                content_html += f'<div class="project-title">{p["title"]}</div>'

                # Link
                if p['link']:
                    content_html += f'<p class="project-link">Link: <a href="{p["link"]}">{p["link"]}</a></p>'

                # Description
                if p['description']:
                    content_html += f'<p>{p["description"]}</p>'

    # 4. AI Generated Resume Summary (as an appendix)
    if generated_content.get('resume'):
        content_html += '<div class="section-title">AI-Generated Resume Highlights</div>'
        content_html += markdown_to_html(generated_content['resume'])

    # 5. Full HTML document assembly
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{user_info['name']} Portfolio</title>
        <!-- Explicitly declare UTF-8 charset for robust Unicode handling -->
        <meta charset="UTF-8"/>
        <style>{css}</style>
    </head>
    <body>
        {header_html}
        {content_html}
    </body>
    </html>
    """

    # 6. Convert HTML to PDF using pisa
    buffer = BytesIO()
    try:
        # Create a PDF object from the HTML string
        pisa_status = pisa.CreatePDF(
            full_html,
            dest=buffer
        )

        if pisa_status.err:
            st.error(
                "Error creating PDF using xhtml2pdf. Check the HTML content or library installation.")
            return BytesIO()

        buffer.seek(0)
        return buffer
    except ImportError:
        st.error(
            "The `xhtml2pdf` library is required but not installed. Please run: `pip install xhtml2pdf`")
        return BytesIO()
    except Exception as e:
        st.error(
            f"An unexpected error occurred during PDF generation (xhtml2pdf): {e}")
        return BytesIO()


# --- CSS Styling (Enhanced) ---
css_style = """
<style>
/* 1. Global/Body Styles */
body {
    font-family: 'Inter', sans-serif;
    color: #2c3e50; /* Darker text */
    background-color: #f8f9fa;
}

/* 2. Container Styling */
.stApp {
    max-width: 1000px;
    padding-top: 2rem;
    padding-bottom: 2rem;
}

/* 3. Headers */
h1 {
    color: #007bff; /* Primary blue for main header */
    text-align: center;
    border-bottom: 3px solid #007bff;
    padding-bottom: 10px;
    margin-bottom: 20px;
}
h2 {
    color: #0056b3; /* Darker blue for subheaders */
    border-left: 5px solid #00cba9; /* Teal accent */
    padding-left: 10px;
    margin-top: 15px;
}

/* 4. Generated Content Display */
.generated-content {
    background-color: #ffffff;
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    margin-bottom: 20px;
}

.resume-section { border: 1px solid #e0f7fa; }
.cover-letter-section { border: 1px solid #ffe0b2; }
.portfolio-section { border: 1px solid #c8e6c9; }

/* 5. Buttons and Inputs */
.stButton>button {
    background-color: #00cba9; /* Teal button */
    color: white;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: bold;
    transition: background-color 0.3s;
}
.stButton>button:hover {
    background-color: #00a892; /* Darker teal on hover */
}
</style>
"""
st.markdown(css_style, unsafe_allow_html=True)

# --- Streamlit UI Layout ---

st.title("AI-Powered Resume, Cover Letter, and Portfolio Generator 🤖")

# Use st.columns for better input layout
col1, col2 = st.columns(2)

with col1:
    st.subheader("Personal Information")
    user_name = st.text_input(
        "Name (for letters/resumes)", "John Doe", key="user_name")
    user_contact = st.text_input(
        "Email/Phone/Location", "john.doe@example.com | (555) 123-4567", key="user_contact")

st.subheader("Enter Your Core Data")
skills = st.text_area("Skills (comma-separated)",
                      "Python, Data Analysis, Machine Learning, Streamlit, SQL", key="user_skills")
projects_text = st.text_area("Projects (list each *brief* project name on a new line)",
                             "AI Job Generator, eCommerce Dashboard, Personal Blog", key="user_projects_text")
experience = st.text_area("Experience (list each job/role on a new line)",
                          "Senior Data Scientist at TechCorp (2020-Present), ML Intern at Innovate Solutions (2019)", key="user_experience")

st.subheader("Customization Options")
col_opt1, col_opt2, col_opt3 = st.columns(3)

with col_opt1:
    resume_template = st.selectbox("Select Resume Template", [
                                   "Classic", "Modern", "Creative"], key="resume_template")
with col_opt2:
    tone = st.radio("Preferred Tone", [
                    "Professional", "Creative", "Enthusiastic"], key="tone")
with col_opt3:
    max_tokens = st.number_input(
        "Max tokens", min_value=50, max_value=2000, value=1000, step=50, help="Controls the length of AI output.", key="max_tokens")

# Workaround controls when OpenAI quota is exhausted
use_mock = st.checkbox(
    "Use mock responses (no OpenAI calls)", value=False, key="use_mock")
if use_mock:
    st.warning("Mock mode is ON. Content will be placeholder text.")

# API Key Validation Button (outside the main flow)
if st.button("Validate OpenAI API Key 🔑"):
    with st.spinner("Validating API key..."):
        ok, message = validate_api_key()
        if ok:
            st.success(message)
        else:
            st.error(message)

st.divider()

# --- Portfolio Projects Tab (for structured data) ---

# Use tabs to separate complex input from output
tabs = st.tabs(["**Portfolio Project Details** 🖼️", "**Generated Content** ✨"])

# Initialize session state for project data
if 'project_data' not in st.session_state:
    st.session_state.project_data = []

with tabs[0]:
    st.subheader("Detailed Portfolio Projects (Optional)")
    st.info("Use this section to add structured details (links) for a comprehensive PDF portfolio.")

    num_projects = st.number_input("Number of Detailed Projects", min_value=0, value=len(
        st.session_state.project_data), step=1, key="num_projects")

    # Dynamic list management
    if num_projects > len(st.session_state.project_data):
        for _ in range(num_projects - len(st.session_state.project_data)):
            st.session_state.project_data.append(
                {"title": "", "description": "", "link": "", "image": None})
    elif num_projects < len(st.session_state.project_data):
        st.session_state.project_data = st.session_state.project_data[:num_projects]

    for i in range(num_projects):
        # Use a unique key for each file uploader based on its index
        image_key = f"project_image_{i}_uploader"
        # Preserve existing image if possible
        current_image = st.session_state.project_data[i].get("image")

        with st.container(border=True):  # Use a container for visual grouping
            st.markdown(f"#### Project {i+1}")
            st.session_state.project_data[i]["title"] = st.text_input(
                f"Project {i+1} Title", value=st.session_state.project_data[i]["title"], key=f"project_title_{i}")
            st.session_state.project_data[i]["description"] = st.text_area(
                f"Project {i+1} Description", value=st.session_state.project_data[i]["description"], key=f"project_description_{i}")
            st.session_state.project_data[i]["link"] = st.text_input(
                f"Project {i+1} Link (URL)", value=st.session_state.project_data[i]["link"], key=f"project_link_{i}")

            # File Uploader
            uploaded_file = st.file_uploader(
                f"Upload Image for Project {i+1} (Preview Only)", type=["png", "jpg", "jpeg"], key=image_key)

            # Update session state with the new uploaded file or keep the old one
            if uploaded_file is not None:
                st.session_state.project_data[i]["image"] = uploaded_file
            elif current_image is None and uploaded_file is None:
                # Ensure 'image' key is handled if user removes it or if it was never set
                st.session_state.project_data[i]["image"] = None

            # Preview uploaded image
            if st.session_state.project_data[i]["image"] is not None:
                st.image(st.session_state.project_data[i]["image"],
                         caption=f"Image preview for {st.session_state.project_data[i]['title'] or f'Project {i+1}'}", width=250)
                st.caption(
                    "Note: Images are *not* included in the PDF download (due to xhtml2pdf complexity) but are here for reference.")

# --- State Management for Generated Content ---
if 'generated_resume' not in st.session_state:
    st.session_state.generated_resume = None
if 'generated_cover_letter' not in st.session_state:
    st.session_state.generated_cover_letter = None
if 'generated_portfolio' not in st.session_state:
    st.session_state.generated_portfolio = None

# --- Generate Button and Output Tab ---
with tabs[1]:
    generate_button = st.button("Generate Content 🚀", type="primary")

    # Containers for generated output (will be filled after generation)
    resume_output_container = st.empty()
    cover_letter_output_container = st.empty()
    portfolio_output_container = st.empty()

    if generate_button:
        # 1. Process Input Data
        user_skills = st.session_state.user_skills
        user_projects_text = st.session_state.user_projects_text
        user_experience = st.session_state.user_experience

        processed_skills = [skill.strip()
                            for skill in user_skills.split(',') if skill.strip()]
        processed_projects_text_list = [
            project.strip() for project in user_projects_text.split('\n') if project.strip()]
        processed_experience = [
            exp.strip() for exp in user_experience.split('\n') if exp.strip()]

        # Include structured project details for AI context
        all_projects_for_ai = processed_projects_text_list + \
            [f"{p['title']}: {p['description']}" for p in st.session_state.project_data if p["title"] or p["description"]]

        if not all_projects_for_ai and not processed_skills and not processed_experience:
            st.warning(
                "Please enter some skills, experience, or projects before generating content.")
        else:
            # 2. Define Prompts (Same as before)
            resume_prompt = f"""Generate a professional resume summary and 3-5 key bullet points for the experience section based on:
Skills: {', '.join(processed_skills)}
Projects: {'; '.join(all_projects_for_ai)}
Experience: {'; '.join(processed_experience)}
Template: {st.session_state.resume_template}. Tone: {st.session_state.tone}.
Format the output using markdown headings and bullet points.
"""
            cover_letter_prompt = f"""Write a compelling cover letter introduction and 3 core paragraphs (targeting an unspecified but relevant job) based on:
Skills: {', '.join(processed_skills)}. Projects: {'; '.join(all_projects_for_ai)}. Experience: {'; '.join(processed_experience)}.
Desired Tone: {st.session_state.tone}. Start with a placeholder greeting (e.g., Dear Hiring Manager,).
Format the output using markdown paragraphs.
"""
            portfolio_prompt = f"""Create a concise portfolio summary (about 100 words) and a list of 3 featured project highlights based on:
Skills: {', '.join(processed_skills)}. Experience: {'; '.join(processed_experience)}. Projects: {'; '.join(all_projects_for_ai)}.
Desired Tone: {st.session_state.tone}.
Format the output using markdown headings and lists.
"""

            # 3. Generate Content
            with st.spinner("Generating content..."):
                st.session_state.generated_resume = generate_text(
                    resume_prompt, max_tokens_override=st.session_state.max_tokens, mock=st.session_state.use_mock)
                st.session_state.generated_cover_letter = generate_text(
                    cover_letter_prompt, max_tokens_override=st.session_state.max_tokens, mock=st.session_state.use_mock)
                st.session_state.generated_portfolio = generate_text(
                    portfolio_prompt, max_tokens_override=st.session_state.max_tokens, mock=st.session_state.use_mock)

            # 4. Display Feedback
            if st.session_state.generated_resume and st.session_state.generated_cover_letter and st.session_state.generated_portfolio:
                st.balloons()
                st.toast('Content Generated Successfully!', icon='🎉')

    # --- Display Content and Download Buttons (Executed on every run) ---
    st.subheader("Generated Content")

    # Check if content exists (either generated or from session state after refresh)
    if st.session_state.generated_resume:
        styled_resume = f'<div class="generated-content resume-section"><h3>Generated Resume</h3>{st.session_state.generated_resume}</div>'
        resume_output_container.markdown(styled_resume, unsafe_allow_html=True)
        st.download_button(
            label="Download Resume (Text)",
            data=st.session_state.generated_resume,
            file_name="resume.txt",
            mime="text/plain",
            key="download_resume"
        )

    if st.session_state.generated_cover_letter:
        styled_cover_letter = f'<div class="generated-content cover-letter-section"><h3>Generated Cover Letter</h3>{st.session_state.generated_cover_letter}</div>'
        cover_letter_output_container.markdown(
            styled_cover_letter, unsafe_allow_html=True)
        st.download_button(
            label="Download Cover Letter (Text)",
            data=st.session_state.generated_cover_letter,
            file_name="cover_letter.txt",
            mime="text/plain",
            key="download_cover_letter"
        )

    if st.session_state.generated_portfolio:
        styled_portfolio = f'<div class="generated-content portfolio-section"><h3>Generated Portfolio Summary</h3>{st.session_state.generated_portfolio}</div>'
        portfolio_output_container.markdown(
            styled_portfolio, unsafe_allow_html=True)

        # --- FULL PDF DOWNLOAD OPTION ---

        # 1. Prepare Data for PDF Function
        pdf_user_info = {
            'name': st.session_state.user_name,
            'contact': st.session_state.user_contact,
            # Processed skills/experience are needed for the PDF
            'skills': [skill.strip() for skill in st.session_state.user_skills.split(',') if skill.strip()],
            'experience': [exp.strip() for exp in st.session_state.user_experience.split('\n') if exp.strip()]
        }
        pdf_generated_content = {
            'portfolio': st.session_state.generated_portfolio,
            'resume': st.session_state.generated_resume
        }

        # Filter project data to only include text/link info
        pdf_structured_projects = [
            {'title': p['title'], 'description': p['description'],
                'link': p['link']}
            for p in st.session_state.project_data if p['title']
        ]

        # 2. Generate the PDF
        pdf_data = create_full_pdf(
            pdf_user_info, pdf_generated_content, pdf_structured_projects)

        # 3. Create the Download Button
        st.download_button(
            label="Download COMPLETE Portfolio (PDF) 📥",
            data=pdf_data,
            file_name=f"{st.session_state.user_name.replace(' ', '_')}_Full_Portfolio.pdf",
            mime="application/pdf",
            key="download_full_portfolio_pdf"
        )

        st.info("The generated PDF is styled professionally and includes your core data, detailed projects, and all AI-generated text.")

