from khabrichacha.core.hardware_profiler import get_cpu_cores, get_total_ram_gb, get_gpu_details

def recommend_model() -> dict:
    """
    Analyzes system resources and recommends the best model to run.
    """
    ram = get_total_ram_gb()
    cores = get_cpu_cores()
    gpu = get_gpu_details()
    
    recommendation = {
        "provider": "",
        "model": "",
        "explanation": "",
        "hardware": {
            "ram_gb": round(ram, 2),
            "cpu_cores": cores,
            "gpu_name": gpu["name"] if gpu["available"] else "None",
            "gpu_vram_gb": round(gpu["vram_gb"], 2) if gpu["available"] else 0.0
        }
    }
    
    if ram < 8.0:
        recommendation["provider"] = "gemini"
        recommendation["model"] = "gemini-2.0-flash"
        recommendation["explanation"] = f"Your system has {round(ram, 1)} GB RAM (less than 8 GB), which is too low to run local LLMs smoothly. We strongly recommend using the Gemini API provider for optimal speed and zero local resource usage."
    elif gpu["available"] and gpu["vram_gb"] >= 6.0:
        recommendation["provider"] = "ollama"
        recommendation["model"] = "deepseek-r1:8b"
        recommendation["explanation"] = f"Found a CUDA-capable GPU ({gpu['name']}) with {round(gpu['vram_gb'], 1)} GB VRAM. Your system can comfortably accelerate local inference. We recommend deepseek-r1:8b or llama3:8b using Ollama."
    elif ram >= 16.0:
        recommendation["provider"] = "ollama"
        recommendation["model"] = "llama3:8b"
        recommendation["explanation"] = f"Your system has {round(ram, 1)} GB RAM and {cores} CPU cores. We recommend running llama3:8b or deepseek-r1:8b via Ollama. Note: Without a dedicated GPU, local inference might be slightly slower."
    else:
        recommendation["provider"] = "ollama"
        recommendation["model"] = "qwen2.5:3b"
        recommendation["explanation"] = f"Your system has {round(ram, 1)} GB RAM and {cores} CPU cores. We recommend a lightweight local model like qwen2.5:3b or llama3:3b via Ollama to ensure smooth performance on CPU."
        
    return recommendation
