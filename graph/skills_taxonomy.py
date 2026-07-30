"""Reference skills taxonomy: Category -> SubCategory -> ranked Skill chain,
plus curated cross-subcategory dependencies.

This is a static, hand-curated knowledge graph of technology skills (independent
of any candidate/job document) used to enrich the matching graph with
domain hierarchy: which skills imply which other, more foundational skills.

Graph model
-----------
    (:Category {name})
    (:SubCategory {name})
    (:Skill {normalized_name, name, rank})

    (:SubCategory)-[:BELONGS_TO]->(:Category)
    (:Skill)-[:BELONGS_TO]->(:SubCategory)
    (:Skill)-[:IMPLIES]->(:Skill)

Within a subcategory, skills are ordered from most advanced (rank 1) to most
foundational (rank N). IMPLIES chains them consecutively, advanced -> simpler,
e.g. rank 1 -[:IMPLIES]-> rank 2 -[:IMPLIES]-> rank 3 ...

CROSS_LINKS (below) adds IMPLIES edges *across* subcategories (and, since
2026-07-25, across top-level categories too — e.g. React Native implying
Front-End's React.js) for real dependencies the same-subcategory rank chain
can't express — e.g. knowing Kubernetes (Container Orchestration & Cluster
Management) should satisfy a requirement for Docker (Containerization &
Runtime Engines): you can't orchestrate containers you don't know, but
they're different subcategories, so no same-subcategory chain ever connected
them. Found live 2026-07-25: a candidate whose only container skill was
Kubernetes could never satisfy a job requiring plain Docker, even though any
human reviewer would call that a match. Same direction convention as the
rank chains (advanced/specialized -> foundational/general), curated by
hand — this is a judgment call, not something derived mechanically.
Coverage is deliberately partial (DevOps container/orchestration tooling,
mobile-language dependencies, BI/warehouse-to-SQL, and the RAG/vector-
embeddings pair) — each entry is one somebody actually reasoned through, not
a mechanically-generated sweep across every plausible pair in every
category. Extending it further is unstarted (see CLAUDE.md's Open
decisions).

2026-07-25: also enriched with three new top-level categories (Mobile
Development, Testing & Quality Engineering, Security & Identity) and three
new subcategories in existing ones (DevOps's Version Control Systems,
Databases' Cloud Data Warehouses, AI/ML's BI & Data Visualization Platforms
and LLM Techniques & Concepts) — still deliberately scoped to tech/data/AI
per the same judgment-call spirit as CROSS_LINKS, not a general skills
taxonomy (no design, marketing, sales, or general-business categories).

Skill.normalized_name (lower-cased, whitespace-stripped) is the dedup key
(see skill_normalized_name_unique in constraints.py) — not `name`. A few
skill *names* recur verbatim under more than one subcategory by design (e.g.
"OpenSearch" under both an observability subcategory and a vector/
hybrid-search subcategory, "Pulumi" under both a DevOps IaC subcategory and a
cloud IaC subcategory); normalized_name resolves those to a single Skill
node with multiple BELONGS_TO edges, same as before. What changed 2026-07-25
is that normalization also catches *incidental* casing/spacing variance
between independent sources (this taxonomy vs. a candidate's parsed resume
vs. a job posting) that isn't a deliberate recurrence, just noise — found via
a real "Power Bi" (candidate) / "Powerbi" (job posting) pair that used to
MERGE into two disconnected nodes. `name` is kept as a display property
(first value seen wins — see `_ADD_SUBCATEGORY`'s `coalesce`), not the key.
Its `rank` property reflects whichever subcategory was loaded last, since
rank is modeled per-node, not per-edge.

Migrating an already-populated graph from the old `name` key to
`normalized_name`: existing nodes have no `normalized_name` property, so a
`MERGE` on that property would create fresh duplicate nodes rather than
matching the old ones. Fixed with a one-time backfill
(`MATCH (s:Skill) WHERE s.normalized_name IS NULL SET s.normalized_name =
replace(toLower(s.name), " ", "")`) run before switching the constraint —
and, since two *already-distinct* nodes can turn out to normalize to the
same value (exactly the Power Bi/Powerbi case), a merge pass
(`deduplicate_skills` below) that folds those into one node first,
reattaching relationships, before the backfill+constraint would otherwise
fail on the collision.
"""

