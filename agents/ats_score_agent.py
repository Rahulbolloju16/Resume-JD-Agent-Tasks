import pandas as pd
from google.colab import files
from io import BytesIO
import docx
import spacy

# Install required libraries
try:
    import spacy
except ImportError:
    print("Installing spaCy...")
    !pip install spacy

try:
    import docx
except ImportError:
    print("Installing python-docx...")
    !pip install python-docx

# Load spaCy and download the model if not already done
try:
    # Try loading the model to see if it's downloaded
    nlp = spacy.load("en_core_web_sm")
    print("spaCy English language model loaded.")
except:
    # If loading fails, download and then load
    print("Downloading spaCy English language model...")
    !python -m spacy download en_core_web_sm
    import spacy
    nlp = spacy.load("en_core_web_sm")
    print("spaCy English language model downloaded and loaded.")


def score_resume(resume, jd_keywords):
    resume_text = resume.get("text", "").lower()
    # Use extracted_entities if available, otherwise fall back to parsed_sections (or an empty list)
    extracted_entities = resume.get("extracted_entities", [])
    parsed_sections = [s.lower() for s in resume.get("parsed_sections", [])]


    score = 0
    suggestions = []

    # --- 1. Keyword Matching (Adjusted Weight: 40%)
    # Combine simple text matching with entity-based matching
    matched_keywords = set()
    missing_keywords = set(jd_keywords)

    # Check keywords against raw text
    for kw in jd_keywords:
        if kw.lower() in resume_text:
            matched_keywords.add(kw)

    # Check keywords against extracted entity text
    # Give a slight bonus or separate check for keywords found as specific entity types (e.g., ORG, PRODUCT for skills/companies)
    entity_matched_keywords = set()
    relevant_entity_types = ["ORG", "PRODUCT", "EVENT"] # Consider these as potential skills/experience indicators

    for kw in jd_keywords:
        if kw not in matched_keywords: # Avoid double counting if already matched in text
            for entity in extracted_entities:
                if entity["label"] in relevant_entity_types and kw.lower() in entity["text"].lower():
                     entity_matched_keywords.add(kw)
                     break # Move to the next keyword once matched

    all_matched = matched_keywords.union(entity_matched_keywords)
    missing = list(set(jd_keywords) - all_matched)

    # Calculate keyword score (giving a slightly higher weight to entity matches could be an option,
    # but for simplicity, we'll just count unique matches here)
    keyword_score = (len(all_matched) / len(jd_keywords)) * 40 if jd_keywords else 0

    if keyword_score < 30 and missing: # Lower threshold for suggestion if entity matching helps
        suggestions.append(f"Add missing keywords: {', '.join(missing[:5])}")

    score += keyword_score

    # --- 2. Section Check (Adjusted Weight: 30%)
    required_sections = ["experience", "education", "skills"] # Less focus on 'summary' if using entities
    present_sections = set(parsed_sections)

    # Try to infer sections based on entity types if not explicitly parsed
    # If 'experience' not found in parsed_sections, check for a minimum number of ORG and DATE entities
    inferred_experience = False
    if "experience" not in present_sections:
        org_count = sum(1 for ent in extracted_entities if ent["label"] == "ORG")
        date_count = sum(1 for ent in extracted_entities if ent["label"] == "DATE")
        # Heuristic: Assume 'experience' section is likely present if there are multiple ORG and DATE entities
        if org_count >= 3 and date_count >= 3: # Thresholds can be adjusted
             inferred_experience = True
             if "experience" not in present_sections: # Only add if not already present
                present_sections.add("inferred_experience") # Use a different tag to distinguish inferred

    # If 'education' not found, check for ORG entities (universities) and specific DATE patterns (graduation years)
    inferred_education = False
    if "education" not in present_sections:
         edu_org_count = sum(1 for ent in extracted_entities if ent["label"] == "ORG" and ("university" in ent["text"].lower() or "college" in ent["text"].lower()))
         edu_date_count = sum(1 for ent in extracted_entities if ent["label"] == "DATE" and len(ent["text"]) == 4 and ent["text"].isdigit()) # Simple year check
         if edu_org_count >= 1 or edu_date_count >= 1: # Simple heuristic
             inferred_education = True
             if "education" not in present_sections: # Only add if not already present
                present_sections.add("inferred_education") # Use a different tag

    # 'Skills' section is hard to infer reliably from generic entities, rely on parsed sections or keywords

    # Calculate section score based on required sections being present (parsed or inferred)
    actually_present_or_inferred = [s for s in required_sections if s in present_sections or (s == 'experience' and 'inferred_experience' in present_sections) or (s == 'education' and 'inferred_education' in present_sections)]

    section_score = (len(actually_present_or_inferred) / len(required_sections)) * 30 if required_sections else 0

    if section_score < 30:
        missing_req = [s for s in required_sections if s not in present_sections and not ((s == 'experience' and 'inferred_experience' in present_sections) or (s == 'education' and 'inferred_education' in present_sections))]
        if missing_req:
             suggestions.append(f"Make sure to include sections like: {', '.join([s.capitalize() for s in missing_req])}.")


    score += section_score

    # --- 3. Format Check (Weight: 30%) - Increased weight as it's independent of API
    format_score = 30 # Start with a higher base
    word_count = len(resume_text.split())

    if word_count > 1200:
        format_score -= 10 # Increased penalty
        suggestions.append("Keep your resume under 2 pages (approx. 1000–1200 words).")

    if "lorem ipsum" in resume_text:
        format_score -= 5
        suggestions.append("Remove placeholder text like 'lorem ipsum'.")

    # Add a small bonus for reasonable length (e.g., between 400 and 1200 words)
    if 400 <= word_count <= 1200:
        format_score += 5 # Bonus for good length

    # Ensure format score doesn't go below zero
    format_score = max(0, format_score)


    score += format_score

    # Ensure total score does not exceed 100
    score = min(100, score)


    return {
        "ats_score": round(score, 2),
        "missing_keywords": missing,
        "suggestions": suggestions,
        "matched_keywords": list(all_matched), # Add matched keywords to output
        "inferred_sections": [s for s in present_sections if s.startswith('inferred_')] # Add inferred sections
    }

