# Security scope

## Synthetic-only scope

This repository implements a **local, synthetic, disconnected cybersecurity laboratory**. It must not be
used to target real systems, networks, organizations, credentials, military infrastructure, weapons
systems, or third parties. It contains no authorization to perform offensive activity against anything
outside this repository's own local/synthetic lab.

MissionNet is a fictional mission-information application with fictional users, services, telemetry, and
records. It is not a digital twin of any real system and must never be populated with real classified
information, Controlled Unclassified Information (CUI), production credentials, or real operational data.

## Prohibited in this codebase

- Malware, ransomware, destructive payloads, or persistence mechanisms targeting real/external systems.
- Credential theft, data exfiltration, or "hack back" capability of any kind.
- A general-purpose shell, SQL, SSH, or firewall tool exposed to the LLM.
- Model-generated commands passed directly to a privileged executor without allow-list validation.
- Any dependency on a paid cloud service or external AI API for the MVP; external AI is disabled by
  default (`SENTINEL_EXTERNAL_AI_ENABLED=false`). An optional cloud provider (`ai/providers/
  deepseek_provider.py`) exists for operators who choose to deploy off this Mac (see
  `docs/deployment.md`) - it is off by default, requires explicitly setting both
  `SENTINEL_LLM_PROVIDER=deepseek` and `SENTINEL_EXTERNAL_AI_ENABLED=true`, and never changes the
  AI Analyst's own guardrails (schema-validated output only, no write path, cannot approve or
  execute anything). Enabling it is an honest, visible change to System Assurance's
  `inference_location`/`internet_required_for_core_demo` fields, never silently masked.
- Claims of DoD certification, CMMC certification, an Authorization to Operate, classified suitability,
  or regulatory compliance — this is a research prototype, not an accredited system.

## Threat model summary

Telemetry is attacker-influenced data and is treated as untrusted at every layer:

```
Sensor/event text         = UNTRUSTED EVIDENCE
Retrieved ATT&CK/KEV      = TRUSTED REFERENCE DATA
Approved runbooks         = TRUSTED OPERATIONAL GUIDANCE
Policy bundle             = AUTHORITATIVE CONTROL
LLM output                = UNTRUSTED RECOMMENDATION
Policy-validated executor = AUTHORIZED ACTION
```

Full threat model: blueprint §20 (`docs/blueprint.md`). Response actions are allow-listed, asset-scoped,
parameter-validated, auditable, and reversible where designed. No playbook marked `requires_approval`
executes without a matching, unexpired approval record tied to the same incident and playbook version.

## Reporting

This is a local single-developer prototype with no external users. If you find a design gap that would
let untrusted evidence text escalate into an authorized action (prompt injection bypassing policy,
excessive-agency tool exposure, improper output handling), record it in `DECISIONS.md` and fix it before
continuing to the next phase — do not ship around it.

## Authorized validation tooling

Atomic Red Team and MITRE CALDERA are optional, later, **isolated-lab-only** validation tools (blueprint
§19). They are not part of the MVP and must never be pointed at anything outside this local lab.
