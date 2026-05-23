import os
import re
from datetime import datetime


def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|《》]', "", name).strip()


def save_outline(outline: str, output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    title_match = re.search(r"#\s*《(.+?)》", outline)
    title = title_match.group(1) if title_match else "故事大纲"
    filename = f"00_大纲_{sanitize_filename(title)}.md"
    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(outline)
    return path


def save_episode(episode_content: str, episode_num: int, output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    title_match = re.search(r"#\s*第\d+集[：:]\s*《?(.+?)》?$", episode_content, re.MULTILINE)
    title = title_match.group(1) if title_match else f"第{episode_num:02d}集"
    filename = f"{episode_num:02d}_第{episode_num}集_{sanitize_filename(title)}.md"
    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(episode_content)
    return path


def save_full_script(outline: str, episodes: list[str], output_dir: str) -> str:
    title_match = re.search(r"#\s*《(.+?)》", outline)
    title = title_match.group(1) if title_match else "剧本"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"完整剧本_{sanitize_filename(title)}_{timestamp}.md"
    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(outline)
        f.write("\n\n---\n\n")
        for ep in episodes:
            f.write(ep)
            f.write("\n\n---\n\n")
    return path


def extract_episode_outlines(outline: str) -> list[str]:
    """Extract per-episode summaries from the full outline."""
    pattern = r"\*\*第(\d+)集[：:].+?\*\*.*?(?=\*\*第\d+集|$)"
    matches = re.findall(pattern, outline, re.DOTALL)
    # Return full block per episode
    blocks = re.split(r"(?=\*\*第\d+集[：:])", outline)
    episode_blocks = [b for b in blocks if re.match(r"\*\*第\d+集", b.strip())]
    return episode_blocks
