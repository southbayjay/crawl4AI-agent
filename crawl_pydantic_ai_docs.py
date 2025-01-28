import os
import sys
import json
import asyncio
import requests
from xml.etree import ElementTree
from typing import List, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import html2text

from openai import AsyncOpenAI
from supabase import create_client, Client
from playwright.async_api import async_playwright

load_dotenv()

# Initialize OpenAI and Supabase clients
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

@dataclass
class ProcessedChunk:
    url: str
    chunk_number: int
    title: str
    summary: str
    content: str
    metadata: Dict[str, Any]
    embedding: List[float]

def chunk_text(text: str, chunk_size: int = 5000) -> List[str]:
    """Split text into chunks, respecting code blocks and paragraphs."""
    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        # Calculate end position
        end = start + chunk_size

        # If we're at the end of the text, just take what's left
        if end >= text_length:
            chunks.append(text[start:].strip())
            break

        # Try to find a code block boundary first (```)
        chunk = text[start:end]
        code_block = chunk.rfind('```')
        if code_block != -1 and code_block > chunk_size * 0.3:
            end = start + code_block

        # If no code block, try to break at a paragraph
        elif '\n\n' in chunk:
            # Find the last paragraph break
            last_break = chunk.rfind('\n\n')
            if last_break > chunk_size * 0.3:  # Only break if we're past 30% of chunk_size
                end = start + last_break

        # If no paragraph break, try to break at a sentence
        elif '. ' in chunk:
            # Find the last sentence break
            last_period = chunk.rfind('. ')
            if last_period > chunk_size * 0.3:  # Only break if we're past 30% of chunk_size
                end = start + last_period + 1

        # Extract chunk and clean it up
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Move start position for next chunk
        start = max(start + 1, end)

    return chunks

async def get_title_and_summary(chunk: str, url: str) -> Dict[str, str]:
    """Extract title and summary using GPT-4."""
    system_prompt = """You are an AI that extracts titles and summaries from documentation chunks.
    Return a JSON object with 'title' and 'summary' keys.
    For the title: If this seems like the start of a document, extract its title. If it's a middle chunk, derive a descriptive title.
    For the summary: Create a concise summary of the main points in this chunk.
    Keep both title and summary concise but informative."""
    
    try:
        response = await openai_client.chat.completions.create(
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"URL: {url}\n\nContent:\n{chunk[:1000]}..."}  # Send first 1000 chars for context
            ],
            response_format={ "type": "json_object" }
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Error getting title and summary: {e}")
        return {"title": "Error processing title", "summary": "Error processing summary"}

async def get_embedding(text: str) -> List[float]:
    """Get embedding vector from OpenAI."""
    try:
        response = await openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error getting embedding: {e}")
        return [0] * 1536  # Return zero vector on error

async def process_chunk(chunk: str, chunk_number: int, url: str) -> ProcessedChunk:
    """Process a single chunk of text."""
    try:
        title, summary = await get_title_and_summary(chunk, url)
        embedding = await get_embedding(chunk)
        
        return ProcessedChunk(
            url=url,
            chunk_number=chunk_number,
            title=title,
            summary=summary,
            content=chunk,
            metadata={
                "source": "python_uv_docs",
                "url": url,
                "chunk_number": chunk_number,
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            embedding=embedding
        )
    except Exception as e:
        print(f"Error processing chunk {chunk_number} from {url}: {str(e)}")
        return None

def get_table_name() -> str:
    """Get the table name from command line arguments."""
    if len(sys.argv) < 2:
        print("Please provide the table name as an argument")
        print("Usage: python crawl_pydantic_ai_docs.py <table_name>")
        sys.exit(1)
    return sys.argv[1]

async def insert_chunk(chunk: ProcessedChunk, table_name: str):
    """Insert a processed chunk into Supabase."""
    try:
        data = {
            'url': chunk.url,
            'chunk_number': chunk.chunk_number,
            'title': chunk.title,
            'summary': chunk.summary,
            'content': chunk.content,
            'metadata': chunk.metadata,
            'embedding': chunk.embedding,
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        
        result = supabase.table(table_name).insert(data).execute()
        print(f"Inserted chunk {chunk.chunk_number} for {chunk.url}")
        return result
    except Exception as e:
        print(f"Error inserting chunk: {e}")
        return None

async def process_and_store_document(url: str, markdown: str, table_name: str):
    """Process a document and store its chunks in parallel."""
    try:
        chunks = chunk_text(markdown)
        tasks = []
        
        for i, chunk in enumerate(chunks):
            processed = await process_chunk(chunk, i, url)
            if processed:
                tasks.append(insert_chunk(processed, table_name))
        
        if tasks:
            await asyncio.gather(*tasks)
            print(f"Processed and stored all chunks for {url}")
    except Exception as e:
        print(f"Error processing document: {e}")

async def crawl_parallel(urls: List[str], table_name: str, max_concurrent: int = 5):
    """Crawl multiple URLs in parallel with a concurrency limit."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_url(url: str):
            async with semaphore:
                try:
                    print(f"Crawling {url}")
                    page = await context.new_page()
                    await page.goto(url)
                    content = await page.content()
                    await page.close()
                    
                    # Convert HTML to markdown
                    soup = BeautifulSoup(content, 'lxml')
                    h = html2text.HTML2Text()
                    h.ignore_links = False
                    markdown = h.handle(str(soup))
                    
                    if markdown:
                        await process_and_store_document(url, markdown, table_name)
                    else:
                        print(f"Failed to get markdown for {url}")
                except Exception as e:
                    print(f"Error processing {url}: {str(e)}")
        
        try:
            tasks = [process_url(url) for url in urls]
            await asyncio.gather(*tasks)
        finally:
            await context.close()
            await browser.close()

async def get_python_uv_urls() -> List[str]:
    """Get URLs from Python UV docs sitemap."""
    try:
        response = requests.get("https://docs.astral.sh/uv/sitemap.xml")
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'xml')
            urls = [loc.text for loc in soup.find_all('loc')]
            return urls
        else:
            print(f"Failed to fetch sitemap: {response.status_code}")
            return []
    except Exception as e:
        print(f"Error fetching sitemap: {str(e)}")
        return []

async def main():
    """Main entry point."""
    table_name = get_table_name()
    
    # Get URLs from sitemap
    urls = await get_python_uv_urls()
    if not urls:
        print("No URLs found in sitemap")
        return
    
    print(f"Starting crawl for {table_name} with {len(urls)} URLs")
    await crawl_parallel(urls, table_name)

if __name__ == "__main__":
    asyncio.run(main())
