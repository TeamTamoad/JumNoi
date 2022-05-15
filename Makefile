.ONESHELL:
package:
	@echo "Packaging $(function) fucntion for the deployment"
	@cd $(function)
	rm -rf packages
	mkdir packages
	pip install --target packages -r requirements.txt
	@cd packages
	zip ../../$(function).zip -r .
	@cd ..
	zip ../$(function).zip -g *.py
