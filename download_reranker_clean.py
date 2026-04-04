"""
Download BAAI/bge-reranker-v2-m3 on a machine WITHOUT Zscaler.

STEPS AFTER DOWNLOAD:
1. Find the downloaded folder at:
      Windows: C:\Users\<your-username>\.cache\huggingface\hub\models--BAAI--bge-reranker-v2-m3
      Mac/Linux: ~/.cache/huggingface/hub/models--BAAI--bge-reranker-v2-m3

2. Zip the entire 'models--BAAI--bge-reranker-v2-m3' folder

3. Upload the zip to Google Drive

4. On your work laptop, download and extract to:
      C:\Users\2171176\.cache\huggingface\hub\models--BAAI--bge-reranker-v2-m3

5. Verify it works by running in the Knowledge_Graph_v2 project (venv activated):
      python -c "from sentence_transformers import CrossEncoder; m = CrossEncoder('BAAI/bge-reranker-v2-m3', device='cpu'); print('Reranker loaded OK')"

6. Enable in .env:
      RAG_ENABLE_RERANKER=true
"""

from huggingface_hub import snapshot_download
import os

print("Downloading BAAI/bge-reranker-v2-m3 (~560MB)...")

local_dir = snapshot_download(
    repo_id="BAAI/bge-reranker-v2-m3",
    ignore_patterns=["*.msgpack", "flax_model*", "tf_model*", "rust_model*"],
)

cache_root = os.path.dirname(os.path.dirname(os.path.dirname(local_dir)))
model_folder = os.path.join(cache_root, "models--BAAI--bge-reranker-v2-m3")

print(f"\nDownload complete.")
print(f"\nFolder to copy to Google Drive:")
print(f"  {model_folder}")
print(f"\nOn your work laptop, extract it to:")
print(f"  C:\\Users\\2171176\\.cache\\huggingface\\hub\\models--BAAI--bge-reranker-v2-m3")
