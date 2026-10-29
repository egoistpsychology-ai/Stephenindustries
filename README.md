# Stephen Industries

1. Create a virtual environment: `python -m venv .venv` and activate it.
2. Install dependencies: `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and add `GROQ_API_KEY` and `DEEPSEEK_API_KEY`.
4. Run `uvicorn backend.main:app --reload`.
5. Open http://localhost:8000.
