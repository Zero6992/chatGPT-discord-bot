import os
import logging
import re
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import asyncio

import g4f
from g4f.client import Client
from g4f.Provider import RetryProvider
from openai import AsyncOpenAI
import google.generativeai as genai
from anthropic import AsyncAnthropic
import aiohttp

logger = logging.getLogger(__name__)


class ProviderType(Enum):
    FREE = "free"
    OPENAI = "openai"
    CLAUDE = "claude"
    GEMINI = "gemini"
    GROK = "grok"


@dataclass
class ModelInfo:
    name: str
    provider: ProviderType
    description: str = ""
    supports_vision: bool = False
    supports_image_generation: bool = False


class BaseProvider(ABC):
    """Base class for all AI providers"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.models: List[ModelInfo] = []
        
    @abstractmethod
    async def chat_completion(self, messages: List[Dict[str, str]], model: str, **kwargs) -> str:
        """Generate chat completion"""
        pass
    
    @abstractmethod
    async def generate_image(self, prompt: str, model: Optional[str] = None, **kwargs) -> str:
        """Generate image from prompt"""
        pass
    
    @abstractmethod
    def get_available_models(self) -> List[ModelInfo]:
        """Get list of available models"""
        pass
    
    @abstractmethod
    def supports_image_generation(self) -> bool:
        """Check if provider supports image generation"""
        pass


class FreeProvider(BaseProvider):
    """Provider for free models via g4f"""
    
    def __init__(self):
        super().__init__()
        # Use completely authentication-free providers
        providers_list = []
        
        # Check for authentication cookies
        gemini_available = bool(os.getenv("GOOGLE_PSID"))
        bing_available = bool(os.getenv("BING_COOKIE"))
        
        # Only add auth-required providers if proper authentication is available
        if gemini_available:
            providers_list.append(g4f.Provider.Gemini)
            logger.info("Gemini provider added (GOOGLE_PSID cookie found)")
        else:
            logger.info("Gemini provider skipped (no GOOGLE_PSID cookie)")
            
        if bing_available:
            # Note: Bing provider through g4f might still need special handling
            logger.info("Bing provider skipped (avoiding authentication issues)")
            pass  # Skip Bing for now to avoid auth issues
        else:
            logger.info("Bing provider skipped (no BING_COOKIE found)")
        
        # Add proven authentication-free providers
        # These providers work without any API keys or cookies
        auth_free_providers = [
            g4f.Provider.PollinationsAI,    # Reliable for text generation
            g4f.Provider.Blackbox,          # Good fallback option
            g4f.Provider.LambdaChat,        # Stable free provider
            g4f.Provider.DeepInfraChat,     # Alternative option
            g4f.Provider.Free2GPT,          # Basic free provider
            g4f.Provider.Cloudflare,        # Fast and reliable
        ]
        
        # Add auth-free providers to the list
        for provider in auth_free_providers:
            try:
                # Verify provider exists before adding
                providers_list.append(provider)
                logger.info(f"Added auth-free provider: {provider.__name__}")
            except AttributeError:
                logger.warning(f"Provider {provider} not available in current g4f version")
        
        # Ensure we have at least one provider
        if not providers_list:
            # Fallback to basic providers that should always be available
            providers_list = [g4f.Provider.Free2GPT, g4f.Provider.Blackbox]
            logger.warning("No providers available, using fallback: Free2GPT and Blackbox")
        
        logger.info(f"FreeProvider initialized with {len(providers_list)} providers")
        
        self.client = Client(
            provider=RetryProvider(providers_list, shuffle=False)
        )
        
    async def chat_completion(self, messages: List[Dict[str, str]], model: str, **kwargs) -> str:
        try:
            # Use best available free model that works with auth-free providers
            if not model or model == "auto":
                # Check if Gemini auth is available for premium models
                if os.getenv("GOOGLE_PSID"):
                    model = "gemini-2.0-flash-exp"
                else:
                    # Use models that work well with auth-free providers
                    # These models are commonly supported by PollinationsAI, Blackbox, etc.
                    model = "gpt-4o-mini"  # Widely supported by free providers
            
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=model,
                messages=messages,
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Free provider error: {e}")
            # If the primary model fails, try with a more basic model
            if "model" in str(e).lower() or "not found" in str(e).lower():
                try:
                    logger.info("Retrying with fallback model: gpt-3.5-turbo")
                    response = await asyncio.to_thread(
                        self.client.chat.completions.create,
                        model="gpt-3.5-turbo",
                        messages=messages,
                        **kwargs
                    )
                    return response.choices[0].message.content
                except Exception as fallback_error:
                    logger.error(f"Fallback model also failed: {fallback_error}")
            raise
    
    async def generate_image(self, prompt: str, model: Optional[str] = None, **kwargs) -> str:
        try:
            # Use g4f image generation
            response = await asyncio.to_thread(
                self.client.images.generate,
                prompt=prompt,
                model=model or "flux",
                **kwargs
            )
            return response.data[0].url
        except Exception as e:
            logger.error(f"Free provider image generation error: {e}")
            raise
    
    def get_available_models(self) -> List[ModelInfo]:
        models = [
            # Models that work well with auth-free providers
            ModelInfo("gpt-4o-mini", ProviderType.FREE, "GPT-4 mini via free providers"),
            ModelInfo("gpt-3.5-turbo", ProviderType.FREE, "GPT-3.5 via free providers"),
            ModelInfo("llama-3.1-70b", ProviderType.FREE, "Meta's Llama model"),
            ModelInfo("claude-3-haiku", ProviderType.FREE, "Claude Haiku via free providers"),
        ]
        
        # Add auth-dependent models only if authentication is available
        if os.getenv("GOOGLE_PSID"):
            models.extend([
                ModelInfo("gemini-2.0-flash-exp", ProviderType.FREE, "Google's latest experimental model", supports_vision=True),
                ModelInfo("gemini-1.5-pro", ProviderType.FREE, "Google's pro model", supports_vision=True),
            ])
        
        # Add image models that work with auth-free providers
        models.extend([
            ModelInfo("flux", ProviderType.FREE, "Flux image generation via PollinationsAI", supports_image_generation=True),
            ModelInfo("dalle-mini", ProviderType.FREE, "DALL-E mini via free providers", supports_image_generation=True),
        ])
        
        return models
    
    def supports_image_generation(self) -> bool:
        return True


class OpenAIProvider(BaseProvider):
    """Official OpenAI API provider"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.client = AsyncOpenAI(api_key=api_key)
        
    async def chat_completion(self, messages: List[Dict[str, str]], model: str, **kwargs) -> str:
        try:
            if not model:
                model = "gpt-4o-mini"
                
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI provider error: {e}")
            raise
    
    async def generate_image(self, prompt: str, model: Optional[str] = None, **kwargs) -> str:
        try:
            response = await self.client.images.generate(
                model=model or "dall-e-3",
                prompt=prompt,
                size=kwargs.get("size", "1024x1024"),
                quality=kwargs.get("quality", "standard"),
                n=1
            )
            return response.data[0].url
        except Exception as e:
            logger.error(f"OpenAI image generation error: {e}")
            raise
    
    def get_available_models(self) -> List[ModelInfo]:
        return [
            ModelInfo("gpt-4o", ProviderType.OPENAI, "Most capable GPT-4 model", supports_vision=True),
            ModelInfo("gpt-4o-mini", ProviderType.OPENAI, "Affordable GPT-4 model", supports_vision=True),
            ModelInfo("o1", ProviderType.OPENAI, "Reasoning model"),
            ModelInfo("o1-mini", ProviderType.OPENAI, "Smaller reasoning model"),
            ModelInfo("dall-e-3", ProviderType.OPENAI, "DALL-E 3 image generation", supports_image_generation=True),
            ModelInfo("dall-e-2", ProviderType.OPENAI, "DALL-E 2 image generation", supports_image_generation=True),
        ]
    
    def supports_image_generation(self) -> bool:
        return True


