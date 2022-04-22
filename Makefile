install:
	pip install -r requirements.txt

lint:
	black .
	isort --profile black .
