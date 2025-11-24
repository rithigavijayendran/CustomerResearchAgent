"""
Session memory management
Maintains context across agent interactions
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)

class SessionMemory:
    """Manage session memory for the agent"""
    
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}
    
    def create_session(self, session_id: Optional[str] = None) -> str:
        """Create a new session"""
        if not session_id:
            session_id = str(uuid.uuid4())
        
        self.sessions[session_id] = {
            'id': session_id,
            'created_at': datetime.now().isoformat(),
            'messages': [],
            'company_name': None,
            'account_plan': None,
            'research_data': [],
            'conflicts': [],
            'questions_asked': [],
            'agent_state': 'idle'
        }
        
        logger.info(f"Created session: {session_id}")
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data"""
        return self.sessions.get(session_id)
    
    def add_message(self, session_id: str, role: str, content: str):
        """Add a message to session"""
        if session_id not in self.sessions:
            self.create_session(session_id)
        
        self.sessions[session_id]['messages'].append({
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat()
        })
    
    def set_company_name(self, session_id: str, company_name: str):
        """Set company name for session"""
        if session_id not in self.sessions:
            self.create_session(session_id)
        
        self.sessions[session_id]['company_name'] = company_name
    
    def add_research_data(self, session_id: str, data: Dict[str, Any]):
        """Add research data to session"""
        if session_id not in self.sessions:
            self.create_session(session_id)
        
        self.sessions[session_id]['research_data'].append(data)
    
    def set_account_plan(self, session_id: str, account_plan: Dict[str, Any]):
        """Set account plan for session"""
        if session_id not in self.sessions:
            self.create_session(session_id)
        
        self.sessions[session_id]['account_plan'] = account_plan
    
    def add_conflict(self, session_id: str, conflict: Dict[str, Any]):
        """Add detected conflict"""
        if session_id not in self.sessions:
            self.create_session(session_id)
        
        self.sessions[session_id]['conflicts'].append(conflict)
    
    def add_question(self, session_id: str, question: str):
        """Add question asked to user"""
        if session_id not in self.sessions:
            self.create_session(session_id)
        
        self.sessions[session_id]['questions_asked'].append({
            'question': question,
            'timestamp': datetime.now().isoformat()
        })
    
    def set_agent_state(self, session_id: str, state: str):
        """Set agent state"""
        if session_id not in self.sessions:
            self.create_session(session_id)
        
        self.sessions[session_id]['agent_state'] = state
    
    def get_conversation_history(self, session_id: str, limit: int = 10) -> List[Dict]:
        """Get recent conversation history"""
        session = self.get_session(session_id)
        if not session:
            return []
        
        messages = session.get('messages', [])
        return messages[-limit:] if len(messages) > limit else messages

