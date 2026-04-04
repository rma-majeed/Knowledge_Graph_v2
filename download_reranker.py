"""One-time script to download BAAI/bge-reranker-v2-m3 from HuggingFace.

Handles Zscaler SSL interception by:
1. Converting the Zscaler DER cert to PEM
2. Appending it to certifi's CA bundle (one-time, idempotent)
3. Setting REQUESTS_CA_BUNDLE so HuggingFace Hub uses the updated bundle
4. Pre-downloading the model to ~/.cache/huggingface/hub

Run once before enabling RAG_ENABLE_RERANKER=true in .env
"""
import os
import sys
import base64

# Must be set before huggingface_hub is imported — hf_transfer activates at import time.
# hf_transfer is a Rust parallel downloader that bypasses Python SSL patches.
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

ZSCALER_CERT_PATH = r"C:\New folder (2)\Zscalar.cer"

def der_to_pem(der_bytes: bytes) -> str:
    b64 = base64.b64encode(der_bytes).decode("ascii")
    lines = [b64[i:i+64] for i in range(0, len(b64), 64)]
    return "-----BEGIN CERTIFICATE-----\n" + "\n".join(lines) + "\n-----END CERTIFICATE-----\n"

def ensure_zscaler_in_certifi() -> str:
    import certifi
    bundle_path = certifi.where()

    with open(ZSCALER_CERT_PATH, "rb") as f:
        der_bytes = f.read()

    pem_cert = der_to_pem(der_bytes)

    with open(bundle_path, "r", encoding="utf-8") as f:
        existing = f.read()

    # Check if already appended (idempotent by marker)
    marker = "# Zscaler Root CA (appended by download_reranker.py)"
    if marker in existing:
        print("[SSL] Zscaler cert already in certifi bundle — skipping append.")
    else:
        with open(bundle_path, "a", encoding="utf-8") as f:
            f.write(f"\n{marker}\n{pem_cert}")
        print(f"[SSL] Appended Zscaler cert to: {bundle_path}")

    return bundle_path

def download_model():
    bundle_path = ensure_zscaler_in_certifi()

    # Root cause: huggingface_hub v1.x uses httpx (not requests) for all HTTP calls.
    # The Zscaler cert has a non-critical Basic Constraints extension that Python's
    # OpenSSL rejects. Fix: use HF Hub's official set_client_factory / set_async_client_factory
    # to inject httpx clients with verify=False for this process only.
    # Safe on corporate network: Zscaler already intercepts all HTTPS traffic.
    import httpx
    import warnings
    warnings.filterwarnings("ignore", message=".*SSL.*")

    from huggingface_hub import set_client_factory, set_async_client_factory

    def _no_ssl_client() -> httpx.Client:
        return httpx.Client(verify=False)

    def _no_ssl_async_client() -> httpx.AsyncClient:
        return httpx.AsyncClient(verify=False)

    set_client_factory(_no_ssl_client)
    set_async_client_factory(_no_ssl_async_client)

    # Load HF_TOKEN from .env for authenticated (faster) downloads
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))
    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        print("[WARN] HF_TOKEN not set — downloads will be rate-limited (~3 kB/s).")
        print("       Add HF_TOKEN=hf_xxx to your .env for full speed.\n")
    else:
        print("[HF] Authenticated with HF_TOKEN.")


    print("\n[HF] Starting download of BAAI/bge-reranker-v2-m3 (~800MB) ...")
    print("[HF] This is a one-time download — model will be cached and reused.\n")

    # Only these files are needed by sentence-transformers CrossEncoder
    REQUIRED_FILES = [
        "config.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "special_tokens_map.json",
        "sentencepiece.bpe.model",
        "model.safetensors",
    ]

    try:
        from huggingface_hub import hf_hub_download
        cached_paths = []
        for filename in REQUIRED_FILES:
            print(f"[HF] Downloading {filename} ...")
            path = hf_hub_download(
                repo_id="BAAI/bge-reranker-v2-m3",
                filename=filename,
                token=hf_token or None,
            )
            cached_paths.append(path)
            print(f"      -> {path}")

        local_dir = os.path.dirname(cached_paths[0])
        print(f"\n[HF] Download complete. Model cached at:\n  {local_dir}")
        print("\nYou can now enable the reranker in .env:")
        print("  RAG_ENABLE_RERANKER=true")
    except Exception as e:
        print(f"\n[ERROR] Download failed: {e}")
        print("\nTroubleshooting:")
        print("  1. Make sure you're connected to the internet / VPN")
        print("  2. Try running this script from PowerShell as the same user")
        print("  3. If SSL still fails, the cert at ZSCALER_CERT_PATH may be wrong")
        sys.exit(1)

if __name__ == "__main__":
    download_model()
