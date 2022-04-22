install:
	pipenv install --python 3.9.10

install-dev:
	pipenv install --dev --python 3.9.10

lint:
	pipenv run black .
	pipenv run isort --profile black .
