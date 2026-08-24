                 Final DecisionCandidate
│
▼
Resume Upload
│
▼
Resume Parser
│
▼
Structured Data
│
┌─────────┴─────────┐
▼ ▼
MongoDB Embedding
│ │
│ ▼
│ Qdrant
│ │
└─────────┬─────────┘
▼
Hiring Agent
│
┌────────┼────────┐
▼ ▼ ▼
Screening Matching Interview
│ │ │
└────────┼────────┘
▼
Final Decision

React / HR Dashboard
│
▼
┌─────────────┐
│ FastAPI │
└──────┬──────┘
│
┌───────────────────┼────────────────────┐
│ │ │
▼ ▼ ▼
MongoDB Qdrant AI Agent
│ │ │
│ │ ┌──────┴──────┐
│ │ │ │
│ │ LangChain Ollama
│ │ │ │
│ │ └──────┬──────┘
│ │ │
└───────────────────┴────────────────────┘
│
▼
Hiring Decision Engine
│
┌─────────────┼──────────────┐
▼ ▼ ▼
Screening Ranking Interview