def extract_resume_info_with_spacy(text_content):
    """
    Analyzes text content using spaCy to extract entities.

    Args:
        text_content (str): The raw text content of the resume.

    Returns:
        dict: A dictionary containing the original text and extracted entities.
    """
    if nlp is None:
        print("spaCy model not loaded. Cannot extract entities.")
        return {"text": text_content, "extracted_entities": []}

    doc = nlp(text_content)

    extracted_entities = []
    # Iterate through the processed document's entities
    for ent in doc.ents:
        # Consider entities that are likely relevant resume information.
        # This is a basic approach; more sophisticated methods exist for resume parsing.
        # Common relevant entity types might include ORG (organizations), GPE (locations),
        # DATE (dates), CARDINAL (numbers, potentially years of experience), PERSON (names).
        # Explicitly looking for skill-related entities is harder without a custom model.
        # For this basic example, we'll capture a few entity types.
        if ent.label_ in ["ORG", "GPE", "DATE", "PERSON", "CARDINAL", "PRODUCT", "EVENT", "WORK_OF_ART", "LAW", "LANGUAGE"]:
            extracted_entities.append({
                "text": ent.text,
                "label": ent.label_
            })

    return {
        "text": text_content,
        "extracted_entities": extracted_entities
    }

# --- Main execution flow ---

# 1. Upload file
print("Please upload your resume file ('.docx' or '.txt')...")
uploaded = files.upload()

if not uploaded:
    print("No file uploaded. Exiting.")
else:
    filename = list(uploaded.keys())[0]
    file_extension = filename.split('.')[-1].lower()
    content = ""

    if file_extension == 'docx':
        try:
            byte_content = BytesIO(uploaded[filename])
            document = docx.Document(byte_content)
            content = "\n".join([paragraph.text for paragraph in document.paragraphs])
        except Exception as e:
            content = f"Error reading .docx file: {e}"
            print(content)
    elif file_extension == 'txt':
        try:
            content = uploaded[filename].decode('utf-8', errors='ignore')
        except Exception as e:
            content = f"Error reading .txt file: {e}"
            print(content)
    else:
        content = "Unsupported file type. Please upload a .docx or .txt file."
        print(content)

    if content and not content.startswith("Error") and not content.startswith("Unsupported"):
        print(f"\nProcessed file: {filename}")
        print("Content preview:")
        print(content[:500]) # Print the first 500 characters as a preview

        # 2. Extract data using spaCy
        print("\nExtracting resume information using spaCy...")
        resume_info_spacy = extract_resume_info_with_spacy(content)

        # Create the resume data dictionary with extracted entities
        resume_data_uploaded = {
            "text": resume_info_spacy["text"],
            "extracted_entities": resume_info_spacy["extracted_entities"],
            "parsed_sections": [] # Placeholder if no explicit parsing done
        }

        # 3. Define job description keywords (replace with actual keywords)
        job_description_keywords_uploaded = ["Python", "Data Analysis", "Machine Learning", "AWS", "SQL", "Communication", "Problem Solving"]
        print(f"\nUsing Job Description Keywords: {', '.join(job_description_keywords_uploaded)}")

        # 4. Score resume
        print("\nCalculating ATS score...")
        ats_results_spacy = score_resume(resume=resume_data_uploaded, jd_keywords=job_description_keywords_uploaded)

        # 5. Display enhanced results
        print("\n--- Resume ATS Score Summary (with spaCy) ---")
        print(f"Overall ATS Score: {ats_results_spacy['ats_score']}")

        print("\nMatched Keywords (including entity-based matches):")
        if ats_results_spacy['matched_keywords']:
            for keyword in ats_results_spacy['matched_keywords']:
                print(f"- {keyword}")
        else:
            print("None")

        print("\nMissing Keywords:")
        if ats_results_spacy['missing_keywords']:
            for keyword in ats_results_spacy['missing_keywords']:
                print(f"- {keyword}")
        else:
            print("None")

        print("\nInferred Sections (from spaCy entities):")
        if ats_results_spacy['inferred_sections']:
            for section in ats_results_spacy['inferred_sections']:
                 print(f"- {section.replace('inferred_', '').capitalize()}") # Remove 'inferred_' prefix
        else:
            print("None inferred")

        print("\nSuggestions for Improvement:")
        if ats_results_spacy['suggestions']:
            for suggestion in ats_results_spacy['suggestions']:
                print(f"- {suggestion}")
        else:
            print("None")
        print("---------------------------------------------")

    else:
        print("\nCould not process the uploaded file.")
