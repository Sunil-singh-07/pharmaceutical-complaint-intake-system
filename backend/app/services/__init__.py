"""Services package.

Owns all business logic. Implemented: Session Manager (in-memory
ComplaintState store), Validator (deterministic complaint validation),
RiskEngine (deterministic risk assessment), and LLMService (structured
information extraction only). Reserved for a later phase: PDF Parser.
The Knowledge Loader lives in ``app.knowledge``, not here.
"""
