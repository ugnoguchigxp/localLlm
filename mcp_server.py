#!/usr/bin/env python3
"""
Gemma 4 用 MCP Server
Brave Search と Web スクレイピング機能を提供
"""
import asyncio
from typing import Any
from dotenv import load_dotenv
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp import stdio_server
from tools import search_web, fetch_content

load_dotenv()

# MCPサーバーインスタンス
app = Server("gemma4-tools")

@app.list_tools()
async def list_tools() -> list[Tool]:
    """利用可能なツールのリストを返す"""
    return [
        Tool(
            name="web_search",
            description="最新の情報を取得するためにウェブ検索を行います。Brave Search APIを使用します。",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "検索クエリ",
                    }
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="fetch_content",
            description="指定されたURLから詳細なテキスト情報を取得します。検索結果からより深い情報を得る際に使用します。",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "取得対象のURL",
                    }
                },
                "required": ["url"],
            },
        ),
    ]

@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """ツール実行ハンドラ"""
    
    if name == "web_search":
        query = arguments.get("query", "")
        if not query:
            return [TextContent(type="text", text="Error: query parameter is required")]
        
        # 同期関数を非同期コンテキストで実行
        result = await asyncio.to_thread(search_web, query)
        return [TextContent(type="text", text=result)]
    
    elif name == "fetch_content":
        url = arguments.get("url", "")
        if not url:
            return [TextContent(type="text", text="Error: url parameter is required")]
        
        # 同期関数を非同期コンテキストで実行
        result = await asyncio.to_thread(fetch_content, url)
        return [TextContent(type="text", text=result)]
    
    else:
        return [TextContent(type="text", text=f"Error: Unknown tool '{name}'")]

async def main():
    """MCPサーバーをstdio経由で起動"""
    async with stdio_server() as streams:
        await app.run(
            streams[0],
            streams[1],
            app.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
