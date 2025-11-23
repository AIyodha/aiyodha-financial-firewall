import asyncio
import sys
import os
import random

# Add parent dir to path to import sdk
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from aiyodha_sdk.wrapper import AiyodhaClient
from aiyodha_sdk.exceptions import BudgetExceededError

async def rogue_loop():
    client = AiyodhaClient()
    print("Rogue Agent Started... Spaming requests with CONCURRENCY!")
    
    batch_size = 10
    batch_count = 0
    
    try:
        while True:
            tasks = []
            for i in range(batch_size):
                prompt = f"Request {batch_count}-{i}"
                tasks.append(client.create(prompt))
            
            print(f"Firing batch {batch_count} ({batch_size} requests)...")
            
            try:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                success_count = 0
                for res in results:
                    if isinstance(res, BudgetExceededError):
                        print("CAUGHT BudgetExceededError! The Firewall worked!")
                        # We can choose to break or continue to see if it persists
                        # For this demo, let's break to show it caught it.
                        raise res 
                    elif isinstance(res, Exception):
                        print(f"Error: {res}")
                    else:
                        success_count += 1
                
                print(f"Batch {batch_count} complete. Success: {success_count}/{batch_size}")
                batch_count += 1
                
                # Small sleep to prevent total CPU lockup, but keep it aggressive
                await asyncio.sleep(0.1) 
                
            except BudgetExceededError:
                print("\n>>> FIREWALL ACTIVATED - BLOCKED REQUESTS <<<")
                break
            except Exception as e:
                print(f"Main Loop Error: {e}")
                break
    finally:
        await client.aclose()

if __name__ == "__main__":
    try:
        asyncio.run(rogue_loop())
    except KeyboardInterrupt:
        print("Stopped.")