SKILLS_TAXONOMY = {
    "DevOps & Container Orchestration": {
        "Service Mesh & Advanced Traffic Management": [
            "Istio", "Linkerd", "Consul",
        ],
        "GitOps & Continuous Deployment Engines": [
            "ArgoCD", "Flux", "Spinnaker",
        ],
        "Container Orchestration & Cluster Management": [
            "Kubernetes", "OpenShift", "Nomad",
        ],
        "Package Management & Templating": [
            "Helm", "Kustomize",
        ],
        "Infrastructure as Code (IaC) & Configuration Automation": [
            "Terraform", "OpenTofu", "Pulumi", "Ansible", "Puppet", "Chef",
        ],
        "CI/CD Pipeline Platforms": [
            "GitHub Actions", "GitLab CI", "Jenkins", "CircleCI", "Azure DevOps Pipelines",
        ],
        "Observability, Monitoring & Log Aggregation": [
            "Prometheus", "Grafana", "Datadog", "ELK Stack", "OpenSearch", "Jaeger",
        ],
        "Containerization & Runtime Engines": [
            "Docker", "Podman", "containerd",
        ],
        "Reverse Proxies & Ingress Controllers": [
            "Nginx", "Traefik", "HAProxy", "Envoy",
        ],
        "OS & Scripting Foundations": [
            "Linux Systems Administration", "Bash", "Shell", "PowerShell",
        ],
        "Version Control Systems": [
            "Git", "GitHub", "GitLab", "Bitbucket", "SVN",
        ],
    },
    "Front-End Development": {
        "Micro-Frontends & Enterprise Web Architecture": [
            "Module Federation", "Bit", "Single-SPA",
        ],
        "Meta-Frameworks, Full-Stack React/Vue & SSR/SSG": [
            "Next.js", "Nuxt.js", "SvelteKit", "Remix", "Gatsby",
        ],
        "Complex State Management & Architecture": [
            "Redux Toolkit", "Zustand", "Recoil", "MobX",
            "TanStack Query (React Query)", "Apollo Client",
        ],
        "Typed Superset Languages": [
            "TypeScript",
        ],
        "Core Declarative UI Frameworks & Libraries": [
            "React.js", "Vue.js", "Angular", "Svelte", "SolidJS",
        ],
        "Build Tools, Module Bundlers & Package Managers": [
            "Vite", "Webpack", "Turbopack", "Rollup", "npm", "pnpm", "yarn",
        ],
        "Styling Systems, Preprocessors & Utility Frameworks": [
            "Tailwind CSS", "SASS/SCSS", "Styled Components", "Emotion",
            "CSS Modules", "Bootstrap",
        ],
        "Core Web Languages": [
            "JavaScript ES6+",
        ],
        "Foundational Layout & Markup": [
            "HTML5", "CSS3", "Flexbox", "CSS Grid",
        ],
    },
    "Back-End Development & Systems": {
        "Distributed Event Streaming, Message Brokers & RPC": [
            "Apache Kafka", "RabbitMQ", "Apache Pulsar", "gRPC", "Protocol Buffers",
        ],
        "Systems Programming & Memory-Safe Languages": [
            "Rust", "C++", "C",
        ],
        "High-Concurrency & Cloud-Native Languages": [
            "Go (Golang)",
        ],
        "Enterprise-Grade Heavyweight Frameworks": [
            "Java / Spring Boot", "C# / .NET Core", "Scala",
        ],
        "Fault-Tolerant & Distributed Runtimes": [
            "Elixir / Phoenix", "Erlang",
        ],
        "Lightweight & High-Performance API Frameworks": [
            "Python / FastAPI", "Node.js / NestJS", "Go / Fiber",
        ],
        "Traditional Web & Scripting Frameworks": [
            "Python / Django / Flask", "Node.js / Express.js", "PHP / Laravel",
            "Ruby / Ruby on Rails",
        ],
        "API Architecture Standards": [
            "RESTful APIs", "GraphQL", "WebSockets", "OpenAPI / Swagger",
        ],
        "Core Query & Data Manipulation": [
            "SQL", "JSON", "XML",
        ],
    },
    "Databases & Data Storage": {
        "Graph Databases & Graph RAG": [
            "Neo4j", "Amazon Neptune", "Memgraph", "ArangoDB",
        ],
        "Distributed Wide-Column NoSQL": [
            "Apache Cassandra", "ScyllaDB", "Amazon Keyspaces",
        ],
        "Cloud-Native Scalable NoSQL & Key-Value": [
            "Amazon DynamoDB", "Google Cloud Bigtable",
        ],
        "Vector Databases & Hybrid Search Engines": [
            "Pinecone", "Milvus", "Qdrant", "Chroma", "Weaviate",
            "Elasticsearch", "OpenSearch",
        ],
        "In-Memory Caches & High-Speed Stores": [
            "Redis", "Memcached", "Dragonfly",
        ],
        "Document Stores": [
            "MongoDB", "Couchbase", "Amazon DocumentDB", "PostgreSQL JSONB",
        ],
        "Advanced Relational Databases (RDBMS)": [
            "PostgreSQL", "MySQL", "MariaDB", "Oracle DB", "MS SQL Server",
        ],
        "Embedded & Light Databases": [
            "SQLite", "DuckDB",
        ],
        "Database Design & CRUD Fundamentals": [
            "Schema Normalization", "Indexes", "SQL Queries",
        ],
        "Cloud Data Warehouses": [
            "Snowflake", "Amazon Redshift", "Google BigQuery",
        ],
    },
    "Cloud Platforms & Infrastructure": {
        "Multi-Cloud Architecture & Programmatic IaC": [
            "AWS CloudFormation", "AWS CDK", "Pulumi", "Azure Resource Manager",
        ],
        "Serverless & Event-Driven Compute": [
            "AWS Lambda", "Google Cloud Functions", "Azure Functions",
        ],
        "Managed Container & Application Platforms": [
            "AWS ECS", "Azure App Service", "Google Cloud Run", "AWS EKS", "Google GKE",
        ],
        "Cloud API Gateways & Service Management": [
            "AWS API Gateway", "Azure API Management", "Kong Konnect",
        ],
        "Managed Cloud Storage & Managed Databases": [
            "AWS S3", "Google Cloud Storage", "AWS RDS", "Azure SQL",
        ],
        "Virtual Machines & Basic Compute": [
            "AWS EC2", "Google Compute Engine", "Azure Virtual Machines",
        ],
        "Cloud Networking & Access Control": [
            "AWS VPC", "Azure VNet", "AWS IAM", "Azure Active Directory (Entra ID)",
            "Security Groups",
        ],
        "DNS, CDN & Global Routing": [
            "Cloudflare", "AWS Route 53", "AWS CloudFront", "Fastly",
        ],
        "Basic Cloud Concepts": [
            "IaaS", "PaaS", "SaaS", "Public/Private Cloud",
        ],
    },
    "AI, Machine Learning & Data Science": {
        "LLM Orchestration, Agent Frameworks & Protocols": [
            "LangChain", "LlamaIndex", "AutoGen", "CrewAI", "MCP (Model Context Protocol)",
        ],
        "Deep Learning Frameworks & Computer Vision/NLP": [
            "PyTorch", "TensorFlow", "JAX", "Hugging Face Transformers", "OpenCV",
        ],
        "MLOps, Pipeline Tools & Model Registry": [
            "MLflow", "Kubeflow", "Weights & Biases", "Amazon SageMaker",
        ],
        "Classical Machine Learning & Statistical Libraries": [
            "Scikit-Learn", "XGBoost", "LightGBM", "CatBoost",
        ],
        "Distributed Big Data Engines & Data Orchestration": [
            "Apache Spark", "Databricks", "Apache Airflow", "dbt (data build tool)", "Prefect",
        ],
        "Data Manipulation, Cleaning & Analysis": [
            "Pandas", "Polars", "PySpark",
        ],
        "Data Science Scripting Languages": [
            "Python", "R", "Julia",
        ],
        "Core Math Foundations": [
            "NumPy", "SciPy", "Linear Algebra", "Statistics",
        ],
        "BI & Data Visualization Platforms": [
            "Looker", "Power BI", "Tableau", "Qlik Sense", "Apache Superset", "Metabase",
        ],
        "LLM Techniques & Concepts": [
            "Fine-Tuning", "Retrieval-Augmented Generation (RAG)",
            "Prompt Engineering", "Vector Embeddings",
        ],
    },
    "Web Scraping, Crawling & Data Extraction": {
        "Distributed Crawling Frameworks": [
            "Scrapy", "Crawlee", "Apache Nutch",
        ],
        "Headless Browser Automation (Modern)": [
            "Playwright", "Puppeteer",
        ],
        "Headless Browser Automation (Legacy / Cross-Browser)": [
            "Selenium",
        ],
        "Anti-Bot & Proxy Bypass Middleware": [
            "Undetected Chromedriver", "FlareSolverr", "ScraperAPI",
        ],
        "DOM Parsing & HTML Extraction Libraries": [
            "BeautifulSoup (bs4)", "Lxml", "Cheerio", "PyQuery",
        ],
        "HTTP Clients & Request Libraries": [
            "Httpx", "Requests", "Aiohttp", "Axios",
        ],
    },
    "Mobile Development": {
        "Cross-Platform App Frameworks": [
            "React Native", "Flutter", "Xamarin", "Ionic", ".NET MAUI",
        ],
        "iOS Native Development": [
            "SwiftUI", "UIKit", "Swift",
        ],
        "Android Native Development": [
            "Jetpack Compose", "Kotlin", "Java",
        ],
    },
    "Testing & Quality Engineering": {
        "Unit & Integration Testing Frameworks": [
            "Jest", "Pytest", "JUnit", "Mocha", "RSpec",
        ],
        "End-to-End & Browser Automation Testing": [
            "Cypress", "Playwright", "Selenium", "TestCafe",
        ],
        "Performance & Load Testing": [
            "k6", "JMeter", "Locust", "Gatling",
        ],
    },
    "Security & Identity": {
        "Application Security Testing (SAST/DAST)": [
            "Burp Suite", "OWASP ZAP", "SonarQube", "Snyk",
        ],
        "Identity, Authentication & Access Management": [
            "OAuth 2.0", "OpenID Connect", "SAML", "JWT",
        ],
        "Network & Infrastructure Security Tools": [
            "Metasploit", "Nmap", "Wireshark", "Nessus",
        ],
        "Cryptography & Compliance Fundamentals": [
            "Public Key Infrastructure (PKI)", "TLS/SSL", "Encryption", "GDPR Compliance",
        ],
    },
}

