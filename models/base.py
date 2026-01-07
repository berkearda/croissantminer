from abc import ABC, abstractmethod

class BaseModel(ABC):
    def __init__(self, model_id: str, **kwargs):
        self.model_id = model_id
        self.config = kwargs
    
    @abstractmethod
    def setup(self) -> bool:
        pass
    
    @abstractmethod
    def generate(self, prompt: str) -> str:
        pass
    
    @abstractmethod
    def cleanup(self):
        pass