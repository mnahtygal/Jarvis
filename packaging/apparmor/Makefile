CC ?= cc
CFLAGS ?= -O2 -pipe
CPPFLAGS ?=
WARNINGS := -Wall -Wextra -Werror -Wconversion -Wformat=2 -Wshadow -Wstrict-prototypes

.PHONY: all clean check

all: jarvis-api-entry jarvis-candidate-sandbox

runtime-manifest.h: src/generate_runtime_manifest.py
	../../.venv/bin/python $< > $@.tmp
	mv $@.tmp $@

jarvis-api-entry: src/jarvis-api-entry.c
	$(CC) $(CPPFLAGS) $(CFLAGS) $(WARNINGS) -std=c17 -o $@ $<
	chmod 0755 $@

jarvis-candidate-sandbox: src/jarvis-candidate-sandbox.c runtime-manifest.h
	$(CC) $(CPPFLAGS) $(CFLAGS) $(WARNINGS) -std=c17 -o $@ $<
	chmod 0755 $@

check: all
	../../.venv/bin/python -m pytest -q ../../tests/test_apparmor_launchers.py

clean:
	rm -f jarvis-api-entry jarvis-candidate-sandbox runtime-manifest.h runtime-manifest.h.tmp
