"""HuggingFace validator — checks if a dataset exists on HuggingFace Hub."""

import httpx


def validate_hf_dataset(name: str) -> dict:
    """Check if a dataset exists on HuggingFace.

    Args:
        name: dataset name (e.g., "openai/gsm8k" or "gsm8k")

    Returns:
        {valid: bool, dataset_id: str|null, downloads: int|null, error: str|null}
    """
    if not name or not name.strip():
        return {"valid": False, "dataset_id": None, "downloads": None, "error": "empty name"}

    name = name.strip().strip("/")

    # Try the HF API (no auth needed for public datasets)
    try:
        url = f"https://huggingface.co/api/datasets/{name}"
        resp = httpx.get(url, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            return {
                "valid": True,
                "dataset_id": data.get("id", name),
                "downloads": data.get("downloads", None),
                "error": None,
            }
        elif resp.status_code == 404:
            return {"valid": False, "dataset_id": None, "downloads": None,
                    "error": f"Dataset '{name}' not found on HuggingFace"}
        else:
            return {"valid": False, "dataset_id": None, "downloads": None,
                    "error": f"HF API returned {resp.status_code}"}

    except Exception as e:
        return {"valid": False, "dataset_id": None, "downloads": None,
                "error": str(e)[:200]}
