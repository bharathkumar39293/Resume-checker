import pdfplumber
from docx import Document
import os
import re
import spacy

# Load spaCy model
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("Downloading spaCy model 'en_core_web_sm'...")
    os.system("python -m spacy download en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

def extract_text_from_pdf(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text(x_tolerance=1) + "\n"
    return text

def extract_text_from_docx(docx_path):
    doc = Document(docx_path)
    text = ""
    for paragraph in doc.paragraphs:
        text += paragraph.text + "\n"
    return text

def clean_text(text):
    # Remove multiple spaces and newlines
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n+', '\n', text)
    # Basic header/footer removal (can be improved with more advanced heuristics)
    text = re.sub(r'Page \d+ of \d+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\bConfidential\b', '', text, flags=re.IGNORECASE)
    return text.strip()

def extract_name(doc):
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            return ent.text
    return ""

def extract_sections(text):
    sections = {
        "Education": [],
        "Skills": [],
        "Projects": [],
        "Certifications": [],
        "Experience": []
    }

    # Define common section headers (can be expanded)
    section_keywords = {
        "EDUCATION": ["education"],
        "SKILLS": ["skills", "technical skills", "proficiencies"],
        "PROJECTS": ["projects", "portfolio"],
        "CERTIFICATIONS": ["certifications", "awards"],
        "EXPERIENCE": ["experience", "work experience", "professional experience"]
    }

    # Use regex to find sections based on keywords
    current_section = None
    lines = text.split('\n')
    for line in lines:
        line_lower = line.lower()
        found_section = False
        for section_name, keywords in section_keywords.items():
            for keyword in keywords:
                if re.search(r'\b' + re.escape(keyword) + r'\b', line_lower):
                    current_section = section_name
                    found_section = True
                    break
            if found_section:
                break

        if not found_section and current_section:
            if current_section == "EDUCATION":
                sections["Education"].append(line.strip())
            elif current_section == "SKILLS":
                sections["Skills"].append(line.strip())
            elif current_section == "PROJECTS":
                sections["Projects"].append(line.strip())
            elif current_section == "CERTIFICATIONS":
                sections["Certifications"].append(line.strip())
            elif current_section == "EXPERIENCE":
                sections["Experience"].append(line.strip())
    
    # Further cleaning for lists (e.g., splitting skills by comma)
    sections["Skills"] = [skill.strip() for item in sections["Skills"] for skill in item.split(',') if skill.strip()]

    return sections

def parse_resume(file_path):
    file_extension = os.path.splitext(file_path)[1].lower()
    
    if file_extension == '.pdf':
        raw_text = extract_text_from_pdf(file_path)
    elif file_extension == '.docx':
        raw_text = extract_text_from_docx(file_path)
    else:
        raise ValueError("Unsupported file type. Only PDF and DOCX are supported.")
    
    cleaned_text = clean_text(raw_text)

    doc = nlp(cleaned_text)
    
    name = extract_name(doc)
    extracted_sections = extract_sections(cleaned_text)

    parsed_sections = {
        "Name": name,
        "Education": extracted_sections["Education"],
        "Skills": extracted_sections["Skills"],
        "Projects": extracted_sections["Projects"],
        "Certifications": extracted_sections["Certifications"],
        "Experience": extracted_sections["Experience"],
        "RawContent": cleaned_text
    }
    
    return parsed_sections

def parse_job_description(text):
    cleaned_text = clean_text(text)
    doc = nlp(cleaned_text)

    role_title = ""
    must_have_skills = []
    good_to_have_skills = []
    required_qualifications = []

    # Attempt to extract role title - often the first prominent phrase or heading
    # This is a very basic heuristic and can be improved.
    lines = cleaned_text.split('\n')
    if lines:
        role_title_candidate = lines[0].strip()
        if len(role_title_candidate.split()) < 10 and len(role_title_candidate) > 5: # simple heuristic for a title
            role_title = role_title_candidate

    # Keywords for skill categories
    must_have_keywords = ["required skills", "must-have skills", "core skills", "essential skills", "technical requirements", "qualifications", "requirements"]
    good_to_have_keywords = ["bonus skills", "good to have", "nice to have", "preferred skills"]
    qualification_keywords = ["qualifications", "education", "experience"]

    # Simple sectioning based on keywords (can be made more robust)
    current_section = None
    for line in lines:
        line_lower = line.lower()
        if any(keyword in line_lower for keyword in must_have_keywords):
            current_section = "MUST_HAVE_SKILLS"
            continue
        elif any(keyword in line_lower for keyword in good_to_have_keywords):
            current_section = "GOOD_TO_HAVE_SKILLS"
            continue
        elif any(keyword in line_lower for keyword in qualification_keywords):
            current_section = "REQUIRED_QUALIFICATIONS"
            continue
        
        if current_section == "MUST_HAVE_SKILLS":
            # Extract potential skills (simple approach: words starting with a capital letter or tech terms)
            skills_found = [word.strip() for word in re.findall(r'\b[A-Z][a-zA-Z0-9\s#-]+\b', line) if len(word.strip()) > 2]
            must_have_skills.extend(skills_found)
            # Also look for comma separated values
            comma_separated = [s.strip() for s in line.split(',') if s.strip()]
            must_have_skills.extend(comma_separated)
            must_have_skills = list(set(must_have_skills)) # Remove duplicates

        elif current_section == "GOOD_TO_HAVE_SKILLS":
            skills_found = [word.strip() for word in re.findall(r'\b[A-Z][a-zA-Z0-9\s#-]+\b', line) if len(word.strip()) > 2]
            good_to_have_skills.extend(skills_found)
            comma_separated = [s.strip() for s in line.split(',') if s.strip()]
            good_to_have_skills.extend(comma_separated)
            good_to_have_skills = list(set(good_to_have_skills)) # Remove duplicates

        elif current_section == "REQUIRED_QUALIFICATIONS":
            if line.strip():
                required_qualifications.append(line.strip())

    # Further refinement for skills - using spaCy for better entity recognition
    # This part can be significantly improved with a custom skill matcher or a pre-trained model.
    for sent in doc.sents:
        for ent in sent.ents:
            if ent.label_ == "ORG" or ent.label_ == "PRODUCT" or ent.label_ == "LANGUAGE": # Example entity types for skills
                # Simple check to avoid adding company names as skills directly
                if ent.text.lower() not in [o.text.lower() for o in doc.ents if o.label_ == "ORG"]:
                    if current_section == "MUST_HAVE_SKILLS" and ent.text not in must_have_skills:
                        must_have_skills.append(ent.text)
                    elif current_section == "GOOD_TO_HAVE_SKILLS" and ent.text not in good_to_have_skills:
                        good_to_have_skills.append(ent.text)

    parsed_jd = {
        "RoleTitle": role_title,
        "MustHaveSkills": must_have_skills,
        "GoodToHaveSkills": good_to_have_skills,
        "RequiredQualifications": required_qualifications,
        "RawContent": cleaned_text
    }

    return parsed_jd

if __name__ == '__main__':
    print("Parser script is intended to be imported and used by other modules (e.g., Flask app).")
    print("No direct execution test for parser.py is performed here after Flask integration.")
