from ..servers.database_server import DataStoreAgent
from ..servers.ocr_server import OCRAgent
from ..servers.mapper_server import SchemaMapperAgent
from ..servers.agent_server import AnomalyAgent
from typing import Dict, Any

class MCPClient:
    """
    A unified client to interact with all the local MCP Agent Servers.
    In a real distributed system, this would handle gRPC calls. Here, it
    instantiates the server classes and calls their methods directly.
    """
    def __init__(self):
        self.datastore = DataStoreAgent()
        self.ocr = OCRAgent()
        self.mapper = SchemaMapperAgent()
        self.anomaly = AnomalyAgent()
        print("MCPClient: All agent servers instantiated.")

    def call_tool(self, agent_name: str, tool_name: str, **kwargs) -> Dict[str, Any]:
        """
        Dynamically calls a tool on one of the agents.

        :param agent_name: 'datastore', 'ocr', 'mapper', or 'anomaly'
        :param tool_name: The method name to call, e.g., 'save_metadata'
        :param kwargs: Arguments to pass to the tool method.
        """
        agent = getattr(self, agent_name)
        tool = getattr(agent, tool_name)
        return tool(**kwargs)
