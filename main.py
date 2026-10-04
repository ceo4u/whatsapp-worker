import os
import re
import asyncio
import uuid
from fastapi import FastAPI, BackgroundTasks, HTTPException
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import tiktoken
import psycopg2
from psycopg2.extras import execute_values
from pgvector.psycopg2 import register_vector
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Crawler Worker (Neon Postgres + pgvector)")

DATABASE_URL = os.getenv("DATABASE_URL")
enc = tiktoken.get_encoding("cl100k_base")


import time

def get_db_connection():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL not configured.")
    max_retries = 3
    for attempt in range(max_retries):
        try:
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
            register_vector(conn)
            return conn
        except psycopg2.OperationalError as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(2)


BLOCKED_KEYWORDS = [
    "login", "signup", "sign-up", "cart", "checkout", "admin",
    "account", "logout", ".pdf", ".jpg", ".jpeg", ".png", ".gif",
    ".zip", ".mp4", ".mp3", ".svg", ".webp", "mailto:", "tel:"
]


def is_valid_url(url: str, base: str) -> bool:
    try:
        parsed = urlparse(url)
        base_parsed = urlparse(base)
        if parsed.netloc != base_parsed.netloc:
            return False
        if any(kw in url.lower() for kw in BLOCKED_KEYWORDS):
            return False
        return True
    except Exception:
        return False


async def fetch_sitemap(base: str) -> list:
    urls = set()
    candidates = ["/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml"]
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        for path in candidates:
            try:
                r = await client.get(base.rstrip("/") + path)
                if r.status_code == 200:
                    locs = re.findall(r"<loc>(.*?)</loc>", r.text)
                    for loc in locs:
                        if is_valid_url(loc, base):
                            urls.add(loc)
                    if urls:
                        break
            except Exception:
                continue
    return list(urls)


async def discover_links(base: str) -> list:
    urls = {base}
    async with httpx.AsyncClient(
        timeout=20,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; AIAgentBot/1.0)"}
    ) as client:
        try:
            r = await client.get(base)
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                full = urljoin(base, a["href"]).split("#")[0].rstrip("/")
                if is_valid_url(full, base):
                    urls.add(full)
        except Exception:
            pass
    return list(urls)[:40]


async def scrape_page(url: str) -> dict:
    async with httpx.AsyncClient(
        timeout=25,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; AIAgentBot/1.0)"}
    ) as client:
        r = await client.get(url)
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header",
                          "noscript", "iframe", "aside", "form"]):
            tag.decompose()
        title = soup.title.string.strip() if soup.title and soup.title.string else url
        text = soup.get_text("\n", strip=True)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return {"url": url, "title": title, "markdown": text}


def chunk_text(text: str, size: int = 800, overlap: int = 100) -> list:
    tokens = enc.encode(text)
    chunks = []
    i = 0
    while i < len(tokens):
        chunk_tokens = tokens[i:i + size]
        chunk_str = enc.decode(chunk_tokens).strip()
        if len(chunk_str) > 100:
            chunks.append(chunk_str)
        i += size - overlap
    return chunks


def embed_texts(texts: list) -> list:
    if not texts:
        return []
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise Exception("GEMINI_API_KEY not set")
    
    embeddings = []
    for text in texts:
        res = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={api_key}",
            json={
                "model": "models/gemini-embedding-001",
                "content": {"parts": [{"text": text}]},
                "outputDimensionality": 768
            },
            timeout=30
        )
        if res.status_code != 200:
            raise Exception(f"Gemini embed failed: {res.text}")
        data = res.json()
        embeddings.append(data["embedding"]["values"])
    return embeddings




def update_company_status(company_id: str, status: str):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE companies SET status = %s WHERE id = %s", (status, company_id))
        conn.commit()
    finally:
        conn.close()


