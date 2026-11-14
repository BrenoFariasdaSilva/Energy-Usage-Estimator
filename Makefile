ifeq ($(OS),Windows_NT)
PYTHON ?= py -3
else
PYTHON ?= python3
endif

.PHONY: run install test diagnostics estimate pages pages-preview clean

run:
	$(PYTHON) scripts/launcher.py run

install:
	$(PYTHON) scripts/launcher.py install

test:
	$(PYTHON) scripts/launcher.py test

diagnostics:
	$(PYTHON) scripts/launcher.py diagnostics

estimate:
	$(PYTHON) main.py estimate --watts 300 --hours 8 --rate 1.0

clean:
	$(PYTHON) -c "import shutil; [shutil.rmtree(p, ignore_errors=True) for p in ('.pytest_cache', '.ruff_cache', 'build', 'dist')]"

pages:
	$(PYTHON) scripts/build_pages.py

pages-preview: pages
	$(PYTHON) -m http.server 8000 --directory dist
