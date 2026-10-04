"""CAOSCare Operations Simulator (docs/CAOSCARE_OPERATIONS_SIMULATOR.md).

SIM-1: roster.py (simulated actors), scenario.py (deterministic steps, each
a call into a canonical service), scheduler.py (run state, controls,
run-chain receipts). The HTTP control surface is routes/simulation.py.
Nothing in this package writes a StaffTask or a task receipt itself.
"""
