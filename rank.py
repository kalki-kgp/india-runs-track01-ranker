#!/usr/bin/env python3
"""
Intelligent Candidate Ranking System for Redrob Hackathon
Senior AI Engineer — Founding Team at Redrob AI

Multi-stage scoring: honeypot detection, title/career relevance,
skill-fit analysis, behavioral signals, experience, location, education.
"""

import argparse
import csv
import json
import math
import re
import sys
from datetime import date, datetime
from typing import Any

REFERENCE_DATE = date(2026, 6, 1)

# Real-world founding years for companies appearing in the dataset.
# The spec's honeypot type 1 is "N years of experience at a company founded
# fewer than N years ago" — a tenure that starts before the company existed
# is structurally impossible. Only unambiguous, well-known founding years
# are listed to avoid false positives.
COMPANY_FOUNDED = {
    "Sarvam AI": 2023,
    "Krutrim": 2023,
    "Glance": 2019,
    "Rephrase.ai": 2019,
    "CRED": 2018,
}

# ─────────────────────────────────────────────────────────────────────
# Skill taxonomies — derived from the JD requirements
# ─────────────────────────────────────────────────────────────────────

RETRIEVAL_SEARCH_SKILLS = {
    "Embeddings", "FAISS", "Pinecone", "Weaviate", "Qdrant", "Milvus",
    "OpenSearch", "Elasticsearch", "Vector Search", "Semantic Search",
    "Information Retrieval", "Information Retrieval Systems",
    "Ranking Systems", "Search & Discovery", "Search Backend",
    "Search Infrastructure", "Sentence Transformers", "Text Encoders",
    "Vector Representations", "BM25", "Content Matching",
    "Indexing Algorithms", "Learning to Rank", "RAG", "pgvector",
}

ML_CORE_SKILLS = {
    "Python", "PyTorch", "TensorFlow", "Deep Learning",
    "Machine Learning", "NLP", "Natural Language Processing",
    "Hugging Face Transformers", "scikit-learn", "Feature Engineering",
    "Statistical Modeling",
}

LLM_FINETUNING_SKILLS = {
    "Fine-tuning LLMs", "LoRA", "QLoRA", "PEFT", "LLMs",
    "LangChain", "LlamaIndex", "Prompt Engineering",
    "Model Adaptation", "Haystack",
}

ML_ENGINEERING_SKILLS = {
    "MLOps", "MLflow", "BentoML", "Weights & Biases", "Kubeflow",
    "Docker", "Data Pipelines", "Spark", "Airflow",
    "Workflow Orchestration", "Open-source ML libraries",
    "Data Science", "Forecasting", "Time Series",
    "Recommendation Systems", "Reinforcement Learning",
}

INFRA_SKILLS = {
    "AWS", "GCP", "Azure", "Kubernetes", "gRPC", "FastAPI",
    "Microservices", "Redis", "PostgreSQL", "MongoDB", "Kafka",
    "Databricks", "BigQuery", "Snowflake", "Terraform", "CI/CD",
    "Hadoop", "Apache Beam", "Apache Flink", "ETL",
}

CV_SPEECH_SKILLS = {
    "Computer Vision", "Image Classification", "Object Detection",
    "GANs", "CNN", "YOLO", "OpenCV", "Diffusion Models",
    "Speech Recognition", "TTS", "ASR", "Document Processing",
}

IRRELEVANT_SKILLS = {
    "Excel", "PowerPoint", "Photoshop", "Figma", "Illustrator",
    "Marketing", "Sales", "SEO", "Content Writing", "Accounting",
    "Tally", "Salesforce CRM", "SAP", "Six Sigma",
    "Project Management", "Scrum", "Agile",
}

# Skills that the JD explicitly mentions as must-haves or strong signals
JD_CORE_SKILLS = RETRIEVAL_SEARCH_SKILLS | {
    "Python", "PyTorch", "NLP", "Natural Language Processing",
    "Deep Learning", "Machine Learning", "Hugging Face Transformers",
    "Recommendation Systems",
}

