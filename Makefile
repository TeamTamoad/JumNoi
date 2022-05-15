.ONESHELL:
package:
	@[ -z $(function) ] && printf "Please set 'function' variable\nExample: function=jumnoiFulfillment make package\n" && exit 1
	@[ ! -d ./$(function) ] && echo "'function' not found" && exit 1
	@[ ! -f ./$(function)/requirements.txt ] && echo "Directory doesn't contain requirements.txt" && exit 1
	@echo "Packaging $(function) fucntion for the deployment"
	@cd ./$(function)
	if [ -d packages ]; then \
		echo "Removing existing 'packages' directory"; \
		rm -r packages;\
	fi
	@mkdir packages
	@pip install --target packages -r requirements.txt
	@cd packages
	@zip ../../$(function).zip -r .
	@cd ..
	@zip ../$(function).zip -g *.py
	@echo "Done!"