#: Curated cross-subcategory IMPLIES edges — see the module docstring for
#: why these exist and what they're not (mechanically derived, exhaustive,
#: or covering categories other than DevOps yet). (from, to): knowing `from`
#: implies knowing `to`, same "advanced -> foundational" direction as the
#: same-subcategory rank chains.
CROSS_LINKS = [
    # Orchestrators depend on knowing containers.
    ("Kubernetes", "Docker"),
    ("Nomad", "Docker"),
    # OpenShift is Kubernetes underneath; its own chain then reaches Docker
    # transitively (OpenShift -> Kubernetes -> Docker) via IMPLIES*1...
    ("OpenShift", "Kubernetes"),
    # Kubernetes packaging/templating tools operate on a cluster.
    ("Helm", "Kubernetes"),
    ("Kustomize", "Kubernetes"),
    # GitOps continuous-deployment engines predominantly target Kubernetes.
    ("ArgoCD", "Kubernetes"),
    ("Flux", "Kubernetes"),
    ("Spinnaker", "Kubernetes"),
    # Service meshes predominantly run on Kubernetes.
    ("Istio", "Kubernetes"),
    ("Linkerd", "Kubernetes"),
    ("Consul", "Kubernetes"),
    # Managed container platforms imply the engine/orchestrator they manage.
    ("AWS EKS", "Kubernetes"),
    ("Google GKE", "Kubernetes"),
    ("AWS ECS", "Docker"),

    # CI platforms imply the source-control platform they're built into.
    ("GitHub Actions", "GitHub"),
    ("GitLab CI", "GitLab"),

    # Cross-platform mobile frameworks depend on the language they're
    # written in. Dart isn't otherwise in the taxonomy — MERGE creates it.
    ("Flutter", "Dart"),
    # React Native is React, targeting native views — same underlying skill.
    ("React Native", "React.js"),

    # BI/visualization platforms are built on querying data with SQL.
    ("Power BI", "SQL Queries"),
    ("Tableau", "SQL Queries"),
    ("Looker", "SQL Queries"),

    # Cloud data warehouses are queried with SQL.
    ("Snowflake", "SQL Queries"),
    ("Amazon Redshift", "SQL Queries"),
    ("Google BigQuery", "SQL Queries"),

    # RAG is specifically built on vector embeddings/similarity search — a
    # stronger, more direct dependency than the subcategory's linear rank
    # chain alone expresses.
    ("Retrieval-Augmented Generation (RAG)", "Vector Embeddings"),
    # The two dominant LLM orchestration frameworks are RAG-first tools.
    ("LangChain", "Retrieval-Augmented Generation (RAG)"),
    ("LlamaIndex", "Retrieval-Augmented Generation (RAG)"),
]

