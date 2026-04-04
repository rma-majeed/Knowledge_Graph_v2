git clone https://github.com/rma-majeed/Knowledge_Graph_v2.git
cd Knowledge_Graph_v2
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Copy .env.example → .env and fill in your values
copy .env.example .env
Key things to set in .env on the new machine:

LLM_PROVIDER, LLM_MODEL, OPENAI_API_BASE, OPENAI_API_KEY for LM Studio
HF_TOKEN if you want to download the reranker
Run download_reranker_clean.py on a non-Zscaler machine first, then transfer the model folder