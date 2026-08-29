from app.agent.graph import graph


candidate = {
    "candidate_id": "candidate_001",
    "job_id": "job_001",
    "screening_score": 84.5,
    "decision": "",
    "message": "",
}


print("\n🚀 Running candidate 001\n")

result = graph.invoke(candidate)

print("\n📤 Final state:")
print(result)