_ADD_SUBCATEGORY = """
MERGE (cat:Category {name: $category})
MERGE (sub:SubCategory {name: $subcategory})
MERGE (sub)-[:BELONGS_TO]->(cat)

FOREACH (sk IN $skills |
  MERGE (s:Skill {normalized_name: sk.normalized_name})
  SET s.name = coalesce(s.name, sk.name),
      s.rank = sk.rank
  MERGE (s)-[:BELONGS_TO]->(sub)
)

FOREACH (pair IN $implies_pairs |
  MERGE (a:Skill {normalized_name: pair.from_normalized})
  SET a.name = coalesce(a.name, pair.from)
  MERGE (b:Skill {normalized_name: pair.to_normalized})
  SET b.name = coalesce(b.name, pair.to)
  MERGE (a)-[:IMPLIES]->(b)
)
"""

_ADD_CROSS_LINKS = """
UNWIND $pairs AS pair
MERGE (a:Skill {normalized_name: pair.from_normalized})
SET a.name = coalesce(a.name, pair.from)
MERGE (b:Skill {normalized_name: pair.to_normalized})
SET b.name = coalesce(b.name, pair.to)
MERGE (a)-[:IMPLIES]->(b)
"""


def _normalize(name: str) -> str:
    return name.lower().replace(" ", "")


