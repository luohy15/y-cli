from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Union, Iterable
from datetime import datetime
from util import get_iso8601_timestamp

@dataclass
class ContentPart:
    text: str
    type: str = "text"

@dataclass
class Message:
    role: str
    content: Union[str, Iterable[ContentPart]]
    timestamp: str
    unix_timestamp: int
    reasoning_content: Optional[str] = None
    reasoning_effort: Optional[str] = None
    links: Optional[List[str]] = None
    images: Optional[List[str]] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    id: Optional[str] = None
    server: Optional[str] = None
    tool: Optional[str] = None
    arguments: Optional[Dict[str, Union[str, int, float, bool, Dict, List]]] = None

    @classmethod
    def from_dict(cls, data: Dict) -> 'Message':
        # Get or generate unix_timestamp
        unix_timestamp = data.get('unix_timestamp')
        if unix_timestamp is None:
            # Convert ISO timestamp to unix timestamp
            dt = datetime.strptime(data['timestamp'].split('+')[0], "%Y-%m-%dT%H:%M:%S")
            unix_timestamp = int(dt.timestamp() * 1000)

        # Handle content which can be str or list of content parts
        content = data['content']
        if isinstance(content, list):
            # Convert dict content parts to ContentPart objects
            content = [ContentPart(**part) if isinstance(part, dict) else part for part in content]

        return cls(
            role=data['role'],
            content=content,  # Keep original structure (str or list)
            reasoning_content=data.get('reasoning_content'),
            reasoning_effort=data.get('reasoning_effort'),
            timestamp=data['timestamp'],
            unix_timestamp=unix_timestamp,
            provider=data.get('provider'),
            links=data.get('links'),
            images=data.get('images'),
            model=data.get('model'),
            id=data.get('id'),
            server=data.get('server'),
            tool=data.get('tool'),
            arguments=data.get('arguments')
        )

    def to_dict(self) -> Dict:
        # Filter out cache_control from content if it's a list of parts
        if isinstance(self.content, list):
            content = [{'type': part.type, 'text': part.text} for part in self.content]
        else:
            content = self.content

        result = {
            'role': self.role,
            'content': content,
            'timestamp': self.timestamp,
            'unix_timestamp': self.unix_timestamp
        }
        if self.reasoning_content is not None:
            result['reasoning_content'] = self.reasoning_content
        if self.reasoning_effort is not None:
            result['reasoning_effort'] = self.reasoning_effort
        if self.id is not None:
            result['id'] = self.id
        if self.links is not None:
            result['links'] = self.links
        if self.images is not None:
            result['images'] = self.images
        if self.model is not None:
            result['model'] = self.model
        if self.provider is not None:
            result['provider'] = self.provider
        if self.server is not None:
            result['server'] = self.server
        if self.tool is not None:
            result['tool'] = self.tool
        if self.arguments is not None:
            result['arguments'] = self.arguments
        return result

@dataclass
class Chat:
    id: str
    create_time: str
    update_time: str
    messages: List[Message]
    external_id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict) -> 'Chat':
        return cls(
            id=data['id'],
            create_time=data['create_time'],
            update_time=data['update_time'],
            messages=sorted(
                [Message.from_dict(m) for m in data['messages'] if m['role'] != 'system'],
                key=lambda x: (x.unix_timestamp)
            ),
            external_id=data.get('external_id')
        )

    def to_dict(self) -> Dict:
        result = {
            'create_time': self.create_time,
            'id': self.id,
            'update_time': self.update_time,
            'messages': [m.to_dict() for m in self.messages]
        }
        if self.external_id is not None:
            result['external_id'] = self.external_id
        return result

    def update_messages(self, messages: List[Message]) -> None:
        # Filter out system messages and sort the remaining ones by timestamp
        self.messages = sorted(
            [msg for msg in messages if msg.role != 'system'],
            key=lambda x: (x.unix_timestamp)
        )
        self.update_time = get_iso8601_timestamp()