# ─────────────────────────────────────────────────────────────────────
# Title tier mapping — career trajectory relevance
# ─────────────────────────────────────────────────────────────────────

TITLE_TIERS = {
    # Tier 1: Direct match — these roles do exactly what the JD describes
    "Senior AI Engineer": 1.0,
    "Lead AI Engineer": 1.0,
    "AI Engineer": 0.95,
    "Search Engineer": 1.0,
    "Recommendation Systems Engineer": 1.0,
    "Senior NLP Engineer": 0.98,
    "NLP Engineer": 0.95,
    "Applied ML Engineer": 0.95,
    "Senior Applied Scientist": 0.93,
    "Staff Machine Learning Engineer": 0.95,
    "Senior Machine Learning Engineer": 0.95,
    "Machine Learning Engineer": 0.92,
    "Senior Software Engineer (ML)": 0.90,
    "AI Specialist": 0.88,
    "AI Research Engineer": 0.82,

    # Tier 2: Strong adjacency — ML/data roles that could transition
    "ML Engineer": 0.85,
    "Junior ML Engineer": 0.70,
    "Senior Data Scientist": 0.80,
    "Data Scientist": 0.75,
    "Computer Vision Engineer": 0.65,

    # Tier 3: Adjacent technical — relevant if career shows ML work
    "Senior Data Engineer": 0.55,
    "Data Engineer": 0.50,
    "Analytics Engineer": 0.50,
    "Senior Software Engineer": 0.50,
    "Backend Engineer": 0.45,
    "Data Analyst": 0.40,

    # Tier 4: General technical — possible but unlikely fit
    "Software Engineer": 0.35,
    "Full Stack Developer": 0.25,
    "Cloud Engineer": 0.20,
    "DevOps Engineer": 0.15,
    "Java Developer": 0.10,
    ".NET Developer": 0.05,
    "Frontend Engineer": 0.05,
    "QA Engineer": 0.05,
    "Mobile Developer": 0.05,

    # Tier 5: Irrelevant — the keyword-stuffer traps
    "HR Manager": 0.0,
    "Accountant": 0.0,
    "Graphic Designer": 0.0,
    "Content Writer": 0.0,
    "Sales Executive": 0.0,
    "Marketing Manager": 0.0,
    "Customer Support": 0.0,
    "Operations Manager": 0.0,
    "Mechanical Engineer": 0.0,
    "Civil Engineer": 0.0,
    "Project Manager": 0.0,
}

CONSULTING_FIRMS = {
    "tcs", "tata consultancy services", "infosys", "wipro",
    "accenture", "cognizant", "capgemini", "hcl",
    "tech mahindra", "mphasis",
}

PRODUCT_COMPANIES = {
    "swiggy", "zomato", "flipkart", "razorpay", "cred",
    "meesho", "nykaa", "inmobi", "byju's", "policybazaar",
    "ola", "zoho", "freshworks", "paytm", "phonepe",
    "google", "meta", "microsoft", "amazon", "apple",
    "uber", "twitter", "linkedin", "netflix", "spotify",
    "stripe", "airbnb", "slack", "dropbox", "atlassian",
    "mad street den", "yellow.ai", "aganitha",
    "adobe", "salesforce",
    "sarvam ai", "krutrim", "observe.ai", "rephrase.ai", "niramai",
    "saarthi.ai", "wysa", "verloop.io", "haptik", "glance", "locobuzz",
}

AI_INDUSTRIES = {
    "ai/ml", "artificial intelligence", "machine learning",
    "data science", "analytics",
    "healthtech ai", "conversational ai", "voice ai", "ai services",
}

PRODUCT_INDUSTRIES = {
    "food delivery", "e-commerce", "fintech", "edtech",
    "social media", "saas", "cloud", "marketplace",
    "internet", "technology", "software",
}

