import sys
import os
from typing import Dict, List, Optional
from storage.entity.dto import Chat, Message
from storage.repository import chat as chat_repo
from storage.repository.chat import ChatSummary
from storage.cache import cache_chat, get_cached_chat

from storage.util import get_iso8601_timestamp, generate_id

IS_WINDOWS = sys.platform == 'win32'


async def list_chats(limit: int = 10) -> List[ChatSummary]:
    return await chat_repo.list_chats(limit=limit)


async def get_chat(chat_id: str) -> Optional[Chat]:
    return await chat_repo.get_chat(chat_id)


async def create_chat(messages: List[Message], external_id: Optional[str] = None, chat_id: Optional[str] = None) -> Chat:
    timestamp = get_iso8601_timestamp()
    chat = Chat(
        id=chat_id if chat_id else generate_id(),
        create_time=timestamp,
        update_time=timestamp,
        messages=[msg for msg in messages if msg.role != 'system'],
        external_id=external_id
    )
    return await chat_repo.add_chat(chat)


async def update_chat(chat_id: str, messages: List[Message], external_id: Optional[str] = None) -> Chat:
    chat = await get_chat(chat_id)
    if not chat:
        raise ValueError(f"Chat with id {chat_id} not found")
    chat.update_messages(messages)
    chat.external_id = external_id
    return await chat_repo.update_chat(chat)


# ---------------------------------------------------------------------------
# Cache-aware methods (for API/worker use)
# ---------------------------------------------------------------------------

async def create_chat_with_cache(
    messages: List[Message],
    chat_id: Optional[str] = None,
    status: Optional[str] = None,
    bot_name: Optional[str] = None,
    prompt: Optional[str] = None,
) -> Chat:
    """Create chat in DB and populate cache."""
    timestamp = get_iso8601_timestamp()
    chat = Chat(
        id=chat_id if chat_id else generate_id(),
        create_time=timestamp,
        update_time=timestamp,
        messages=[msg for msg in messages if msg.role != 'system'],
        status=status,
        bot_name=bot_name,
    )
    chat = await chat_repo.add_chat(chat)
    # Populate cache with chat data + transient fields
    cache_data: Dict = chat.to_dict()
    if prompt:
        cache_data["prompt"] = prompt
    cache_chat(chat.id, cache_data)
    return chat


async def get_chat_with_cache(chat_id: str) -> Optional[Dict]:
    """Cache-aside read: check cache first, fallback to DB, backfill cache."""
    cached = get_cached_chat(chat_id)
    if cached:
        return cached
    chat = await chat_repo.get_chat(chat_id)
    if not chat:
        return None
    cache_data = chat.to_dict()
    cache_chat(chat_id, cache_data)
    return cache_data


async def update_chat_with_cache(chat_id: str, messages: List[Message], status: Optional[str] = None) -> Chat:
    """Update chat in DB and refresh cache."""
    chat = await get_chat(chat_id)
    if not chat:
        raise ValueError(f"Chat with id {chat_id} not found")
    chat.update_messages(messages)
    if status is not None:
        chat.status = status
    chat = await chat_repo.update_chat(chat)
    cache_data = chat.to_dict()
    cache_chat(chat_id, cache_data)
    return chat


async def delete_chat(chat_id: str) -> bool:
    return await chat_repo.delete_chat(chat_id)


