import os

from dotenv import load_dotenv
from langchain_community.chat_models.tongyi import ChatTongyi


def get_chat_model() -> ChatTongyi:
    """
    创建通义千问聊天模型。

    注意：
    - embedding 模型负责“找资料”
    - chat 模型负责“根据资料组织答案”

    这里使用 .env 中的 QWEN_CHAT_MODEL。
    """
    load_dotenv()

    api_key = os.getenv("DASHSCOPE_API_KEY")
    model_name = os.getenv("QWEN_CHAT_MODEL", "qwen-turbo")

    if not api_key:
        raise ValueError("缺少 DASHSCOPE_API_KEY，请检查项目根目录下的 .env 文件")

    return ChatTongyi(
        model=model_name,
        dashscope_api_key=api_key,
        temperature=0.2,
    )