CAREER_POSITIVE_KEYWORDS = [
    "ranking", "retrieval", "search", "recommendation",
    "embedding", "vector", "nlp", "natural language",
    "deployed", "shipped", "production", "model serving",
    "a/b test", "ndcg", "mrr", "evaluation", "fine-tun",
    "inference", "real-time", "latency", "feature engineer",
    "feature store", "ml pipeline", "transformer",
    "bert", "gpt", "llm", "large language model",
    "re-ranking", "reranking", "hybrid search",
    "semantic", "information retrieval", "bm25",
    "faiss", "pinecone", "weaviate", "qdrant", "milvus",
    "sentence-transform", "learning-to-rank", "learn to rank",
    "xgboost", "lightgbm", "gradient-boost",
    "collaborative filtering", "matrix factorization",
    "knowledge graph", "entity resolution",
    "pytorch", "tensorflow", "hugging face",
    "recruiter", "talent", "hiring", "matching",
]

CAREER_NEGATIVE_KEYWORDS = [
    "photoshop", "illustrator", "figma",
    "accounting", "tally", "gst",
    "content writing", "seo", "blog",
    "mechanical", "civil engineering",
    "sales target", "sales pipeline",
]


# ─────────────────────────────────────────────────────────────────────
# Honeypot detection
# ─────────────────────────────────────────────────────────────────────

def detect_honeypot(candidate: dict) -> bool:
    skills = candidate.get("skills", [])
    career = candidate.get("career_history", [])
    profile = candidate.get("profile", {})

    # Honeypot type 1 (per spec): tenure at a company that starts before the
    # company was founded. NOTE: a high expert-skill count alone is NOT a
    # honeypot signal — the spec's example is expert proficiency with ZERO
    # duration. Corroborated expert skills (real durations/endorsements) mark
    # the strongest genuine candidates and must not be excluded.
    for ch in career:
        founded = COMPANY_FOUNDED.get(ch.get("company"))
        if founded and ch.get("start_date", "9999") < str(founded):
            return True

    expert_zero_duration = sum(
        1 for s in skills
        if s.get("proficiency") == "expert" and s.get("duration_months", 0) == 0
    )
    if expert_zero_duration >= 3:
        return True

    if career:
        earliest_start = min(ch["start_date"] for ch in career)
        earliest_year = int(earliest_start[:4])
        claimed_yoe = profile.get("years_of_experience", 0)
        actual_span = REFERENCE_DATE.year - earliest_year
        if claimed_yoe > actual_span + 2 and claimed_yoe > 5:
            return True

    for ch in career:
        start = ch.get("start_date", "")
        end = ch.get("end_date")
        duration = ch.get("duration_months", 0)
        if start and end and duration > 0:
            try:
                s = datetime.strptime(start, "%Y-%m-%d").date()
                e = datetime.strptime(end, "%Y-%m-%d").date()
                actual_months = (e.year - s.year) * 12 + (e.month - s.month)
                if actual_months > 0 and duration > actual_months * 3 and duration > 60:
                    return True
            except ValueError:
                pass

    high_endorse_zero_duration = sum(
        1 for s in skills
        if s.get("endorsements", 0) > 40 and s.get("duration_months", 0) == 0
    )
    if high_endorse_zero_duration >= 2:
        return True

    return False


# ─────────────────────────────────────────────────────────────────────
# Scoring components
# ─────────────────────────────────────────────────────────────────────

def score_title(candidate: dict) -> float:
    title = candidate["profile"]["current_title"]
    return TITLE_TIERS.get(title, 0.0)