class ClaudeProvider(BaseProvider):
    """Official Anthropic Claude API provider"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.client = AsyncAnthropic(api_key=api_key)
        
    async def chat_completion(self, messages: List[Dict[str, str]], model: str, **kwargs) -> str:
        try:
            if not model:
                model = "claude-3-5-haiku-latest"
            
            # Convert messages format for Claude
            system_message = None
            claude_messages = []
            
            for msg in messages:
                if msg["role"] == "system":
                    system_message = msg["content"]
                else:
                    claude_messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
            
            response = await self.client.messages.create(
                model=model,
                messages=claude_messages,
                system=system_message,
                max_tokens=kwargs.get("max_tokens", 4096)
            )
            
            return response.content[0].text
        except Exception as e:
            logger.error(f"Claude provider error: {e}")
            raise
    
    async def generate_image(self, prompt: str, model: Optional[str] = None, **kwargs) -> str:
        raise NotImplementedError("Claude does not support image generation")
    
    def get_available_models(self) -> List[ModelInfo]:
        return [
            ModelInfo("claude-3-5-sonnet-latest", ProviderType.CLAUDE, "Most capable Claude model"),
            ModelInfo("claude-3-5-haiku-latest", ProviderType.CLAUDE, "Fast and affordable"),
            ModelInfo("claude-3-opus-latest", ProviderType.CLAUDE, "Previous flagship model"),
        ]
    
    def supports_image_generation(self) -> bool:
        return False


class GeminiProvider(BaseProvider):
    """Official Google Gemini API provider"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        genai.configure(api_key=api_key)
        
    async def chat_completion(self, messages: List[Dict[str, str]], model: str, **kwargs) -> str:
        try:
            if not model:
                model = "gemini-2.0-flash-exp"
            
            # Initialize model
            gemini_model = genai.GenerativeModel(model)
            
            # Convert messages to Gemini format
            chat = gemini_model.start_chat(history=[])
            
            # Process messages
            for msg in messages:
                if msg["role"] == "user":
                    response = await asyncio.to_thread(
                        chat.send_message,
                        msg["content"]
                    )
                elif msg["role"] == "assistant":
                    # Add assistant messages to history
                    chat.history.append({
                        "role": "model",
                        "parts": [msg["content"]]
                    })
            
            return response.text
        except Exception as e:
            logger.error(f"Gemini provider error: {e}")
            raise
    
    async def generate_image(self, prompt: str, model: Optional[str] = None, **kwargs) -> str:
        try:
            # Use Imagen via Gemini
            model_name = model or "imagen-3.0-generate-001"
            imagen = genai.ImageGenerationModel(model_name)
            
            response = await asyncio.to_thread(
                imagen.generate_images,
                prompt=prompt,
                number_of_images=1,
                aspect_ratio=kwargs.get("aspect_ratio", "1:1")
            )
            
            # Save image and return URL or base64
            return response.images[0]._image_bytes
        except Exception as e:
            logger.error(f"Gemini image generation error: {e}")
            raise
    
    def get_available_models(self) -> List[ModelInfo]:
        return [
            ModelInfo("gemini-2.0-flash-exp", ProviderType.GEMINI, "Latest experimental model", supports_vision=True),
            ModelInfo("gemini-1.5-pro", ProviderType.GEMINI, "Advanced reasoning", supports_vision=True),
            ModelInfo("gemini-1.5-flash", ProviderType.GEMINI, "Fast multimodal", supports_vision=True),
            ModelInfo("imagen-3.0-generate-001", ProviderType.GEMINI, "Image generation", supports_image_generation=True),
        ]
    
    def supports_image_generation(self) -> bool:
        return True


