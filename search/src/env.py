from dotenv import load_dotenv
import os

load_dotenv()

class Config:
    LLM_MODEL: str = os.getenv("LLM_MODEL")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY")
    LLM_API_BASE_URL: str = os.getenv("LLM_API_BASE_URL")


assert Config.LLM_MODEL, "LLM_MODEL is not set"
assert Config.LLM_API_KEY, "LLM_API_KEY is not set"
assert Config.LLM_API_BASE_URL, "LLM_API_BASE_URL is not set"
