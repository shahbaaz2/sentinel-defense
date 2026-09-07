"""Falco integration (Phase 8) - contract and fixtures only, per the phase scope: Falco is not run
live in this lab (a live Falco needs kernel-level instrumentation of the Colima VM that is not
worth the added instability for a Lite-profile 16 GB machine). The adapter/mapper are real and
tested against Falco's actual default JSON alert shape (see tests/unit/test_falco_mapper.py) so
enabling it against a real Falco output file later needs no code change - see docs/integrations.md.
"""

ADAPTER_VERSION = "FALCO-001"
