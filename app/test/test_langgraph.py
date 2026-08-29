import asyncio

from app.agent.graph import graph


async def main():

    candidate_id = "6a91bf0fa14af04e089e4734"

    initial_state = {
        "candidate_id": candidate_id,
        "job_id": "",
        "candidate_name": None,
        "candidate_email": None,
        "screening_score": None,
        "screening_rationale": None,
        "decision": None,
        "message": None,
    }

    print("\n Starting hiring graph\n")

    result = await graph.ainvoke(initial_state)

    print("\n==============================")
    print("FINAL GRAPH STATE")
    print("==============================")

    print(result)


if __name__ == "__main__":
    asyncio.run(main())
