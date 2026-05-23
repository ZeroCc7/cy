import os
from openai import OpenAI
from dotenv import load_dotenv
from prompts import OUTLINE_SYSTEM, OUTLINE_PROMPT, EPISODE_SYSTEM, EPISODE_PROMPT, REFINE_PROMPT

load_dotenv()

client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=os.environ["OPENAI_BASE_URL"],
)
MODEL = os.environ["OPENAI_MODEL_ID"]


def stream_print(response) -> str:
    full_text = ""
    for chunk in response:
        text = chunk.choices[0].delta.content or ""
        print(text, end="", flush=True)
        full_text += text
    print()
    return full_text


def _chat(system: str, messages: list, max_tokens: int = 4000) -> str:
    print()
    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=max_tokens,
        stream=True,
        messages=[{"role": "system", "content": system}] + messages,
    )
    return stream_print(response)


def generate_outline(requirements: str, episode_count: int = 15) -> str:
    prompt = OUTLINE_PROMPT.format(requirements=requirements, episode_count=episode_count)
    return _chat(OUTLINE_SYSTEM, [{"role": "user", "content": prompt}], max_tokens=4000)


def generate_episode(
    outline: str,
    episode_num: int,
    episode_outline: str,
    duration_min: int = 1,
    duration_max: int = 3,
) -> str:
    words_per_min = 200
    prompt = EPISODE_PROMPT.format(
        episode_num=episode_num,
        outline=outline,
        episode_outline=episode_outline,
        duration_min=duration_min,
        duration_max=duration_max,
        word_count_min=duration_min * words_per_min,
        word_count_max=duration_max * words_per_min,
    )
    return _chat(EPISODE_SYSTEM, [{"role": "user", "content": prompt}], max_tokens=3000)


def refine_content(current_content: str, feedback: str) -> str:
    from prompts import REFINE_PROMPT
    prompt = REFINE_PROMPT.format(feedback=feedback, current_content=current_content)
    return _chat(
        "你是专业短视频剧本编剧，根据用户反馈修改内容，保持风格一致。",
        [{"role": "user", "content": prompt}],
        max_tokens=4000,
    )


def chat_with_user(messages: list) -> str:
    system = """你是一个短视频剧本创作助手，专注于古装/玄幻类型。

通过友好对话收集用户的故事需求：主角设定、故事核心（复仇/逆袭/爱情/成长）、世界观（修仙/宫廷/江湖）、情感基调、想要的爽点。

每次最多问2个问题，聊天式交流。
当信息足够时，回复最后一行写：「✅ 信息已足够，准备生成大纲！」"""
    return _chat(system, messages, max_tokens=800)
