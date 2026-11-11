"""
Skill extraction, the simple way: a fixed vocabulary and word matching.
Good enough for an MVP and easy to explain. Its weakness is that it only
finds skills that are in the list and spelled the way the list spells them.
"""
import re

SKILLS = [
    "python", "java", "javascript", "typescript", "go", "c++", "c#", "swift", "kotlin", "dart", "bash", "sql",
    "html", "css", "react", "react native", "vue", "angular", "next.js", "tailwind", "node.js", "express",
    "fastapi", "django", "flask", "spring boot", "graphql", "rest", "grpc",
    "postgresql", "mysql", "mongodb", "redis", "kafka", "rabbitmq",
    "docker", "kubernetes", "terraform", "aws", "azure", "gcp", "linux", "git", "jenkins", "github actions", "ci/cd",
    "pytorch", "tensorflow", "scikit-learn", "pandas", "numpy", "spark", "airflow", "dbt", "hugging face",
    "machine learning", "deep learning", "nlp", "llm", "embeddings", "statistics",
    "jest", "pytest", "unit testing", "figma", "firebase", "swiftui", "flutter", "jetpack compose",
    "networking", "penetration testing", "owasp", "siem", "prometheus", "grafana",
]

# Different spellings that mean the same skill.
ALIASES = {"postgres": "postgresql", "nodejs": "node.js", "k8s": "kubernetes",
           "sklearn": "scikit-learn", "golang": "go",
           "rest api": "rest", "rest apis": "rest", "unit tests": "unit testing", "huggingface": "hugging face"}


def extract_skills(text: str) -> list[str]:
    """Return the skills from SKILLS that appear in the text, alphabetically."""
    text = text.lower()
    found = set()
    for term in SKILLS + list(ALIASES):
        # (?<![a-z0-9]) and (?![a-z0-9]) mean "not in the middle of a word",
        # so "go" does not match inside "google" and "java" not inside "javascript".
        if re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9+#])", text):
            found.add(ALIASES.get(term, term))
    return sorted(found)