async def ingest_company(company_id: str, base_url: str):
    try:
        update_company_status(company_id, "crawling")

        urls = await fetch_sitemap(base_url)
        if len(urls) < 3:
            urls = await discover_links(base_url)

        if not urls:
            urls = [base_url]

        total_pages = 0
        total_chunks = 0

        conn = get_db_connection()
        try:
            for url in urls:
                try:
                    page = await scrape_page(url)
                    if len(page["markdown"].strip()) < 50:
                        continue


                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO company_pages (company_id, url, title, raw_markdown)
                            VALUES (%s, %s, %s, %s)
                            RETURNING id
                            """,
                            (company_id, page["url"], page["title"], page["markdown"])
                        )
                        page_id = cur.fetchone()[0]

                        chunks = chunk_text(page["markdown"])
                        if not chunks:
                            continue

                        vectors = embed_texts(chunks)

                        rows = [
                            (
                                company_id,
                                page_id,
                                page["url"],
                                ch,
                                len(enc.encode(ch)),
                                vec
                            )
                            for ch, vec in zip(chunks, vectors)
                        ]

                        execute_values(
                            cur,
                            """
                            INSERT INTO company_docs (company_id, page_id, url, content, token_count, embedding)
                            VALUES %s
                            """,
                            rows
                        )
                    conn.commit()

                    total_pages += 1
                    total_chunks += len(chunks)
                    print(f"[OK] {url} -> {len(chunks)} chunks", flush=True)

                except Exception as e:
                    conn.rollback()
                    print(f"[SKIP] {url}: {e}", flush=True)
                    continue
        finally:
            conn.close()

        update_company_status(company_id, "ready")
        print(f"[DONE] company={company_id} pages={total_pages} chunks={total_chunks}", flush=True)

    except Exception as e:
        print(f"[ERROR] company={company_id}: {e}", flush=True)
        try:
            update_company_status(company_id, "error")
        except:
            pass



@app.get("/")
def root():
    return {"status": "ok", "service": "crawler-worker-neon"}


@app.post("/ingest")
async def ingest(payload: dict):
    """Queue crawl job — returns immediately"""
    company_id = payload.get("company_id")
    url = payload.get("url")

    if not company_id or not url:
        raise HTTPException(status_code=400, detail="company_id and url required")

    job_id = str(uuid.uuid4())

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO crawl_jobs (id, company_id, url, status, created_at)
                VALUES (%s, %s, %s, 'pending', NOW())
            """, (job_id, company_id, url))
        conn.commit()
    finally:
        conn.close()

    return {"job_id": job_id, "status": "queued"}


@app.api_route("/worker/tick", methods=["GET", "POST"])
async def worker_tick():
    """Called by cron every minute — processes 1 job"""
    job = None
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, company_id, url FROM crawl_jobs
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            """)
            job = cur.fetchone()

            if not job:
                return {"status": "no_jobs"}

            job_id, company_id, url = job

            cur.execute("""
                UPDATE crawl_jobs SET status = 'processing' WHERE id = %s
            """, (job_id,))
        conn.commit()
    finally:
        conn.close()

    try:
        await asyncio.wait_for(
            ingest_company(str(company_id), url),
            timeout=50
        )

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE crawl_jobs SET status = 'done', completed_at = NOW()
                    WHERE id = %s
                """, (job_id,))
            conn.commit()
        finally:
            conn.close()
    except asyncio.TimeoutError:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE crawl_jobs SET status = 'timeout', completed_at = NOW()
                    WHERE id = %s
                """, (job_id,))
            conn.commit()
        finally:
            conn.close()
        return {"status": "timeout", "job_id": str(job_id)}
    except Exception as e:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE crawl_jobs SET status = 'error', error = %s, completed_at = NOW()
                    WHERE id = %s
                """, (str(e), job_id))
            conn.commit()
        finally:
            conn.close()
        return {"status": "error", "job_id": str(job_id), "error": str(e)}

    return {"status": "processed", "job_id": str(job_id)}


from pydantic import BaseModel

class TrainTextRequest(BaseModel):
    company_id: str
    text: str
    source_type: str = "manual"


@app.post("/train-text")
async def train_text(
    payload: TrainTextRequest,
    background: BackgroundTasks
):
    background.add_task(
        process_training_text,
        payload.company_id,
        payload.text,
        payload.source_type,
    )
    return {"status": "queued", "company_id": payload.company_id}


def process_training_text(
    company_id: str,
    text: str,
    source_type: str = "manual",
):
    """Chunk text, embed, store in company_docs"""
    try:
        print(f"[TRAIN] Starting for company={company_id}, text length={len(text)}", flush=True)

        # Chunk text
        chunks = chunk_text(text, size=800, overlap=100)

        if not chunks:
            print(f"[TRAIN] No chunks generated for {company_id}", flush=True)
            return

        print(f"[TRAIN] {len(chunks)} chunks generated", flush=True)

        # Generate embeddings
        embeddings = embed_texts(chunks)

        if len(embeddings) != len(chunks):
            raise Exception("Embedding count mismatch")

        # Store in company_docs
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Delete old manual chunks first
                cur.execute(
                    """
                    DELETE FROM company_docs 
                    WHERE company_id = %s AND source_type = %s
                    """,
                    (company_id, source_type),
                )

                rows = [
                    (
                        company_id,
                        None,
                        None,
                        chunk,
                        len(enc.encode(chunk)),
                        embedding,
                        source_type,
                        "manual_training",
                    )
                    for chunk, embedding in zip(chunks, embeddings)
                ]

                execute_values(
                    cur,
                    """
                    INSERT INTO company_docs 
                    (company_id, page_id, url, content, token_count, 
                     embedding, source_type, source_id)
                    VALUES %s
                    """,
                    rows,
                    template="(%s, %s, %s, %s, %s, %s, %s, %s)",
                )
            conn.commit()
        finally:
            conn.close()

        print(f"[TRAIN] DONE: {len(chunks)} chunks for {company_id}", flush=True)

    except Exception as e:
        print(f"[TRAIN ERROR] {company_id}: {e}", flush=True)

