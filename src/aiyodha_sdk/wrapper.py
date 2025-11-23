import asyncio
import time
import httpx
import logging
from collections import deque
from .exceptions import BudgetExceededError, CircuitBreakerTrippedError

# Setup logger for latency tracking
logger = logging.getLogger("aiyodha_latency")
logger.setLevel(logging.INFO)
handler = logging.FileHandler("latency.log")
formatter = logging.Formatter('%(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

import os
from dotenv import load_dotenv

load_dotenv()

class AiyodhaClient:
    def __init__(self, agent_id="Agent_007", policy_engine_url=None):
        self.agent_id = agent_id
        self.policy_engine_url = policy_engine_url or os.getenv("POLICY_ENGINE_URL", "http://localhost:8001")
        self.client = httpx.AsyncClient()
        
        # Layer 1: Local State
        self.local_kill_switch = False
        self.request_timestamps = deque()
        self.MAX_LOCAL_RPS = 5
        
        # Circuit Breaker State
        self.consecutive_failures = 0
        self.circuit_tripped_until = 0.0  # Unix timestamp
        self.FAILURE_THRESHOLD = 3
        self.COOLDOWN_SECONDS = 60
        
        # Zombie Detection (Statistical)
        self.response_history = []  # Stores response lengths 

    async def _send_heartbeat(self, cost=0.05, model="gpt-4-mock", is_zombie=False):
        """
        Layer 2: Async Heartbeat (Fire and Forget)
        If the engine returns 402, updates the local cache to kill future requests.
        Implements Circuit Breaker failure tracking.
        """
        try:
            response = await self.client.post(
                f"{self.policy_engine_url}/heartbeat",
                json={
                    "agent_id": self.agent_id, 
                    "cost": cost, 
                    "model": model,
                    "is_zombie": is_zombie
                }
            )
            # SUCCESS PATH: Reset failure counter on successful response
            if response.status_code in [200, 402]:
                self.consecutive_failures = 0
            
            if response.status_code == 402:
                self.local_kill_switch = True
                
        except (httpx.RequestError, httpx.HTTPError) as e:
            # FAILURE PATH: Track consecutive failures
            self.consecutive_failures += 1
            logging.error(f"Heartbeat error ({self.consecutive_failures}/{self.FAILURE_THRESHOLD}): {e}")
            
            # Trip Circuit Breaker if threshold reached
            if self.consecutive_failures >= self.FAILURE_THRESHOLD:
                self.circuit_tripped_until = time.time() + self.COOLDOWN_SECONDS
                logging.critical(
                    f"CIRCUIT BREAKER TRIPPED! Policy Engine unreachable. "
                    f"Cooldown: {self.COOLDOWN_SECONDS}s. Tripped until: {self.circuit_tripped_until}"
                )
        except Exception as e:
            logging.error(f"Unexpected heartbeat error: {e}")

    async def create(self, prompt):
        """
        Wraps the LLM call with Two-Layer Enforcement.
        Includes Circuit Breaker pre-check.
        """
        t0 = time.perf_counter_ns()

        # --- CIRCUIT BREAKER CHECK ---
        if time.time() < self.circuit_tripped_until:
            raise CircuitBreakerTrippedError(
                f"Policy Engine is down. Cooldown active until {self.circuit_tripped_until}. "
                f"Remaining: {self.circuit_tripped_until - time.time():.1f}s"
            )

        # --- LAYER 1: LOCAL CHECKS (Zero Latency) ---
        if self.local_kill_switch:
            raise BudgetExceededError("Agent is killed (Local Cache)")

        # Local Rate Limiter (Leaky Bucket)
        now = time.time()
        while self.request_timestamps and self.request_timestamps[0] < now - 1.0:
            self.request_timestamps.popleft()
        
        if len(self.request_timestamps) >= self.MAX_LOCAL_RPS:
             raise BudgetExceededError("Local Rate Limit Exceeded (5 RPS)")
        
        self.request_timestamps.append(now)

        # --- LAYER 2: ASYNC HEARTBEAT ---
        # Dispatch background task immediately
        # Zombie logic is calculated POST-call, but we send the heartbeat PRE-call logic here 
        # for simplicity in this POC, or we can send it after. 
        # The prompt asks for "Run local checks and dispatch async task." then "Stop timer".
        
        # We need to know if it's a zombie from PREVIOUS calls to send in this heartbeat?
        # Or send the result of THIS call in the NEXT heartbeat?
        # The prompt says: "If server returns 402, set self.local_kill_switch = True."
        # Let's check for zombie status based on history BEFORE the call.
        
        is_zombie = self._check_zombie_status()
        asyncio.create_task(self._send_heartbeat(is_zombie=is_zombie))

        # Measure Overhead
        t1 = time.perf_counter_ns()
        overhead_ms = (t1 - t0) / 1e6
        logger.info(f"{overhead_ms:.4f}")

        # --- ACTUAL LLM CALL ---
        response_text = await self._mock_llm_call(prompt)

        # Update Zombie History
        self._update_zombie_history(response_text)

        return response_text

    def _check_zombie_status(self):
        """
        Advanced Zombie Detection using statistical analysis.
        Detects agents stuck in repetitive patterns by analyzing response length variance.
        """
        if len(self.response_history) >= 5:
            # Calculate standard deviation of response lengths
            mean = sum(self.response_history) / len(self.response_history)
            variance = sum((x - mean) ** 2 for x in self.response_history) / len(self.response_history)
            std_dev = variance ** 0.5
            
            # Flag zombie if responses are too uniform (std_dev < 5.0)
            if std_dev < 5.0:
                logging.warning(
                    f"Zombie detected! Response length std_dev: {std_dev:.2f} (threshold: 5.0). "
                    f"History: {self.response_history}"
                )
                return True
        return False

    def _update_zombie_history(self, response_text):
        """
        Store response length for statistical zombie detection.
        Maintains a sliding window of the last 10 response lengths.
        """
        response_length = len(response_text)
        self.response_history.append(response_length)
        if len(self.response_history) > 10:
            self.response_history.pop(0)

    async def _mock_llm_call(self, prompt):
        # Simulate network delay for LLM
        await asyncio.sleep(0.1) 
        return f"Processed: {prompt}"

    async def aclose(self):
        await self.client.aclose()
