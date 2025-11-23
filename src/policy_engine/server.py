import asyncio
import os
import time
import logging
from typing import Dict, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import redis.asyncio as redis

# Load configuration
load_dotenv()

# Configuration
PORT = int(os.getenv("PORT", 8001))
HOST = os.getenv("HOST", "0.0.0.0")
ALLOWED_ORIGINS = eval(os.getenv("ALLOWED_ORIGINS", '["http://localhost:8501", "http://localhost:3000"]'))
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Logging Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("policy_engine")

app = FastAPI(title="AIYODHA Policy Engine", version="2.0.0")

# Security Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["localhost", "127.0.0.1", "0.0.0.0"]
)

# --- RESILIENCE TRACKING ---
# Redis keys:
# stats:breaches -> Counter for total budget breaches
# stats:zombies -> Counter for detected zombie agents

# --- REDIS & DISTRIBUTED LOCK ---

class MockRedis:
    """Simulates Redis for environments without a running Redis server."""
    def __init__(self):
        self.data = {}
        self.lock = asyncio.Lock()
        logger.warning("⚠️  RUNNING IN MOCK REDIS MODE (No persistence) ⚠️")

    async def get(self, key):
        return self.data.get(key)

    async def set(self, key, value):
        self.data[key] = str(value)
        return True

    async def setnx(self, key, value):
        async with self.lock:
            if key in self.data:
                return False
            self.data[key] = str(value)
            return True

    async def delete(self, key):
        if key in self.data:
            del self.data[key]
            return 1
        return 0

    async def decrby(self, key, amount):
        val = float(self.data.get(key, 0))
        val -= amount
        self.data[key] = str(val)
        return val

    async def incrbyfloat(self, key, amount):
        val = float(self.data.get(key, 0))
        val += amount
        self.data[key] = str(val)
        return val
    
    async def expire(self, key, time):
        # Mock expiration (noop for simplicity in this demo)
        return True
        
    async def close(self):
        pass

class DistributedLock:
    def __init__(self, redis_client, resource: str, lock_timeout: int = 5):
        self.redis = redis_client
        self.resource = f"lock:{resource}"
        self.timeout = lock_timeout
        self.is_locked = False

    async def __aenter__(self):
        # Simple spin lock implementation
        start_time = time.time()
        while True:
            if await self.redis.setnx(self.resource, "locked"):
                await self.redis.expire(self.resource, self.timeout)
                self.is_locked = True
                return self
            
            if time.time() - start_time > self.timeout:
                raise HTTPException(status_code=503, detail="Service Busy: Could not acquire lock")
            
            await asyncio.sleep(0.01) # 10ms spin

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.is_locked:
            await self.redis.delete(self.resource)
            self.is_locked = False

# Initialize Redis
redis_client = None

@app.on_event("startup")
async def startup_event():
    global redis_client
    try:
        # Try connecting to real Redis
        client = redis.from_url(REDIS_URL, decode_responses=True)
        await client.ping()
        redis_client = client
        logger.info(f"✅ Connected to Redis at {REDIS_URL}")
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}. Falling back to MockRedis.")
        redis_client = MockRedis()

    # Seeding Logic
    agent_id = "Agent_007"
    balance_key = f"agent:{agent_id}:balance"
    
    # Check if agent exists
    if not await redis_client.get(balance_key):
        logger.info(f"🌱 Seeding initial data for {agent_id}")
        await redis_client.set(f"agent:{agent_id}:balance", 100.0)
        await redis_client.set(f"agent:{agent_id}:spent", 0.0)
        await redis_client.set(f"agent:{agent_id}:killed", "false")

@app.on_event("shutdown")
async def shutdown_event():
    if redis_client:
        await redis_client.close()

# Models
class HeartbeatRequest(BaseModel):
    agent_id: str
    cost: float
    is_zombie: bool = False
    metadata: Optional[dict] = {}

# Endpoints

