import os

os.environ["TOKENIZERS_PARALLELISM"] = "false"

# اجزای PyTorch روی CPU
os.environ["SEMANTIC_DEVICE"] = "cpu"
os.environ["RETRIEVAL_DEVICE"] = "cpu"
os.environ["RERANKER_DEVICE"] = "cpu"

# فقط llama.cpp / Meditron روی GPU
os.environ["LLM_N_GPU_LAYERS"] = "-1"

# فعلاً خاموش
os.environ["ENABLE_QUERY_EXPANSION"] = "false"
os.environ["ENABLE_LOCAL_LLM_ANSWERS"] = "false"