def score_skills(candidate: dict) -> dict:
    skills = candidate.get("skills", [])
    skill_names = {s["name"] for s in skills}

    retrieval_hits = skill_names & RETRIEVAL_SEARCH_SKILLS
    ml_core_hits = skill_names & ML_CORE_SKILLS
    llm_hits = skill_names & LLM_FINETUNING_SKILLS
    ml_eng_hits = skill_names & ML_ENGINEERING_SKILLS
    infra_hits = skill_names & INFRA_SKILLS
    cv_speech_hits = skill_names & CV_SPEECH_SKILLS
    irrelevant_hits = skill_names & IRRELEVANT_SKILLS

    retrieval_score = min(len(retrieval_hits) / 4.0, 1.0)
    ml_core_score = min(len(ml_core_hits) / 3.0, 1.0)
    llm_score = min(len(llm_hits) / 2.0, 1.0)
    ml_eng_score = min(len(ml_eng_hits) / 3.0, 1.0)

    has_nlp_ir = bool(skill_names & {
        "NLP", "Natural Language Processing", "Information Retrieval",
        "Information Retrieval Systems", "Semantic Search",
    })
    cv_only = bool(cv_speech_hits) and not has_nlp_ir
    cv_penalty = -0.15 if cv_only and len(cv_speech_hits) >= 3 else 0.0

    skill_trust = 0.0
    for s in skills:
        if s["name"] in JD_CORE_SKILLS:
            prof_w = {"expert": 1.0, "advanced": 0.8, "intermediate": 0.5, "beginner": 0.2}.get(s["proficiency"], 0.3)
            dur = s.get("duration_months", 0)
            endorse = s.get("endorsements", 0)
            dur_w = min(dur / 36.0, 1.0) if dur > 0 else 0.1
            endorse_w = min(endorse / 20.0, 1.0) if endorse > 0 else 0.1
            skill_trust += prof_w * dur_w * endorse_w
    skill_trust = min(skill_trust / 5.0, 1.0)

    assessment_scores = candidate.get("redrob_signals", {}).get("skill_assessment_scores", {})
    relevant_assessments = {
        k: v for k, v in assessment_scores.items()
        if k in JD_CORE_SKILLS or k in ML_CORE_SKILLS or k in LLM_FINETUNING_SKILLS
    }
    if relevant_assessments:
        avg_assessment = sum(relevant_assessments.values()) / len(relevant_assessments)
        assessment_score = avg_assessment / 100.0
    else:
        assessment_score = 0.0

    combined = (
        retrieval_score * 0.35
        + ml_core_score * 0.25
        + llm_score * 0.15
        + ml_eng_score * 0.10
        + skill_trust * 0.10
        + assessment_score * 0.05
        + cv_penalty
    )

    return {
        "total": max(0.0, min(1.0, combined)),
        "retrieval": retrieval_score,
        "ml_core": ml_core_score,
        "llm": llm_score,
        "retrieval_hits": retrieval_hits,
        "ml_core_hits": ml_core_hits,
    }


def score_career(candidate: dict) -> dict:
    career = candidate.get("career_history", [])
    profile = candidate.get("profile", {})

    if not career:
        return {"total": 0.0, "details": "no career history"}

    companies = [ch["company"].lower() for ch in career]
    industries = [ch.get("industry", "").lower() for ch in career]
    descriptions = " ".join(ch.get("description", "") for ch in career).lower()
    titles_in_career = [ch.get("title", "").lower() for ch in career]

    is_consulting_only = all(
        any(cf in comp for cf in CONSULTING_FIRMS) for comp in companies
    )
    if is_consulting_only:
        return {"total": 0.02, "details": "consulting-only career"}

    consulting_ratio = sum(
        1 for comp in companies if any(cf in comp for cf in CONSULTING_FIRMS)
    ) / len(companies)

    product_count = sum(
        1 for comp in companies if any(pc in comp for pc in PRODUCT_COMPANIES)
    )
    ai_industry_count = sum(
        1 for ind in industries if any(ai in ind for ai in AI_INDUSTRIES)
    )
    product_industry_count = sum(
        1 for ind in industries if any(pi in ind for pi in PRODUCT_INDUSTRIES)
    )

    company_score = min(
        (product_count * 0.3 + ai_industry_count * 0.2 + product_industry_count * 0.1) / 1.0,
        1.0,
    )

    positive_keyword_count = sum(
        1 for kw in CAREER_POSITIVE_KEYWORDS if kw in descriptions
    )
    negative_keyword_count = sum(
        1 for kw in CAREER_NEGATIVE_KEYWORDS if kw in descriptions
    )

    desc_score = min(positive_keyword_count / 8.0, 1.0) - min(negative_keyword_count / 3.0, 0.5)

    ml_title_in_career = any(
        any(t in title for t in [
            "ml", "machine learning", "ai", "data scien",
            "nlp", "search engineer", "recommendation",
            "ranking", "retrieval",
        ])
        for title in titles_in_career
    )
    title_career_bonus = 0.15 if ml_title_in_career else 0.0

    tenure_months = [ch.get("duration_months", 0) for ch in career]
    avg_tenure = sum(tenure_months) / len(tenure_months) if tenure_months else 0
    stability_score = min(avg_tenure / 24.0, 1.0)
    hopper_penalty = -0.1 if avg_tenure < 12 and len(career) >= 3 else 0.0

    combined = (
        company_score * 0.25
        + desc_score * 0.40
        + title_career_bonus
        + stability_score * 0.10
        + hopper_penalty
        - consulting_ratio * 0.15
    )

    return {
        "total": max(0.0, min(1.0, combined)),
        "details": f"product={product_count} ai_ind={ai_industry_count} kw={positive_keyword_count} ml_title={ml_title_in_career}",
    }


