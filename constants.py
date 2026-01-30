import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

# Require at least one API key
if not OPENAI_API_KEY and not ANTHROPIC_API_KEY and not DEEPSEEK_API_KEY:
    raise ValueError("No API key found. Please set DEEPSEEK_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY environment variable or create a .env file.")
