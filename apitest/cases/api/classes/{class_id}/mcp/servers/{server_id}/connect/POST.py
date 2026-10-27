from mcp_scenarios import mcp_servers_connect

ORDER = 49
OPERATION_ID = "mcp_servers_connect"
MCP_REQUIRED = True

def run(context):
    mcp_servers_connect(context)
