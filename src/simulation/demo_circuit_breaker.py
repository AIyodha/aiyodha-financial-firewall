import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from aiyodha_sdk.wrapper import AiyodhaClient, BudgetExceededError

async def run_circuit_breaker_demo():
    print("STARTING CIRCUIT BREAKER DEMO...")
    client = AiyodhaClient(agent_id="Agent_HighRoller")
    
    # Limit is $50 in 10 mins.
    # We will send a request costing $60.
    
    print(f"\n[Request 1] Sending massive request (Cost: $60.00)...")
    try:
        # We need to manually trigger the heartbeat with high cost for this demo
        # since the wrapper default is 0.05. 
        # We'll use the internal method for demonstration or modify the wrapper call if possible.
        # The wrapper.create() uses default cost. Let's bypass and use _send_heartbeat directly 
        # to simulate the high cost, or just call create() many times.
        
        # Better: Let's just call create() many times to simulate rapid spend.
        # $60 / $0.05 = 1200 requests. That's too many.
        # Let's cheat and call _send_heartbeat directly to simulate a "Whale" request.
        
        await client._send_heartbeat(cost=60.0, model="gpt-4-32k")
        print("Heartbeat sent. Waiting for Policy Engine...")
        await asyncio.sleep(1)
        
        # Now try a normal request. It should be blocked.
        print("\n[Request 2] Trying normal request...")
        await client.create("Can I spend more?")
        print("Success (Unexpected!)")
        
    except BudgetExceededError as e:
        print(f"BLOCKED: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(run_circuit_breaker_demo())