def score_experience(candidate: dict) -> float:
    yoe = candidate["profile"].get("years_of_experience", 0)
    if 5 <= yoe <= 9:
        return 1.0
    elif 4 <= yoe < 5:
        return 0.8
    elif 9 < yoe <= 12:
        return 0.85 - (yoe - 9) * 0.05
    elif 3 <= yoe < 4:
        return 0.6
    elif 12 < yoe <= 15:
        return 0.65 - (yoe - 12) * 0.05
    elif 2 <= yoe < 3:
        return 0.3
    else:
        return 0.1


def score_location(candidate: dict) -> float:
    country = candidate["profile"].get("country", "")
    location = candidate["profile"].get("location", "").lower()
    signals = candidate.get("redrob_signals", {})
    willing = signals.get("willing_to_relocate", False)
    work_mode = signals.get("preferred_work_mode", "")

    if country == "India":
        preferred_cities = [
            "pune", "noida", "delhi", "ncr", "gurgaon", "gurugram",
            "hyderabad", "mumbai", "bangalore", "bengaluru", "chennai",
            "kolkata",
        ]
        if any(city in location for city in ["pune", "noida"]):
            return 1.0
        elif any(city in location for city in preferred_cities):
            return 0.90
        else:
            return 0.80 if willing else 0.70
    elif country in ("USA", "UK", "Canada", "Germany", "Singapore", "UAE", "Australia"):
        if willing:
            return 0.40
        elif work_mode == "remote":
            return 0.30
        else:
            return 0.15
    else:
        return 0.10


