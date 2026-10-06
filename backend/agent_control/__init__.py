"""Agent Control Plane (docs/CAOSCARE_AGENT_CONTROL_PLANE.md).

Owner-only supervision of local Claude workers: an agent registry, a command
queue, and a receipt for every step. Adapters (mock first) sit behind one
interface; the browser only ever names an agent_id.
"""
