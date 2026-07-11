# Architecture Documents

This folder owns architecture and design-proof documents for OfficeFlow /
FakturaBot.

Active source-of-truth documents can still live outside this folder when their
role is broader than architecture:

- `docs/TZ_FakturaBot.md` remains the product/runtime technical assignment.
- `docs/llm/FakturaBot_LLM_Orchestrator_Contract.md` remains the LLM
  orchestration contract.
- `PROJECT_LOG.md` remains the chronological decision log.

Current architecture/design documents:

- `OfficeFlow_Architecture_Framing.md`
- `OfficeFlow_Storage_Model_Proposal.md`
- `MULTI_WORKSPACE_BUSINESS_PROFILES_ARCHITECTURE_DESIGN_PROOF.md`

The multi-workspace business profiles proof is a handoff-ready architecture
decision record. It does not by itself make multi-business profiles supported
in runtime; implementation still requires code, migrations, Product Truth,
InfoHelp, tests, and acceptance proof.