def score_behavioral(candidate: dict) -> float:
    signals = candidate.get("redrob_signals", {})

    completeness = signals.get("profile_completeness_score", 0) / 100.0

    last_active = signals.get("last_active_date", "")
    if last_active:
        try:
            la = datetime.strptime(last_active, "%Y-%m-%d").date()
            days_inactive = (REFERENCE_DATE - la).days
            if days_inactive <= 7:
                recency = 1.0
            elif days_inactive <= 30:
                recency = 0.9
            elif days_inactive <= 90:
                recency = 0.7
            elif days_inactive <= 180:
                recency = 0.4
            else:
                recency = 0.1
        except ValueError:
            recency = 0.3
    else:
        recency = 0.2

    open_to_work = 1.0 if signals.get("open_to_work_flag", False) else 0.3

    response_rate = signals.get("recruiter_response_rate", 0)
    response_score = response_rate

    resp_time = signals.get("avg_response_time_hours", 72)
    if resp_time <= 4:
        time_score = 1.0
    elif resp_time <= 12:
        time_score = 0.9
    elif resp_time <= 24:
        time_score = 0.8
    elif resp_time <= 48:
        time_score = 0.6
    elif resp_time <= 72:
        time_score = 0.4
    else:
        time_score = 0.2

    github = signals.get("github_activity_score", -1)
    if github < 0:
        github_score = 0.3
    else:
        github_score = min(github / 80.0, 1.0)

    interview_rate = signals.get("interview_completion_rate", 0)
    offer_rate = signals.get("offer_acceptance_rate", -1)

    notice = signals.get("notice_period_days", 90)
    if notice <= 15:
        notice_score = 1.0
    elif notice <= 30:
        notice_score = 0.9
    elif notice <= 60:
        notice_score = 0.7
    elif notice <= 90:
        notice_score = 0.5
    else:
        notice_score = 0.3

    verified_email = 0.05 if signals.get("verified_email", False) else 0.0
    verified_phone = 0.05 if signals.get("verified_phone", False) else 0.0
    linkedin = 0.05 if signals.get("linkedin_connected", False) else 0.0

    saved = signals.get("saved_by_recruiters_30d", 0)
    saved_score = min(saved / 10.0, 1.0)

    combined = (
        recency * 0.20
        + open_to_work * 0.15
        + response_score * 0.15
        + time_score * 0.05
        + github_score * 0.10
        + interview_rate * 0.08
        + notice_score * 0.10
        + completeness * 0.05
        + saved_score * 0.02
        + verified_email + verified_phone + linkedin
        + (max(offer_rate, 0) * 0.05 if offer_rate >= 0 else 0.0)
    )

    return max(0.0, min(1.0, combined))


def score_education(candidate: dict) -> float:
    education = candidate.get("education", [])
    if not education:
        return 0.2

    best_tier_score = 0.0
    best_field_score = 0.0
    best_degree_score = 0.0

    relevant_fields = {
        "computer science", "machine learning", "artificial intelligence",
        "data science", "mathematics", "statistics", "information technology",
        "electrical engineering", "electronics", "software engineering",
    }

    for edu in education:
        tier = edu.get("tier", "unknown")
        field = edu.get("field_of_study", "").lower()
        degree = edu.get("degree", "").lower()

        tier_score = {
            "tier_1": 1.0, "tier_2": 0.7, "tier_3": 0.4,
            "tier_4": 0.2, "unknown": 0.3,
        }.get(tier, 0.2)
        best_tier_score = max(best_tier_score, tier_score)

        field_relevant = any(rf in field for rf in relevant_fields)
        best_field_score = max(best_field_score, 1.0 if field_relevant else 0.2)

        if any(d in degree for d in ["ph.d", "phd", "doctorate"]):
            best_degree_score = max(best_degree_score, 1.0)
        elif any(d in degree for d in ["m.s.", "m.tech", "m.e.", "master", "mba"]):
            best_degree_score = max(best_degree_score, 0.7)
        elif any(d in degree for d in ["b.tech", "b.e.", "b.sc", "bachelor"]):
            best_degree_score = max(best_degree_score, 0.4)
        else:
            best_degree_score = max(best_degree_score, 0.3)

    return best_tier_score * 0.4 + best_field_score * 0.4 + best_degree_score * 0.2


def keyword_stuffer_penalty(candidate: dict) -> float:
    title = candidate["profile"]["current_title"]
    title_score = TITLE_TIERS.get(title, 0.0)

    if title_score >= 0.35:
        return 0.0

    skills = candidate.get("skills", [])
    skill_names = {s["name"] for s in skills}
    ai_skill_count = len(skill_names & (RETRIEVAL_SEARCH_SKILLS | ML_CORE_SKILLS | LLM_FINETUNING_SKILLS))

    if title_score <= 0.05 and ai_skill_count >= 5:
        return -0.5
    elif title_score <= 0.05 and ai_skill_count >= 3:
        return -0.3
    elif title_score <= 0.15 and ai_skill_count >= 6:
        return -0.2

    return 0.0


