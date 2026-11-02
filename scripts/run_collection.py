"""Run all collectors (needs internet; GITHUB_TOKEN recommended). Usage: python scripts/run_collection.py"""
import os, subprocess, sys
env = {**os.environ, "PYTHONPATH": "src"}
for mod in ["ainevo.collection.arxiv_collector", "ainevo.collection.blogs", "ainevo.collection.github_releases"]:
    print("==", mod); subprocess.run([sys.executable, "-m", mod], check=True, env=env)