def add_subcategory(session, category: str, subcategory: str, skills: list) -> None:
    """Load one subcategory's ranked skill chain: rank 1 (most advanced) ->
    rank N (most foundational), each IMPLIES the next."""
    session.run(
        _ADD_SUBCATEGORY,
        category=category,
        subcategory=subcategory,
        skills=[
            {"name": name, "normalized_name": _normalize(name), "rank": i + 1}
            for i, name in enumerate(skills)
        ],
        implies_pairs=[
            {
                "from": skills[i],
                "from_normalized": _normalize(skills[i]),
                "to": skills[i + 1],
                "to_normalized": _normalize(skills[i + 1]),
            }
            for i in range(len(skills) - 1)
        ],
    )


def add_cross_links(session, cross_links: list = CROSS_LINKS) -> None:
    """Load the hand-curated cross-subcategory IMPLIES edges (see
    CROSS_LINKS above). MERGE, not MATCH, on both ends: safe to run before or
    after add_subcategory for the skills involved, and safe against a
    cross-link naming a skill that isn't in SKILLS_TAXONOMY at all (it just
    gets a Skill node with no rank/BELONGS_TO, same as any candidate/job
    skill outside the taxonomy)."""
    session.run(
        _ADD_CROSS_LINKS,
        pairs=[
            {
                "from": from_name,
                "from_normalized": _normalize(from_name),
                "to": to_name,
                "to_normalized": _normalize(to_name),
            }
            for from_name, to_name in cross_links
        ],
    )


