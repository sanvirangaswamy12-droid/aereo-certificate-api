import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'certificates.db'}")
CERTIFICATE_DIR = Path(os.getenv("CERTIFICATE_DIR", BASE_DIR / "generated_certificates"))

# Upper limit of recipients accepted in a single job (protects the server).
MAX_RECIPIENTS_PER_JOB = int(os.getenv("MAX_RECIPIENTS_PER_JOB", "1000"))
