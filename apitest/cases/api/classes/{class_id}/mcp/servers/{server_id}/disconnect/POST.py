from mcp_scenarios import mcp_servers_disconnect

ORDER = 51
OPERATION_ID = "mcp_servers_disconnect"
MCP_REQUIRED = True

def run(context):
    mcp_servers_disconnect(context)
