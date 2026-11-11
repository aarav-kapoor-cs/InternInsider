"""
Skill extraction, the simple way: a fixed list of skills and word matching.
Easy to explain and test. It only finds skills that are on the list.
"""
import re

# Grouped so the Resume page can show them under headings.
SKILL_GROUPS = {
    "Languages": ["python", "java", "javascript", "typescript", "rust", "c++", "c#", "swift", "kotlin",
                  "dart", "scala", "ruby", "php", "bash", "sql", "html", "css", "matlab"],
    "Frontend": ["react", "react native", "vue", "angular", "next.js", "tailwind", "redux", "figma"],
    "Backend": ["node.js", "express.js", "fastapi", "django", "flask", "spring boot", ".net", "graphql",
                "rest api", "grpc", "websockets", "microservices", "kafka", "rabbitmq"],
    "Databases": ["postgresql", "mysql", "mongodb", "redis", "sqlite", "pgvector", "elasticsearch",
                  "snowflake", "bigquery"],
    "Cloud & DevOps": ["docker", "kubernetes", "terraform", "aws", "azure", "gcp", "linux", "git",
                       "github actions", "jenkins", "ci/cd", "prometheus", "grafana"],
    "Data & ML": ["machine learning", "deep learning", "computer vision", "nlp", "statistics", "pytorch",
                  "tensorflow", "keras", "scikit-learn", "pandas", "numpy", "spark", "airflow", "dbt",
                  "tableau", "power bi", "hugging face", "opencv"],
    "AI & LLMs": ["llm", "rag", "embeddings", "langchain", "langgraph", "openai", "mcp", "semantic kernel"],
    "Mobile": ["ios", "android", "swiftui", "flutter", "jetpack compose", "firebase"],
    "Testing": ["unit testing", "pytest", "jest", "junit", "selenium", "cypress", "playwright"],
    "Security": ["penetration testing", "owasp", "siem", "splunk", "wireshark", "network security"],
    "Practices": ["agile", "scrum", "jira", "object-oriented programming", "data structures"],
}
SKILLS = [skill for group in SKILL_GROUPS.values() for skill in group]

# Other spellings of the same skill.
ALIASES = {
    "postgres": "postgresql", "nodejs": "node.js", "expressjs": "express.js", "nextjs": "next.js",
    "k8s": "kubernetes", "sklearn": "scikit-learn", "huggingface": "hugging face", "mongo": "mongodb",
    "rest apis": "rest api", "restful": "rest api", "unit tests": "unit testing", "websocket": "websockets",
    "llms": "llm", "natural language processing": "nlp", "google cloud": "gcp", "oop": "object-oriented programming",
}

# These skill names are also everyday English: "react to feedback", "the rest of
# the team", "a swift reply". They only count when capitalised like the technology.
CAPITALISED = {"react": "React", "swift": "Swift", "spark": "Spark", "rust": "Rust", "dart": "Dart",
               "rag": "RAG", "rest api": "REST"}


def extract_skills(text: str) -> list[str]:
    """Return the skills from the list that appear in the text, alphabetically."""
    lower = text.lower()
    found = set()
    for term in SKILLS + list(ALIASES):
        if term in CAPITALISED:
            continue
        # (?<![a-z0-9]) and (?![a-z0-9+#]) mean "not inside another word",
        # so "java" is not found inside "javascript" and "git" not inside "github".
        if re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9+#])", lower):
            found.add(ALIASES.get(term, term))
    for skill, written in CAPITALISED.items():
        if re.search(r"\b" + written + r"\b", text):  # case-sensitive: "React", not "react"
            found.add(skill)
    return sorted(found)


def group_skills(skills: list[str]) -> dict[str, list[str]]:
    """{"Languages": ["python", "sql"], "Frontend": ["react"], ...}"""
    groups = {name: [s for s in members if s in skills] for name, members in SKILL_GROUPS.items()}
    return {name: found for name, found in groups.items() if found}
