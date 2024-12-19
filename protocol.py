from dataclasses import dataclass
from typing import Dict, Any, Optional

@dataclass
class Conference:
    id: str
    name: str    
    creator_id: str
    participants: Dict[str, str]  # client_id: client_name
    max_participants: int = 10
    
    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Conference':
        return cls(**data)