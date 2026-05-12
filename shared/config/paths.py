from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]

ENV_FILE = ROOT_DIR / ".env"

ML_CONFIG_FILE = ROOT_DIR / "ml_conf.yaml"
