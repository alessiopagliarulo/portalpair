"""Configuration for the College Football Analytics pipeline."""
import os

from dotenv import load_dotenv

load_dotenv()

# API endpoints - use apinext for latest, or api for stable
CFBD_BASE_URL = os.getenv("CFBD_BASE_URL", "https://api.collegefootballdata.com")
# Get your API key from https://collegefootballdata.com/key
CFBD_API_KEY = os.getenv("CFBD_API_KEY", "")

# Actian VectorAI DB - https://github.com/hackmamba-io/actian-vectorAI-db-beta
# Docker: docker compose up -> gRPC on localhost:50051
# Use 127.0.0.1 to avoid IPv6/localhost connection issues with Docker
ACTIAN_VECTORAI_HOST = os.getenv("ACTIAN_VECTORAI_HOST", "127.0.0.1:50051")

# ChromaDB - use as primary when USE_CHROMADB=1 (recommended with Python 3.11/3.12)
USE_CHROMADB = os.getenv("USE_CHROMADB", "1").lower() in ("1", "true", "yes")
CHROMA_PERSIST_DIRECTORY = os.getenv("CHROMA_PERSIST_DIRECTORY", "./chroma_backup")

# LLM for coach chatbot - Cerebras
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "")

# Rate limit controls - set TEAM_LIMIT to process fewer teams, FETCH_DELAY between API calls
# PLAYER_LIMIT caps unique players (default 500)
# PLAYERS_PER_TEAM caps players per team for variety (default 50 = ~10 teams for 500)
# API_CALL_LIMIT caps total CFBD API calls (default 1000); each team = 12 calls, fetch_teams = 1
TEAM_LIMIT = int(os.getenv("TEAM_LIMIT", "5")) or None
PLAYERS_PER_TEAM = int(os.getenv("PLAYERS_PER_TEAM", "50")) or None
FETCH_DELAY = float(os.getenv("FETCH_DELAY", "2.0"))
PLAYER_LIMIT = int(os.getenv("PLAYER_LIMIT", "500")) or None
API_CALL_LIMIT = int(os.getenv("API_CALL_LIMIT", "1000")) or None
