from fastmcp import FastMCP

# Create an MCP server instance
mcp = FastMCP(name="ShippingTrackerServer")

@mcp.tool
def get_package_status(tracking_id: str) -> str:
    """Gets the status of a shipping package."""
    print(f"--- Shipping Server: Received request for tracking ID: {tracking_id} ---")
    # In a real application, this would call a shipping carrier's API.
    # For this simulation, we'll just return a hardcoded status.
    return f"Your package with tracking ID {tracking_id} is currently in transit in Memphis, TN."

if __name__ == "__main__":
    # This will run the MCP server over stdio
    print("--- External Shipping Tracker MCP Server is running --- ")
    mcp.run()