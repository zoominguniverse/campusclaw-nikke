from mcp_scenarios import mcp_servers_create

ORDER = 45
OPERATION_ID = "mcp_servers_create"
MCP_REQUIRED = True

def run(context):
    mcp_servers_create(context)
