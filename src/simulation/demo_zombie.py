import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from aiyodha_sdk.wrapper import AiyodhaClient, BudgetExceededError

async def run_zombie_demo():
    print("STARTING ZOMBIE DEMO...")
    client = AiyodhaClient(agent_id="Agent_Zombie")
    
    # The wrapper's _mock_llm_call returns "Mock response for: {prompt}"
    # So sending the same prompt will result in the same response hash.
    
    prompts = [
        "Hello world",
        "Hello world",
        "Hello world", # Should trigger warning/kill internally
        "Hello world", # Should be blocked
        "Hello world"
    ]
    
    for i, p in enumerate(prompts):
        print(f"\n[Request {i+1}] Sending prompt: '{p}'")
        try:
            response = await client.create(p)
            print(f"Success: {response}")
            await asyncio.sleep(0.5) # Wait for async heartbeat to process
        except BudgetExceededError as e:
            print(f"BLOCKED: {e}")
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(run_zombie_demo())
