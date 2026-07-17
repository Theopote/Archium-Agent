import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env file")

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_MODEL = "gemini-2.5-flash"

ARCHIUM_IDENTITY = """\
你是 Archium（阿基姆），一位资深的架构与知识管理智能体——名字寓意 Architecture（建筑）与 Museum（博物馆）的结合，既关注空间与结构的秩序，也重视知识的归档与呈现。
你的语气像一位专业、冷静、高效的建筑师助理：表述精准、条理分明、直奔要点，不使用浮夸或多余的寒暄。
"""

client = OpenAI(
    api_key=GEMINI_API_KEY,
    base_url=GEMINI_BASE_URL,
)
