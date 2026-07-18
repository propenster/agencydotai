"""Agency module for dotagency."""

from .agency import BaseAgent
from .broker import MemoryBroker
from .loader import AgencyLoader

# We expose the FastAPI app instance if developers need to mount it 
# into an existing server, rather than an 'API' class.
from .api import app as oversight_app 

__all__ = [
    'BaseAgent',
    'MemoryBroker',
    'AgencyLoader',
    'oversight_app',
]