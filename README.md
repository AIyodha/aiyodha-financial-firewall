**AIYODHA Financial Firewall** 🛡️

Zero-Latency Policy Enforcement Engine for Autonomous Agents

This project demonstrates a high-performance, distributed policy enforcement point designed to integrate with large language models (LLMs) or autonomous agents. Its primary goal is to enforce financial, security, and governance policies (Token Bucket, Circuit Breaker, Zombie Detection, Kill Switch) with sub-2ms latency overhead.The architecture uses a Fire-and-Forget model, where the Agent SDK calls the Policy Engine asynchronously, ensuring that the latency added to the LLM call is negligible.

**🚀 Key Feature**
Zero-Latency Guarantee: Policy checks add minimal overhead ($\ll 2$ms) via local caching and asynchronous heartbeats.
Distributed Budgeting: Uses Redis as a token bucket store for atomic, persistent financial control across multiple Policy Engine instances.
**
**Resilience & Security:****
Kill Switch: Global, immediate system shutdown.
Zombie Detection: Identifies agents stuck in infinite loops.
Circuit Breaker: Included in the SDK to handle Policy Engine failures.
CFO Cockpit: A real-time, professional dashboard displaying operational metrics, financial health, and resilience status.

**📦 Project Structure**

aiyodha-financial-firewall/
├── docker/                     # Docker configurations (Nginx, Dockerfiles)
├── src/
│   ├── aiyodha_sdk/            # The Python SDK Wrapper (wrapper.py, exceptions.py)
│   ├── policy_engine/          # The FastAPI Policy Engine Server (server.py)
│   └── dashboard/              # The React/Vite Dashboard UI
├── simulation/                 # Simulation scripts (rogue_agent.py)
├── .env.example                # Example environment variables
├── docker-compose.yml          # Orchestration for the entire stack
└── requirements.txt            # Python dependencies


**⚙️ How to Run (Containerized Setup)**

This project is designed to be run entirely within Docker containers.
Prerequisites:Docker and Docker Compose installed.
Steps:Clone the Repository:
git clone [https://github.com/YOUR_USERNAME/aiyodha-financial-firewall.git](https://github.com/YOUR_USERNAME/aiyodha-financial-firewall.git)
cd aiyodha-financial-firewall

Start the Stack:docker compose up --build -d
This command will build the Policy Engine and Dashboard containers, start the Redis database, and link them all together.
Access the Dashboard:Open your browser to: http://localhost/

**Run the Simulation:**
To simulate load and see the metrics update in real-time, you need to run the rogue_agent.py script.

# You must run this command *outside* the docker containers for the simulation
# to communicate with the network correctly.
pip install -r requirements.txt
python simulation/rogue_agent.py