class GrokProvider(BaseProvider):
    """xAI Grok API provider"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.api_key = api_key
        self.base_url = "https://api.x.ai/v1"
        
    async def chat_completion(self, messages: List[Dict[str, str]], model: str, **kwargs) -> str:
        try:
            if not model:
                model = "grok-2-latest"
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": model,
                "messages": messages,
                "temperature": kwargs.get("temperature", 0.7),
                "max_tokens": kwargs.get("max_tokens", 4096)
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=data
                ) as response:
                    result = await response.json()
                    
                    if response.status != 200:
                        raise Exception(f"Grok API error: {result}")
                    
                    return result["choices"][0]["message"]["content"]
                    
        except Exception as e:
            logger.error(f"Grok provider error: {e}")
            raise
    
    async def generate_image(self, prompt: str, model: Optional[str] = None, **kwargs) -> str:
        raise NotImplementedError("Grok does not support image generation yet")
    
    def get_available_models(self) -> List[ModelInfo]:
        return [
            ModelInfo("grok-2-latest", ProviderType.GROK, "Latest Grok-2 model"),
            ModelInfo("grok-2-mini", ProviderType.GROK, "Smaller, faster Grok model"),
        ]
    
    def supports_image_generation(self) -> bool:
        return False


class ProviderManager:
    """Manages all AI providers"""
    
    def __init__(self):
        self.providers: Dict[ProviderType, BaseProvider] = {}
        self.current_provider = ProviderType.FREE
        self._initialize_providers()
        
    def _validate_api_key(self, api_key: str, provider_name: str, pattern: Optional[str] = None) -> bool:
        """Validate API key format"""
        if not api_key or len(api_key) < 10:
            logger.warning(f"Invalid {provider_name} API key: too short")
            return False
            
        if pattern and not re.match(pattern, api_key):
            logger.warning(f"Invalid {provider_name} API key format")
            return False
            
        return True
    
    def _initialize_providers(self):
        """Initialize available providers based on API keys"""
        # Always add free provider
        self.providers[ProviderType.FREE] = FreeProvider()
        logger.info("Initialized free provider")
        
        # API key configurations: (env_var, provider_type, provider_class, validation_pattern)
        api_configs = [
            ("OPENAI_KEY", ProviderType.OPENAI, OpenAIProvider, r'^sk-[a-zA-Z0-9-]{43,}$'),
            ("CLAUDE_KEY", ProviderType.CLAUDE, ClaudeProvider, r'^sk-ant-[a-zA-Z0-9-]{95,}$'),
            ("GEMINI_KEY", ProviderType.GEMINI, GeminiProvider, r'^[a-zA-Z0-9_-]{39}$'),
            ("GROK_KEY", ProviderType.GROK, GrokProvider, r'^xai-[a-zA-Z0-9-]{40,}$')
        ]
        
        for env_key, provider_type, provider_class, pattern in api_configs:
            api_key = os.getenv(env_key)
            if api_key:
                if self._validate_api_key(api_key, provider_type.value, pattern):
                    try:
                        self.providers[provider_type] = provider_class(api_key)
                        logger.info(f"Initialized {provider_type.value} provider")
                    except Exception as e:
                        logger.error(f"Failed to initialize {provider_type.value}: {e}")
                else:
                    logger.warning(f"Skipping {provider_type.value} due to invalid API key")
    
    def get_provider(self, provider_type: Optional[ProviderType] = None) -> BaseProvider:
        """Get specific provider or current provider"""
        if provider_type:
            if provider_type not in self.providers:
                raise ValueError(f"Provider {provider_type.value} not available")
            return self.providers[provider_type]
        return self.providers[self.current_provider]
    
    def set_current_provider(self, provider_type: ProviderType):
        """Set current provider"""
        if provider_type not in self.providers:
            raise ValueError(f"Provider {provider_type.value} not available")
        self.current_provider = provider_type
    
    def get_available_providers(self) -> List[ProviderType]:
        """Get list of available providers"""
        return list(self.providers.keys())
    
    def get_all_models(self) -> Dict[ProviderType, List[ModelInfo]]:
        """Get all models from all providers"""
        result = {}
        for provider_type, provider in self.providers.items():
            result[provider_type] = provider.get_available_models()
        return result
    
    def get_provider_models(self, provider_type: ProviderType) -> List[ModelInfo]:
        """Get models for specific provider"""
        if provider_type not in self.providers:
            return []
        return self.providers[provider_type].get_available_models()