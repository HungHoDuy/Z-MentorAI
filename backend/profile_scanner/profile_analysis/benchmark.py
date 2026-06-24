BENCHMARK_VERSION = "cv-benchmark-v1.1"

BENCHMARK_NOTES = [
    "Role-skill fit is mapped from an internal role benchmark inspired by O*NET/ESCO occupation-skill taxonomies.",
    "Career-readiness signals follow the NACE competency framing: communication, teamwork, technology, leadership, professionalism, critical thinking, and career self-development.",
    "Gemini may normalize CV evidence, but deterministic rubric weights produce the final score and grade.",
    "Scores should be calibrated later with recruiter-reviewed CV datasets and real job-posting benchmarks.",
]

GRADE_THRESHOLDS = [
    ("S", 90),
    ("A", 80),
    ("B", 70),
    ("C", 60),
    ("D", 50),
    ("E", 0),
]

DIMENSION_WEIGHTS = {
    "role_skill_fit": 0.35,
    "experience_evidence": 0.20,
    "education_certification": 0.15,
    "career_readiness": 0.15,
    "cv_clarity": 0.15,
}

SKILL_ALIASES = {
    "python": ["python"],
    "sql": ["sql", "postgresql", "mysql", "sql server", "bigquery"],
    "excel": ["excel", "spreadsheet", "google sheets"],
    "power bi": ["power bi", "powerbi"],
    "tableau": ["tableau"],
    "data visualization": ["data visualization", "visualization", "dashboard", "bi dashboard"],
    "statistics": ["statistics", "statistical", "a/b testing", "hypothesis testing"],
    "machine learning": ["machine learning", "ml", "scikit-learn", "sklearn", "tensorflow", "pytorch"],
    "etl": ["etl", "data pipeline", "airflow", "dbt"],
    "javascript": ["javascript", "js", "typescript"],
    "typescript": ["typescript", "ts"],
    "react": ["react", "reactjs", "next.js", "nextjs"],
    "html": ["html", "html5"],
    "css": ["css", "tailwind", "sass", "scss"],
    "node.js": ["node.js", "nodejs", "express"],
    "fastapi": ["fastapi"],
    "django": ["django"],
    "flask": ["flask"],
    "docker": ["docker", "container"],
    "kubernetes": ["kubernetes", "k8s"],
    "gcp": ["gcp", "google cloud", "cloud run", "bigquery", "firestore", "vertex ai"],
    "aws": ["aws", "amazon web services", "lambda", "s3", "ec2"],
    "linux": ["linux", "ubuntu", "bash", "shell"],
    "git": ["git", "github", "gitlab"],
    "api": ["api", "rest", "graphql", "grpc"],
    "testing": ["test", "testing", "unit test", "integration test", "pytest", "jest"],
    "figma": ["figma"],
    "ux research": ["ux research", "user research", "usability"],
    "wireframing": ["wireframe", "wireframing", "prototype", "prototyping"],
    "product management": ["product management", "roadmap", "prd", "user story"],
    "agile": ["agile", "scrum", "kanban"],
    "communication": ["communication", "presentation", "stakeholder", "communicated", "documented", "trình bày", "báo cáo"],
}

CAREER_READINESS_SIGNALS = {
    "communication": ["presented", "communicated", "wrote", "documented", "stakeholder", "presentation", "báo cáo", "trình bày"],
    "teamwork": ["team", "collaborated", "cross-functional", "worked with", "nhóm", "phối hợp"],
    "leadership": ["led", "managed", "mentored", "owned", "leader", "dẫn dắt", "quản lý"],
    "critical thinking": ["analyzed", "optimized", "debugged", "solved", "root cause", "phân tích", "tối ưu"],
    "professionalism": ["deadline", "quality", "standard", "process", "compliance", "quy trình", "chất lượng"],
    "technology": ["built", "implemented", "automated", "deployed", "developed", "xây dựng", "triển khai"],
    "career self-development": ["certification", "course", "self-study", "bootcamp", "khóa học", "chứng chỉ", "tự học"],
}

ROLE_BENCHMARKS = {
    "data_analyst": {
        "label": "Data Analyst",
        "aliases": ["data analyst", "business analyst", "bi analyst", "junior data analyst", "entry-level data analyst", "phân tích dữ liệu"],
        "core_skills": ["sql", "excel", "data visualization", "statistics"],
        "supporting_skills": ["python", "power bi", "tableau", "etl"],
        "education_keywords": ["data", "statistics", "computer science", "information systems", "business", "analytics", "toán", "thống kê"],
    },
    "frontend_engineer": {
        "label": "Frontend Engineer",
        "aliases": ["frontend", "front-end", "react developer", "web developer", "frontend engineer"],
        "core_skills": ["javascript", "typescript", "react", "html", "css"],
        "supporting_skills": ["testing", "api", "git", "figma"],
        "education_keywords": ["computer science", "software", "information technology", "web", "công nghệ thông tin"],
    },
    "backend_engineer": {
        "label": "Backend Engineer",
        "aliases": ["backend", "back-end", "backend developer", "software engineer", "python backend", "java backend"],
        "core_skills": ["python", "sql", "api", "docker"],
        "supporting_skills": ["fastapi", "django", "flask", "gcp", "aws", "testing"],
        "education_keywords": ["computer science", "software", "information technology", "công nghệ thông tin"],
    },
    "cloud_devops": {
        "label": "Cloud / DevOps Engineer",
        "aliases": ["devops", "cloud engineer", "site reliability", "sre", "cloud devops"],
        "core_skills": ["linux", "docker", "gcp", "aws", "git"],
        "supporting_skills": ["kubernetes", "python", "testing"],
        "education_keywords": ["computer science", "network", "information technology", "cloud", "công nghệ thông tin"],
    },
    "ux_ui_designer": {
        "label": "UX/UI Designer",
        "aliases": ["ui designer", "ux designer", "product designer", "ux/ui"],
        "core_skills": ["figma", "ux research", "wireframing"],
        "supporting_skills": ["html", "css", "product management"],
        "education_keywords": ["design", "human computer interaction", "media", "mỹ thuật", "thiết kế"],
    },
    "product_manager": {
        "label": "Product Manager",
        "aliases": ["product manager", "associate product manager", "apm", "product owner"],
        "core_skills": ["product management", "agile", "communication"],
        "supporting_skills": ["sql", "data visualization", "ux research"],
        "education_keywords": ["business", "computer science", "information systems", "marketing", "quản trị"],
    },
    "general_early_career": {
        "label": "General Early-Career Profile",
        "aliases": [],
        "core_skills": ["git", "communication", "technology"],
        "supporting_skills": ["sql", "python", "javascript", "excel", "agile"],
        "education_keywords": ["computer science", "business", "engineering", "information technology", "công nghệ thông tin"],
    },
}
