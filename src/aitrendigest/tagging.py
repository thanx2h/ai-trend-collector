TAG_KEYWORDS = {
    "agent": ["agent", "tool calling", "workflow", "orchestrator"],
    "eval": ["eval", "evaluation", "benchmark", "harness"],
    "rag": ["rag", "retrieval"],
    "infra": ["infra", "platform", "stack"],
    "multimodal": ["multimodal", "vision", "ocr", "image", "video", "audio"],
    "serving": ["serving", "inference", "vllm", "llama.cpp", "ollama"],
    "tooling": ["sdk", "framework", "tooling"],
    "skill": ["prompt", "fine-tuning", "alignment", "post-training"],
}


def infer_tags(text: str) -> list[str]:
    lowered = text.lower()
    tags = [
        tag
        for tag, keywords in TAG_KEYWORDS.items()
        if any(keyword in lowered for keyword in keywords)
    ]
    return sorted(set(tags))