# ─────────────────────────────────────────────────────────────────────
# Reasoning generation
# ─────────────────────────────────────────────────────────────────────

def generate_reasoning(candidate: dict, scores: dict, rank: int) -> str:
    profile = candidate["profile"]
    signals = candidate.get("redrob_signals", {})
    skill_info = scores["skill_details"]
    career_info = scores["career_details"]

    title = profile["current_title"]
    company = profile["current_company"]
    yoe = profile["years_of_experience"]
    location = profile.get("location", "")
    country = profile.get("country", "")

    parts = []

    parts.append(f"{title} at {company} with {yoe:.1f} yrs exp")

    if location:
        parts.append(f"based in {location}, {country}")

    retrieval_hits = skill_info.get("retrieval_hits", set())
    ml_hits = skill_info.get("ml_core_hits", set())
    if retrieval_hits:
        parts.append(f"retrieval/search skills: {', '.join(sorted(list(retrieval_hits)[:4]))}")
    if ml_hits:
        parts.append(f"ML core: {', '.join(sorted(list(ml_hits)[:3]))}")

    career = candidate.get("career_history", [])
    career_text = " ".join(ch.get("description", "") for ch in career).lower()
    strengths = []
    if any(kw in career_text for kw in ["ranking", "re-ranking", "reranking", "learn to rank", "learning-to-rank"]):
        strengths.append("ranking experience")
    if any(kw in career_text for kw in ["retrieval", "search", "semantic"]):
        strengths.append("search/retrieval background")
    if any(kw in career_text for kw in ["recommendation", "collaborative filtering"]):
        strengths.append("recommendation systems")
    if any(kw in career_text for kw in ["embedding", "vector"]):
        strengths.append("embeddings work")
    if any(kw in career_text for kw in ["production", "deployed", "shipped"]):
        strengths.append("production deployment")
    if any(kw in career_text for kw in ["a/b test", "evaluation", "ndcg", "mrr"]):
        strengths.append("evaluation framework experience")

    if strengths:
        parts.append(f"career highlights: {', '.join(strengths[:3])}")

    concerns = []
    response_rate = signals.get("recruiter_response_rate", 0)
    if response_rate < 0.3:
        concerns.append(f"low recruiter response rate ({response_rate:.0%})")

    notice = signals.get("notice_period_days", 0)
    if notice > 60:
        concerns.append(f"long notice period ({notice}d)")

    last_active = signals.get("last_active_date", "")
    if last_active:
        try:
            la = datetime.strptime(last_active, "%Y-%m-%d").date()
            days_inactive = (REFERENCE_DATE - la).days
            if days_inactive > 120:
                concerns.append(f"inactive for {days_inactive}d")
        except ValueError:
            pass

    if country != "India":
        concerns.append(f"located outside India ({country})")

    if yoe < 4:
        concerns.append(f"below experience range ({yoe:.1f} yrs)")
    elif yoe > 10:
        concerns.append(f"above target experience range ({yoe:.1f} yrs)")

    if concerns:
        parts.append(f"concerns: {'; '.join(concerns[:2])}")

    reasoning = "; ".join(parts)
    if len(reasoning) > 300:
        reasoning = reasoning[:297] + "..."
    return reasoning


# ─────────────────────────────────────────────────────────────────────
# Main scoring and ranking pipeline
# ─────────────────────────────────────────────────────────────────────