async def generate_share_html(chat_id: str) -> str:
    home = os.path.expanduser(os.environ.get("Y_AGENT_HOME", "~/.y-agent"))
    tmp_dir = os.path.join(home, "tmp")
    chat = await get_chat(chat_id)
    if not chat:
        raise ValueError(f"Chat with id {chat_id} not found")

    # Generate table of contents
    toc_content = '<div class="toc">\n<h3>Table of Contents</h3>\n<ul>\n'

    # Generate markdown content with anchors for TOC
    md_content = f'<div class="content-wrapper">\n\n# Chat {chat_id}\n\n'

    msg_index = 0
    for msg in chat.messages:
        if msg.role == 'system':
            continue

        msg_index += 1
        msg_id = f"msg-{msg_index}"

        header = msg.role.capitalize()
        if msg.model or msg.provider:
            model_info = []
            if msg.model:
                model_info.append(msg.model)
            if msg.provider:
                model_info.append(f"via {msg.provider}")
            header += f" <span class='model-info'>({' '.join(model_info)})</span>"

        message_preview = msg.content[:20] + "..." if len(msg.content) > 20 else msg.content
        toc_content += f'<li><a href="#{msg_id}">{msg.role.capitalize()}: {message_preview}</a></li>\n'

        content = msg.content
        section_content = content

        import re
        webpage_sections = re.findall(r'\[webpage (\d+) begin\](.*?)\[webpage \1 end\]', content, re.DOTALL)

        if webpage_sections:
            toc_content += '<ul>\n'
            for section_num, section_text in webpage_sections:
                section_lines = section_text.strip().split('\n')
                section_title = section_lines[0].strip() if section_lines else f"Section {section_num}"

                section_id = f"{msg_id}-section-{section_num}"
                toc_content += f'<li><a href="#{section_id}">{section_title}</a></li>\n'

                section_replacement = f'<details id="{section_id}">\n<summary>{section_title}</summary>\n<div class="webpage-section">\n\n{section_text}\n\n</div></details>'
                section_content = section_content.replace(f'[webpage {section_num} begin]{section_text}[webpage {section_num} end]', section_replacement)

            toc_content += '</ul>\n'

        md_content += f'<h2 id="{msg_id}">{header}</h2>\n\n'

        if msg.reasoning_content:
            md_content += f'<details><summary>Reasoning</summary><div class="reasoning-content">\n\n{msg.reasoning_content}\n\n</div></details>\n\n'

        md_content += f"{section_content}\n\n"
        md_content += f"*{msg.timestamp}*\n\n---\n\n"

    md_content += '</div>\n'
    toc_content += '</ul>\n</div>\n'

    os.makedirs(tmp_dir, exist_ok=True)

    md_file = os.path.join(tmp_dir, f"{chat_id}.md")
    html_file = os.path.join(tmp_dir, f"{chat_id}.html")
    temp_html = os.path.join(tmp_dir, f"{chat_id}_temp.html")

    with open(md_file, "w", encoding="utf-8") as f:
        f.write(md_content)

    css = '''
<style>
body {
    max-width: 1200px;
    margin: 0 auto;
    padding: 2rem;
    font-family: system-ui, -apple-system, sans-serif;
    line-height: 1.6;
    position: relative;
}
.content-wrapper {
    max-width: 800px;
    margin: 0 auto;
    margin-left: 220px;
}
.toc {
    width: 180px;
    position: fixed;
    left: 20px;
    top: 2rem;
    max-height: calc(100vh - 4rem);
    overflow-y: auto;
    padding: 1rem;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 0.5rem;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
}
.toc h3 { margin-top: 0; padding-bottom: 0.5rem; border-bottom: 1px solid #e2e8f0; }
.toc ul { list-style-type: none; padding-left: 0.5rem; margin-top: 0.5rem; }
.toc li { margin-bottom: 0.5rem; font-size: 0.875rem; }
.toc ul ul { margin-top: 0; padding-left: 1rem; }
.toc ul ul li { margin-bottom: 0.25rem; font-size: 0.8125rem; }
.toc a { color: #4b5563; text-decoration: none; display: block; padding: 0.25rem 0.5rem; border-radius: 0.25rem; }
.toc a:hover { color: #2563eb; background: #f1f5f9; }
h1 { border-bottom: 2px solid #eee; padding-bottom: 0.5rem; }
h2 { margin-top: 2rem; color: #2563eb; scroll-margin-top: 2rem; }
h3 { color: #4b5563; }
sup { color: #6b7280; }
hr { margin: 2rem 0; border: 0; border-top: 1px solid #eee; }
.references { background: #f9fafb; padding: 1rem; border-radius: 0.5rem; }
.images { margin: 1rem 0; }
details { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 0.5rem; margin: 1rem 0; padding: 0.5rem; }
summary { cursor: pointer; font-weight: 500; color: #4b5563; }
details[open] summary { margin-bottom: 1rem; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.5rem; }
.reasoning-content, .webpage-section { padding: 0.5rem; color: #4b5563; }
.webpage-section { margin-top: 0.5rem; margin-bottom: 0.5rem; }
.model-info { font-size: 0.875rem; font-weight: normal; color: #6b7280; }
code { background: #f1f5f9; border-radius: 0.25rem; padding: 0.2rem 0.4rem; font-size: 0.875rem; }
pre { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 0.5rem; padding: 1rem; overflow-x: auto; margin: 1rem 0; }
@media (max-width: 1024px) {
    body { display: block; }
    .content-wrapper { max-width: 100%; margin: 0 auto; margin-left: 0; }
    .toc { position: relative; width: auto; max-width: 800px; margin: 0 auto 2rem auto; left: auto; top: auto; }
}
</style>
'''

    css_file = os.path.join(tmp_dir, f"{chat_id}.css")
    with open(css_file, "w", encoding="utf-8") as f:
        f.write(css)

    pandoc_cmd = 'pandoc'
    if IS_WINDOWS:
        pandoc_cmd = os.path.expanduser('~/AppData/Local/Pandoc/pandoc')

    os.system(f'{pandoc_cmd} "{md_file}" -o "{temp_html}" -s --metadata title="{chat_id}" --metadata charset="UTF-8" --include-in-header="{css_file}"')

    with open(temp_html, 'r', encoding='utf-8') as f:
        pandoc_html = f.read()

    import re
    body_content = re.search(r'<body>(.*?)</body>', pandoc_html, re.DOTALL)
    content_html = body_content.group(1) if body_content else pandoc_html

    final_html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{chat_id}</title>
    {css}
</head>
<body>
    {toc_content}
    <div class="content-wrapper">
        {content_html}
    </div>
</body>
</html>
'''

    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(final_html)

    os.remove(css_file)
    os.remove(md_file)
    os.remove(temp_html)

    return html_file
