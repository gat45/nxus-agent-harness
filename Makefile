PYTHONPATH := src

.PHONY: test demo audit

test:
	PYTHONPATH=$(PYTHONPATH) python3 -m unittest discover -s tests -v

demo:
	PYTHONPATH=$(PYTHONPATH) python3 -m nxus_harness demo

audit:
	@test -n "$(RUN)" || (echo "Usage: make audit RUN=runs/<tenant>/<run>/audit.jsonl" && exit 2)
	PYTHONPATH=$(PYTHONPATH) python3 -m nxus_harness verify-audit $(RUN)
