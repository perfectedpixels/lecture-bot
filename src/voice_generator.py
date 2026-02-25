"""
ElevenLabs Voice Generator for Lecture Bot
Generates audio from text responses using ElevenLabs API
"""

import os
import requests
from typing import Optional
import base64

# Try to import streamlit for secrets
try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False

class VoiceGenerator:
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize ElevenLabs voice generator
        
        Args:
            api_key: ElevenLabs API key (or set ELEVENLABS_API_KEY env var or Streamlit secret)
        """
        # Try Streamlit secrets first, then env var, then parameter
        if api_key:
            self.api_key = api_key
        else:
            # Try Streamlit secrets
            try:
                if HAS_STREAMLIT and hasattr(st, 'secrets'):
                    try:
                        self.api_key = st.secrets.get('ELEVENLABS_API_KEY')
                    except:
                        self.api_key = None
                else:
                    self.api_key = None
            except:
                self.api_key = None
            
            # Fall back to env var
            if not self.api_key:
                self.api_key = os.getenv('ELEVENLABS_API_KEY')
            
        if not self.api_key:
            raise ValueError("ElevenLabs API key required. Set ELEVENLABS_API_KEY env var or add to Streamlit secrets")
        
        self.base_url = "https://api.elevenlabs.io/v1"
        
        # Voice IDs - Chris voice
        self.voices = {
            "chris": "iP95p4xoKVk53GoZ742B"  # Chris voice ID
        }
    
    def generate_audio(self, text: str, voice: str = "chris") -> bytes:
        """
        Generate audio from text using ElevenLabs API
        
        Args:
            text: Text to convert to speech
            voice: Voice name (default: "chris")
            
        Returns:
            Audio data as bytes (MP3 format)
        """
        voice_id = self.voices.get(voice.lower())
        if not voice_id:
            raise ValueError(f"Voice '{voice}' not found. Available: {list(self.voices.keys())}")
        
        url = f"{self.base_url}/text-to-speech/{voice_id}"
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key
        }
        
        data = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }
        
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code != 200:
            raise Exception(f"ElevenLabs API error: {response.status_code} - {response.text}")
        
        return response.content
    
    def generate_audio_base64(self, text: str, voice: str = "chris") -> str:
        """
        Generate audio and return as base64 string for embedding in HTML
        
        Args:
            text: Text to convert to speech
            voice: Voice name (default: "chris")
            
        Returns:
            Base64 encoded audio data
        """
        audio_bytes = self.generate_audio(text, voice)
        return base64.b64encode(audio_bytes).decode('utf-8')
    
    def get_voice_sample_waveform(self, voice: str = "chris") -> Optional[list]:
        """
        Get waveform data for a voice sample
        
        Args:
            voice: Voice name (default: "chris")
            
        Returns:
            List of floats representing waveform, or None if unavailable
        """
        voice_id = self.voices.get(voice.lower())
        if not voice_id:
            return None
        
        try:
            # First, get the voice samples
            url = f"{self.base_url}/voices/{voice_id}"
            headers = {"xi-api-key": self.api_key}
            
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                return None
            
            voice_data = response.json()
            samples = voice_data.get('samples', [])
            
            if not samples:
                return None
            
            # Get waveform for first sample
            sample_id = samples[0].get('sample_id')
            if not sample_id:
                return None
            
            waveform_url = f"{self.base_url}/voices/{voice_id}/samples/{sample_id}/waveform"
            waveform_response = requests.get(waveform_url, headers=headers)
            
            if waveform_response.status_code == 200:
                waveform_data = waveform_response.json()
                return waveform_data.get('visual_waveform', [])
            
            return None
            
        except Exception as e:
            print(f"Error getting waveform: {e}")
            return None
    
    def list_voices(self) -> dict:
        """
        List all available voices from ElevenLabs
        
        Returns:
            Dictionary of voice data
        """
        url = f"{self.base_url}/voices"
        headers = {"xi-api-key": self.api_key}
        
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            raise Exception(f"ElevenLabs API error: {response.status_code}")
        
        return response.json()
