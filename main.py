#!/usr/bin/env python3
"""短视频剧本生成器 - 古装/玄幻专项"""

import os
import sys
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.markdown import Markdown
from rich.rule import Rule

from generator import generate_outline, generate_episode, refine_content, chat_with_user
from exporter import save_outline, save_episode, save_full_script, extract_episode_outlines

console = Console()


def print_banner():
    console.print(Panel.fit(
        "[bold cyan]✦ 短视频剧本生成器 ✦[/bold cyan]\n"
        "[dim]古装 / 玄幻 短剧专项[/dim]",
        border_style="cyan",
    ))


def collect_requirements() -> tuple[str, int]:
    """Interactive chat to gather story requirements."""
    console.print(Rule("[cyan]第一步：聊聊你的故事想法[/cyan]"))
    console.print("[dim]先告诉我你想要什么样的故事，我会帮你完善细节。输入 q 跳过对话直接描述需求。[/dim]\n")

    messages = []
    requirements_summary = ""

    # Initial greeting from AI
    messages.append({
        "role": "user",
        "content": "你好，我想创作一个古装/玄幻短视频剧本，请帮我完善故事想法。"
    })
    console.print("[bold cyan]助手[/bold cyan]：", end="")
    response = chat_with_user(messages)
    messages.append({"role": "assistant", "content": response})

    while True:
        user_input = Prompt.ask("\n[bold yellow]你[/bold yellow]")
        if user_input.lower() == "q":
            break

        messages.append({"role": "user", "content": user_input})
        console.print("\n[bold cyan]助手[/bold cyan]：", end="")
        response = chat_with_user(messages)
        messages.append({"role": "assistant", "content": response})

        if "✅" in response or "信息已足够" in response:
            break

    # Build requirements summary from conversation
    if len(messages) > 2:
        summary_messages = messages + [{
            "role": "user",
            "content": "请用200字以内总结我的故事需求，格式：主角设定、世界观、核心矛盾、情感基调、爽点关键词。"
        }]
        console.print("\n[dim]正在整理需求...[/dim]")
        requirements_summary = chat_with_user(summary_messages)
    else:
        requirements_summary = Prompt.ask("\n[bold]请直接描述你的故事需求")

    console.print()
    episode_count = IntPrompt.ask(
        "[bold]要生成几集？[/bold] [dim](建议10-20集)[/dim]",
        default=15,
    )
    return requirements_summary, episode_count


def outline_phase(requirements: str, episode_count: int) -> str:
    """Generate and optionally refine the story outline."""
    console.print(Rule("[cyan]第二步：生成故事大纲[/cyan]"))
    console.print("[dim]正在为你创作大纲...[/dim]\n")

    outline = generate_outline(requirements, episode_count)

    while True:
        console.print()
        action = Prompt.ask(
            "[bold]大纲满意吗？[/bold]",
            choices=["继续", "修改", "重新生成"],
            default="继续",
        )
        if action == "继续":
            break
        elif action == "重新生成":
            console.print("[dim]重新生成中...[/dim]")
            outline = generate_outline(requirements, episode_count)
        else:
            feedback = Prompt.ask("请描述你想修改的地方")
            console.print("[dim]修改中...[/dim]")
            outline = refine_content(outline, feedback)

    return outline


def episodes_phase(outline: str, episode_count: int, output_dir: str) -> list[str]:
    """Generate episode scripts interactively."""
    console.print(Rule("[cyan]第三步：生成分集剧本[/cyan]"))

    episode_outlines = extract_episode_outlines(outline)
    episodes = []

    # Choose generation mode
    mode = Prompt.ask(
        "[bold]生成方式[/bold]",
        choices=["全部自动生成", "逐集确认"],
        default="逐集确认",
    )

    # Determine which episodes to generate
    if mode == "全部自动生成":
        episode_range = range(1, episode_count + 1)
    else:
        start = IntPrompt.ask("从第几集开始生成？", default=1)
        end = IntPrompt.ask("生成到第几集？", default=min(5, episode_count))
        episode_range = range(start, end + 1)

    for ep_num in episode_range:
        console.print(f"\n[bold cyan]▶ 正在生成第 {ep_num} 集...[/bold cyan]")

        ep_outline = episode_outlines[ep_num - 1] if ep_num <= len(episode_outlines) else f"第{ep_num}集"
        episode_content = generate_episode(outline, ep_num, ep_outline)

        # Save immediately
        path = save_episode(episode_content, ep_num, output_dir)
        console.print(f"[green]✓ 已保存：{path}[/green]")
        episodes.append(episode_content)

        if mode == "逐集确认" and ep_num < max(episode_range):
            action = Prompt.ask(
                "  继续下一集？",
                choices=["继续", "修改本集", "停止"],
                default="继续",
            )
            if action == "停止":
                break
            elif action == "修改本集":
                feedback = Prompt.ask("  请描述修改意见")
                episode_content = refine_content(episode_content, feedback)
                episodes[-1] = episode_content
                save_episode(episode_content, ep_num, output_dir)
                console.print(f"[green]✓ 已更新第 {ep_num} 集[/green]")

    return episodes


def main():
    load_dotenv()
    print_banner()

    missing = [k for k in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL_ID") if not os.environ.get(k)]
    if missing:
        console.print(f"[bold red]错误：.env 文件缺少以下配置：{', '.join(missing)}[/bold red]")
        console.print("  请参考 .env.example 填写配置")
        sys.exit(1)

    output_dir = Prompt.ask(
        "\n[bold]剧本保存目录[/bold]",
        default="./scripts",
    )

    # Phase 1: Collect requirements
    requirements, episode_count = collect_requirements()

    # Phase 2: Generate outline
    outline = outline_phase(requirements, episode_count)
    outline_path = save_outline(outline, output_dir)
    console.print(f"\n[green]✓ 大纲已保存：{outline_path}[/green]")

    # Phase 3: Generate episodes
    episodes = episodes_phase(outline, episode_count, output_dir)

    # Save full script if episodes were generated
    if episodes:
        full_path = save_full_script(outline, episodes, output_dir)
        console.print(f"\n[bold green]✓ 完整剧本已保存：{full_path}[/bold green]")

    console.print(Panel.fit(
        f"[bold green]创作完成！[/bold green]\n"
        f"共生成 {len(episodes)} 集剧本\n"
        f"保存目录：{output_dir}",
        border_style="green",
    ))


if __name__ == "__main__":
    main()
