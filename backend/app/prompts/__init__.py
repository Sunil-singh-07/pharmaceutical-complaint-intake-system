"""Prompts package.

Holds LLM prompt templates as plain text files, loaded by their owning
service (e.g. ``extractor.txt`` is loaded by
``app.services.llm_service.LLMService``). ``intent_router``,
``classifier``, and ``responder`` prompts are added in later development
phases per the Development Plan.
"""
