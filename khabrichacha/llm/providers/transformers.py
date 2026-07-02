from khabrichacha.llm.base import BaseLLMProvider
from typing import List, Dict, Any, Optional
from loguru import logger

class TransformersProvider(BaseLLMProvider):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.model_id = config.get("model_id", "meta-llama/Meta-Llama-3-8B-Instruct")
        self.device = config.get("device", "cpu")
        self.pipeline = None
        logger.info(f"TransformersProvider initialized for model_id {self.model_id} on {self.device}")

    def _lazy_init(self):
        if self.pipeline is not None:
            return
            
        try:
            import transformers
            import torch
            logger.info(f"Loading transformers pipeline for {self.model_id}...")
            self.pipeline = transformers.pipeline(
                "text-generation",
                model=self.model_id,
                device_map=self.device,
                torch_dtype=torch.float16 if self.device != "cpu" else torch.float32
            )
        except Exception as e:
            logger.error(f"Failed to load transformers pipeline: {e}")
            self.pipeline = "failed"

    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        logger.info(f"Transformers generate request for model {self.model_id}")
        self._lazy_init()
        if self.pipeline and self.pipeline != "failed":
            try:
                full_prompt = prompt
                if system_prompt:
                    full_prompt = f"<<SYS>>\n{system_prompt}\n<</SYS>>\n\n{prompt}"
                
                outputs = self.pipeline(
                    full_prompt,
                    max_new_tokens=self.config.get("max_tokens", 2048),
                    do_sample=True,
                    temperature=self.config.get("temperature", 0.7),
                    **kwargs
                )
                generated_text = outputs[0]["generated_text"]
                if generated_text.startswith(full_prompt):
                    generated_text = generated_text[len(full_prompt):].strip()
                return generated_text
            except Exception as e:
                logger.error(f"Transformers generation failed: {e}")
                return f"Error: Transformers generation failed: {e}"
        return f"[Mock Transformers {self.model_id}] response to prompt: {prompt}"

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        logger.info(f"Transformers chat request for model {self.model_id}")
        self._lazy_init()
        if self.pipeline and self.pipeline != "failed":
            try:
                outputs = self.pipeline(
                    messages,
                    max_new_tokens=self.config.get("max_tokens", 2048),
                    do_sample=True,
                    temperature=self.config.get("temperature", 0.7),
                    **kwargs
                )
                if isinstance(outputs, list) and len(outputs) > 0:
                    generated = outputs[0]
                    if "generated_text" in generated:
                        result = generated["generated_text"]
                        if isinstance(result, list) and len(result) > 0:
                            last_msg = result[-1]
                            return last_msg.get("content", "")
                        elif isinstance(result, str):
                            return result
                return str(outputs)
            except Exception as e:
                logger.error(f"Transformers chat execution failed: {e}")
                return f"Error: Transformers chat failed: {e}"
        return f"[Mock Transformers {self.model_id}] response to chat history of length {len(messages)}"
