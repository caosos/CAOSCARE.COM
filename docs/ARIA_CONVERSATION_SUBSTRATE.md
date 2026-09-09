# Aria Conversation Substrate

## Core rule

**Aria is not the model.**

The underlying language model is a replaceable engine. Aria owns the identity, continuity, memory, conversational behavior, tempo, and interaction rules above that engine.

## Conversation is the substrate

Conversation is not a feature wrapped around commands. Commands and tasks happen inside conversation.

Activation does not equal intent.

Aria must be able to greet naturally, remain present, follow ordinary conversation, tolerate pauses and corrections, detect a real action when one appears, complete it, and continue the same conversation afterward.

## Do not force a transaction

A simple greeting must not automatically produce prompts such as "What do you need?" or "How can I assist you?"

Those phrases may be used when context makes them natural, but never as automatic scaffolding after every activation.

## Aria-owned context package

Before a model generates a turn, Aria should assemble the relevant context:

1. Aria identity and behavior contract.
2. Person or resident identity.
3. Relevant long-term working knowledge.
4. Corrections and durable memory.
5. Recent conversation and unresolved threads.
6. Current conversation state.
7. Tempo and interaction-pattern state.
8. Current task state.
9. Relevant room or facility context.
10. Available actions and permissions.

The model receives this package. The model does not own it.

## Separate conversation from intent

Runtime state should distinguish ordinary conversation from actionable intent. Waking Aria or speaking to Aria must not by itself create a task.

Useful states include:
- conversation_active
- actionable_intent_detected
- action_in_progress
- awaiting_required_detail
- action_completed
- conversation_resumed

## Model boundary

Conceptually:

`person -> Aria conversation layer -> context assembly -> model adapter -> model -> action layer -> response`

Provider-specific behavior belongs below the model adapter. Aria identity, memory, continuity, tempo, and conversation rules belong above it.

## Acceptance cases

### Greeting only
User: "Hey Aria."

Valid: natural greeting and room for the user to continue.

Failure: demand a request, present a menu, or force intent extraction.

### Conversation without task
User: "I couldn't sleep last night."

Valid: continue the conversation naturally.

Failure: force the statement into a structured task.

### Embedded action
User: "I couldn't sleep last night. It was freezing in here. Can you turn the heat up two degrees?"

Valid: preserve the conversational thread, detect the actual command, execute or route it, report the result naturally, and stay in conversation afterward.

### Correction or interruption
If the user changes direction or corrects Aria mid-thought, update the interpretation. Do not execute an abandoned phrase as a completed command.

### Silence after greeting
If the user says "Aria," receives a response, and then says nothing, wait. Do not repeatedly solicit a task.

### Model swap
If the underlying provider or model changes, Aria's user-facing identity, continuity, memory, and behavior should remain stable within model capability.

## Success criterion

A user should not feel like they are speaking to a voice-controlled vending machine.

The system succeeds when Aria can simply be present, converse naturally, recognize tasks when they arise, complete them, and continue the same relationship without resetting every interaction into a transaction.

## Implementation principle

**We define Aria. Models generate turns for Aria.**
