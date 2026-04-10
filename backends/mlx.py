import mlx_lm
from mlx_lm import load, generate
from mlx_lm.sample_utils import make_sampler
from typing import Generator, List, Dict, Any
from .base import BaseBackend

class MLXBackend(BaseBackend):
    def __init__(self, verbose: bool = False):
        super().__init__(verbose=verbose)
        self.model = None
        self.tokenizer = None
        self.model_path = None

    def load_model(self, model_path: str):
        if self.verbose:
            print(f"[Debug] Loading MLX model: {model_path}...")
        self.model, self.tokenizer = load(model_path)
        self.model_path = model_path

    def generate_stream(self, messages: List[Dict[str, str]], **kwargs) -> Generator[str, None, None]:
        if not self.model:
            raise ValueError("Model not loaded. Call load_model() first.")

        # MLX用プロンプト作成
        prompt = self.tokenizer.apply_chat_template(
            messages, 
            add_generation_prompt=True, 
            tokenize=False
        )
        
        # パラメータ設定
        max_tokens = kwargs.get("max_tokens", 1024)
        temp = kwargs.get("temperature", 0.0)
        
        # 生成
        for chunk in generate(
            self.model, 
            self.tokenizer, 
            prompt=prompt, 
            sampler=make_sampler(temp), 
            max_tokens=max_tokens
        ):
            yield chunk

    def list_models(self) -> List[str]:
        return []
