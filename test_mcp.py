#!/usr/bin/env python3
"""
シンプルなMCP接続テスト
"""
import asyncio
import sys
from mcp import ClientSession, StdioServerParameters, stdio_client

async def test_mcp():
    print("Starting MCP connection test...")
    
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["./mcp_server.py"],
        env=None
    )
    
    print("Connecting to MCP server...")
    try:
        async with stdio_client(server_params) as (read, write):
            print("Connected! Creating session...")
            session = ClientSession(read, write)
            
            print("Initializing session...")
            await session.initialize()
            
            print("Listing tools...")
            response = await session.list_tools()
            print(f"Available tools: {[t.name for t in response.tools]}")
            
            print("Testing web_search tool...")
            result = await session.call_tool("web_search", {"query": "test"})
            print(f"Result: {result.content[0].text[:100]}...")
            
            print("✅ MCP test successful!")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_mcp())
