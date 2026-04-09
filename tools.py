import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

BRAVE_SEARCH_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY")
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"

def search_web(query: str):
    """Brave Search API を利用して Web 検索を実行する"""
    if not BRAVE_SEARCH_API_KEY:
        return "Error: Brave Search API key is not set."

    headers = {
        "X-Subscription-Token": BRAVE_SEARCH_API_KEY,
        "Accept": "application/json",
    }
    params = {
        "q": query,
        "count": 3, # 件数を絞って高速化
        "safesearch": "off",
    }

    try:
        response = requests.get(BRAVE_SEARCH_URL, headers=headers, params=params, timeout=5) # 5秒に短縮
        response.raise_for_status()
        data = response.json()

        results = []
        if data and "web" in data and "results" in data["web"]:
            for r in data["web"]["results"]:
                results.append({
                    "title": r.get("title", "No Title"),
                    "url": r.get("url", ""),
                    "snippet": r.get("description", "")
                })
        
        if not results:
            return "検索結果が見つかりませんでした。"
        
        formatted_results = "\n".join([f"- {r['title']} ({r['url']})\n  {r['snippet']}" for r in results])
        return formatted_results
    except Exception as e:
        return f"Error: 検索に失敗しました ({str(e)})"

def fetch_content(url: str):
    """指定された URL から本文テキストを抽出する"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    try:
        response = requests.get(url, headers=headers, timeout=8) # 8秒に短縮
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 不要な要素を削除
        for script_or_style in soup(["script", "style", "nav", "header", "footer", "aside"]):
            script_or_style.decompose()

        # 本文と思われる要素を優先的に取得
        main_content = soup.find('main') or soup.find('article') or soup.find(id='content') or soup.find(class_='content')
        target = main_content if main_content else soup.body
        
        if not target:
            return "エラー: 本文を取得できませんでした。"

        text = target.get_text(separator='\n')
        # 改行と空白の整理
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)

        # 文字数制限
        if len(text) > 5000:
            text = text[:5000] + "..."
            
        return text
    except Exception as e:
        return f"Error: 内容の取得に失敗しました ({str(e)})"

if __name__ == "__main__":
    # Test
    # print(search_web("Apple M4"))
    # print(fetch_content("https://example.com"))
    pass
