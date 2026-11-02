"""Raw collections -> corpus_v1.jsonl -> corpus_v1_clean.jsonl. Usage: python scripts/run_pipeline.py"""
import os, subprocess, sys
env = {**os.environ, "PYTHONPATH": "src"}
for mod in ["ainevo.preprocessing.build_corpus", "ainevo.preprocessing.clean_dedup"]:
    print("==", mod); subprocess.run([sys.executable, "-m", mod], check=True, env=env)