def apply_taxonomy(session, taxonomy: dict = SKILLS_TAXONOMY) -> None:
    for category, subcategories in taxonomy.items():
        for subcategory, skills in subcategories.items():
            add_subcategory(session, category, subcategory, skills)
    add_cross_links(session)


def deduplicate_skills(session) -> int:
    """One-time migration: folds Skill nodes that share a normalized_name
    but were created under the old name-keyed MERGE (so they're currently
    separate nodes, e.g. "Power Bi" and "Powerbi") into a single node,
    reattaching every relationship before deleting the duplicate. Must run
    before backfilling normalized_name + creating
    skill_normalized_name_unique, or the constraint creation fails on the
    collision. Returns the number of duplicate nodes removed. Safe to
    re-run — a no-op once no collisions remain."""
    result = session.run(
        """
        MATCH (s:Skill)
        WITH replace(toLower(s.name), " ", "") AS norm, collect(s) AS nodes
        WHERE size(nodes) > 1
        WITH norm, nodes[0] AS keep, nodes[1..] AS duplicates
        UNWIND duplicates AS dup
        CALL {
          WITH keep, dup
          OPTIONAL MATCH (dup)-[r:BELONGS_TO]->(sub)
          FOREACH (_ IN CASE WHEN r IS NOT NULL THEN [1] ELSE [] END |
            MERGE (keep)-[:BELONGS_TO]->(sub)
          )
          OPTIONAL MATCH (dup)-[:IMPLIES]->(out)
          FOREACH (_ IN CASE WHEN out IS NOT NULL THEN [1] ELSE [] END |
            MERGE (keep)-[:IMPLIES]->(out)
          )
          OPTIONAL MATCH (inc)-[:IMPLIES]->(dup)
          FOREACH (_ IN CASE WHEN inc IS NOT NULL THEN [1] ELSE [] END |
            MERGE (inc)-[:IMPLIES]->(keep)
          )
          OPTIONAL MATCH (cand:Candidate)-[hs:HAS_SKILL]->(dup)
          FOREACH (_ IN CASE WHEN hs IS NOT NULL THEN [1] ELSE [] END |
            MERGE (cand)-[hs2:HAS_SKILL]->(keep)
            SET hs2.years_experience = hs.years_experience,
                hs2.last_used_year = hs.last_used_year
          )
          OPTIONAL MATCH (j:Job)-[rs:REQUIRES_SKILL]->(dup)
          FOREACH (_ IN CASE WHEN rs IS NOT NULL THEN [1] ELSE [] END |
            MERGE (j)-[rs2:REQUIRES_SKILL]->(keep)
            SET rs2.min_years = rs.min_years
          )
          OPTIONAL MATCH (j2:Job)-[ps:PREFERS_SKILL]->(dup)
          FOREACH (_ IN CASE WHEN ps IS NOT NULL THEN [1] ELSE [] END |
            MERGE (j2)-[ps2:PREFERS_SKILL]->(keep)
            SET ps2.weight = ps.weight
          )
          SET keep.rank = coalesce(keep.rank, dup.rank)
          DETACH DELETE dup
          RETURN count(*) AS n
        }
        RETURN count(*) AS removed
        """
    ).single()
    return result["removed"] if result else 0


def backfill_normalized_name(session) -> int:
    """One-time migration: sets normalized_name on any Skill node that
    predates the 2026-07-25 switch from name-keyed to normalized-name-keyed
    MERGE (see module docstring). Run deduplicate_skills() first — this
    assumes no two remaining nodes collide on the computed value, which is
    exactly what creating skill_normalized_name_unique afterwards enforces.
    Safe to re-run — only touches nodes missing the property."""
    result = session.run(
        """
        MATCH (s:Skill) WHERE s.normalized_name IS NULL
        SET s.normalized_name = replace(toLower(s.name), " ", "")
        RETURN count(s) AS updated
        """
    ).single()
    return result["updated"] if result else 0
