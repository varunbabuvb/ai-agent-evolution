PY=PYTHONPATH=src python

.PHONY: data pipeline forecast app test

data:
	$(PY) scripts/run_collection.py

pipeline:
	$(PY) scripts/run_pipeline.py

forecast:
	$(PY) scripts/run_forecast.py

app:
	streamlit run app/streamlit_app.py

test:
	PYTHONPATH=src python -m pytest -q tests