def score_candidate(candidate: dict) -> dict | None:
    if detect_honeypot(candidate):
        return None

    title_s = score_title(candidate)
    skill_result = score_skills(candidate)
    skill_s = skill_result["total"]
    career_result = score_career(candidate)
    career_s = career_result["total"]
    experience_s = score_experience(candidate)
    location_s = score_location(candidate)
    behavioral_s = score_behavioral(candidate)
    education_s = score_education(candidate)
    stuffer_pen = keyword_stuffer_penalty(candidate)

    # Corroborated skill depth: an "expert" claim backed by years of actual
    # usage (duration) is the strongest skill evidence available — the inverse
    # of the zero-duration expert honeypot pattern. Small additive bonus,
    # capped, so genuine depth separates from keyword breadth.
    corroborated_experts = sum(
        1 for s in candidate.get("skills", [])
        if s.get("proficiency") == "expert" and s.get("duration_months", 0) >= 24
    )
    depth_bonus = min(corroborated_experts, 8) / 8.0 * 0.03

    final_score = (
        title_s * 0.28
        + career_s * 0.25
        + skill_s * 0.20
        + behavioral_s * 0.12
        + experience_s * 0.08
        + location_s * 0.04
        + education_s * 0.03
        + depth_bonus
        + stuffer_pen
    )

    final_score = max(0.0, min(1.0, final_score))

    return {
        "candidate_id": candidate["candidate_id"],
        "score": final_score,
        "title_score": title_s,
        "skill_score": skill_s,
        "career_score": career_s,
        "behavioral_score": behavioral_s,
        "experience_score": experience_s,
        "location_score": location_s,
        "education_score": education_s,
        "stuffer_penalty": stuffer_pen,
        "skill_details": skill_result,
        "career_details": career_result,
        "candidate": candidate,
    }


def rank_candidates(candidates_path: str, output_path: str):
    scored = []
    honeypot_count = 0
    total = 0

    print("Loading and scoring candidates...", file=sys.stderr)
    with open(candidates_path, "r") as f:
        for line in f:
            if not line.strip():
                continue
            candidate = json.loads(line)
            total += 1
            result = score_candidate(candidate)
            if result is None:
                honeypot_count += 1
                continue
            scored.append(result)
            if total % 10000 == 0:
                print(f"  Processed {total} candidates...", file=sys.stderr)

    print(f"Total: {total}, Honeypots excluded: {honeypot_count}", file=sys.stderr)
    print(f"Candidates scored: {len(scored)}", file=sys.stderr)

    scored.sort(key=lambda x: (-x["score"], x["candidate_id"]))

    top_100 = scored[:100]

    for entry in top_100:
        entry["display_score"] = round(entry["score"], 4)

    for i in range(len(top_100) - 1):
        if top_100[i]["display_score"] == top_100[i + 1]["display_score"]:
            if top_100[i]["candidate_id"] > top_100[i + 1]["candidate_id"]:
                top_100[i], top_100[i + 1] = top_100[i + 1], top_100[i]

    for i in range(1, len(top_100)):
        if top_100[i]["display_score"] >= top_100[i - 1]["display_score"]:
            top_100[i]["display_score"] = top_100[i - 1]["display_score"] - 0.0001

    print(f"\nTop 10 candidates:", file=sys.stderr)
    for i, s in enumerate(top_100[:10]):
        print(
            f"  {i+1}. {s['candidate_id']} "
            f"({s['candidate']['profile']['current_title']} at {s['candidate']['profile']['current_company']}) "
            f"score={s['display_score']:.4f} "
            f"[title={s['title_score']:.2f} career={s['career_score']:.2f} "
            f"skill={s['skill_score']:.2f} behavioral={s['behavioral_score']:.2f} "
            f"exp={s['experience_score']:.2f} loc={s['location_score']:.2f}]",
            file=sys.stderr,
        )

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        for rank, entry in enumerate(top_100, 1):
            reasoning = generate_reasoning(entry["candidate"], entry, rank)
            writer.writerow([
                entry["candidate_id"],
                rank,
                f"{entry['display_score']:.4f}",
                reasoning,
            ])

    print(f"\nSubmission written to {output_path}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Rank candidates for Senior AI Engineer role")
    parser.add_argument("--candidates", required=True, help="Path to candidates.jsonl")
    parser.add_argument("--out", required=True, help="Output CSV path")
    args = parser.parse_args()
    rank_candidates(args.candidates, args.out)


if __name__ == "__main__":
    main()
