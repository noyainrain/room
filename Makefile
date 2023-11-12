PYTHON=python3
PIP=pip3
PIPFLAGS=--upgrade
NPM=npm
NPMFLAGS=--no-save

.PHONY: test
test:
	$(PYTHON) -m unittest

.PHONY: test-ui
test-ui:
	$(PYTHON) -m unittest room.tests.ui_test

.PHONY: type
type:
	mypy
	$(NPM) --prefix=client run type

.PHONY: lint
lint:
	pylint room
	$(NPM) --prefix=client run lint

.PHONY: check
check: type test test-ui lint

.PHONY: deps
deps:
	$(PIP) install $(PIPFLAGS) --requirement requirements.txt

.PHONY: deps-dev
deps-dev:
	$(PIP) install $(PIPFLAGS) --requirement requirements-dev.txt
	@# Work around npm 7 update modifying package.json (see https://github.com/npm/cli/issues/3044)
	$(NPM) --prefix=client install $(NPMFLAGS)

.PHONY: clean
clean:
	rm --recursive --force $$(find . -name __pycache__) .mypy_cache
	$(NPM) --prefix=client run clean