@app.post("/heartbeat")
async def heartbeat(request: HeartbeatRequest):
    async with DistributedLock(redis_client, request.agent_id):
        # Keys
        key_balance = f"agent:{request.agent_id}:balance"
        key_spent = f"agent:{request.agent_id}:spent"
        key_killed = f"agent:{request.agent_id}:killed"

        # 1. Agent Check (Implicit by keys existence, but we can check balance)
        balance = await redis_client.get(key_balance)
        if balance is None:
             raise HTTPException(status_code=404, detail="Agent not found")
        balance = float(balance)

        # 2. Kill Switch Check
        killed = await redis_client.get(key_killed)
        if killed == "true":
            await redis_client.incr("stats:breaches")  # Track breach in Redis
            raise HTTPException(status_code=402, detail="Payment Required: Agent Killed")
        
        # 3. Zombie Check
        if request.is_zombie:
            await redis_client.incr("stats:zombies")  # Track zombie in Redis
            await redis_client.set(key_killed, "true")
            logger.warning(f"Zombie detected: {request.agent_id}. Kill switch activated.")
            raise HTTPException(status_code=402, detail="Payment Required: Zombie Agent Detected")

        # 4. Budget Enforcement
        if balance < request.cost:
            await redis_client.incr("stats:breaches")  # Track breach in Redis
            raise HTTPException(status_code=402, detail="Payment Required: Insufficient Budget")
        
        # 5. Deduct Cost (Atomic-ish with lock)
        # In a real production env, we might use Lua scripts for true atomicity without locks,
        # but the prompt requested DistributedLock.
        new_balance = await redis_client.incrbyfloat(key_balance, -request.cost)
        await redis_client.incrbyfloat(key_spent, request.cost)
        
        return {"status": "ok", "remaining_balance": float(new_balance)}

@app.post("/admin/kill_switch")
async def kill_switch(agent_id: str = "Agent_007"):
    async with DistributedLock(redis_client, agent_id):
        key_killed = f"agent:{agent_id}:killed"
        # Check existence
        if not await redis_client.get(f"agent:{agent_id}:balance"):
             raise HTTPException(status_code=404, detail="Agent not found")
        
        await redis_client.set(key_killed, "true")
        logger.info(f"Kill switch activated for {agent_id}")
        return {"status": "killed", "agent_id": agent_id}

@app.get("/status/{agent_id}")
async def get_status(agent_id: str):
    # No lock needed for simple status read, but cleaner to be consistent if strict consistency required.
    # For status display, eventual consistency is usually fine, but let's read directly.
    
    balance = await redis_client.get(f"agent:{agent_id}:balance")
    if balance is None:
        return {}
    
    spent = await redis_client.get(f"agent:{agent_id}:spent")
    killed = await redis_client.get(f"agent:{agent_id}:killed")

    return {
        "agent_id": agent_id,
        "budget": float(balance) + float(spent),
        "remaining": float(balance),
        "spent": float(spent),
        "killed": killed == "true"
    }

@app.get("/stats/latency")
def get_latency_stats():
    """Get latency statistics with avg, max, min calculations"""
    try:
        if os.path.exists("latency.log"):
            with open("latency.log", "r") as f:
                lines = f.readlines()
                # Get last 50 data points
                data = [float(line.strip()) for line in lines if line.strip()][-50:]
                
                if data:
                    return {
                        "history": data,
                        "avg": sum(data) / len(data),
                        "max": max(data),
                        "min": min(data),
                        "count": len(data)
                    }
    except Exception as e:
        logger.error(f"Error reading latency stats: {e}")
    
    return {"history": [], "avg": 0, "max": 0, "min": 0, "count": 0}

@app.get("/stats/resilience")
async def get_resilience_stats():
    """Get resilience metrics from Redis"""
    try:
        breaches = await redis_client.get("stats:breaches") or 0
        zombies = await redis_client.get("stats:zombies") or 0
        
        return {
            "zombie_agents": int(zombies),
            "total_breaches": int(breaches),
            "circuit_breaker_trips": 0 # Inferred from client-side logs usually, but kept for API compatibility
        }
    except Exception as e:
        logger.error(f"Error fetching resilience stats: {e}")
        return {"zombie_agents": 0, "total_breaches": 0, "circuit_breaker_trips": 0}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
