from app.agent.graph import graph

initial_state = {"candidate_name": "Shankar Ghimire", "message": ""}

print("\n Starting graph\n")

print(f"Initial state: {initial_state}")

final_state = graph.invoke(initial_state)

print(f"Final state: {final_state}")
