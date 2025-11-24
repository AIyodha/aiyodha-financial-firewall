FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose ports for API and Dashboard
EXPOSE 8001
EXPOSE 8501

# Create a startup script
RUN echo '#!/bin/bash\n\
python policy_engine/server.py & \n\
streamlit run dashboard/app.py --server.port 8501 --server.address 0.0.0.0\n\
wait' > start.sh && chmod +x start.sh

CMD ["./start.sh"]
