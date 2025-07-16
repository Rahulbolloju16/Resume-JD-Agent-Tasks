# ats_score_agent.py

def score_resume(resume, jd_keywords):
    resume_text = resume.get("text", "").lower()
    parsed_sections = [s.lower() for s in resume.get("parsed_sections", [])]
    
    score = 0
    suggestions = []

    # --- 1. Keyword Matching (50%)
    matched = [kw for kw in jd_keywords if kw.lower() in resume_text]
    missing = list(set(jd_keywords) - set(matched))
    keyword_score = (len(matched) / len(jd_keywords)) * 50 if jd_keywords else 0

    if keyword_score < 40:
        suggestions.append(f"Add missing keywords: {', '.join(missing[:5])}")

    score += keyword_score

    # --- 2. Section Check (25%)
    required_sections = ["summary", "experience", "education", "skills"]
    present = [s for s in required_sections if s in parsed_sections]
    section_score = (len(present) / len(required_sections)) * 25
    if section_score < 25:
        suggestions.append("Make sure to include sections like Summary, Experience, Education, and Skills.")
    
    score += section_score

    # --- 3. Format Check (25%)
    format_score = 25
    if len(resume_text.split()) > 1200:
        format_score -= 5
        suggestions.append("Keep your resume under 2 pages (approx. 1000–1200 words).")

    if "lorem ipsum" in resume_text:
        format_score -= 5
        suggestions.append("Remove placeholder text like 'lorem ipsum'.")

    score += format_score

    return {
        "ats_score": round(score, 2),
        "missing_keywords": missing,
        "suggestions": suggestions
    }
