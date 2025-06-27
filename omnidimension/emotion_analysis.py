"""
emotion_analysis.py

A reusable class-based module for emotion analysis using Omnidimension (omnidim).
Supports repeated calls for:
- Plain text
- Audio/voice files (wav/mp3)
- Pre-transcribed text
"""

import os
import omnidim

class EmotionAnalyzer:
    def __init__(self, api_key=None):
        """
        Initialize the Omnidimension client for repeated use.
        """
        self.api_key = api_key or os.getenv('OMNIDIM_API_KEY')
        if not self.api_key:
            raise ValueError("Omnidimension API key not found. Set OMNIDIM_API_KEY environment variable or pass api_key.")
        self.client = omnidim.Client(api_key=self.api_key)

    def analyze_text(self, text):
        """
        Analyze emotion(s) in the given text.

        Args:
            text (str): The input text to analyze.

        Returns:
            dict: The emotion analysis result as returned by Omnidimension API.
        """
        try:
            return self.client.emotions(text)
        except Exception as e:
            return {"error": str(e)}

    def analyze_audio(self, audio_path):
        """
        Analyze emotions in an audio file (wav/mp3 supported).

        Args:
            audio_path (str): Path to the audio file.

        Returns:
            dict: The emotion analysis result as returned by Omnidimension API.
        """
        try:
            return self.client.emotions_from_audio(audio_path)
        except Exception as e:
            return {"error": str(e)}

    def analyze_transcribed_text(self, transcribed_text):
        """
        Analyze emotion(s) in pre-transcribed text.

        Args:
            transcribed_text (str): Transcribed text to analyze.

        Returns:
            dict: The emotion analysis result as returned by Omnidimension API.
        """
        return self.analyze_text(transcribed_text)

    def analyze(self, input_data, input_type="text"):
        """
        Unified method to analyze emotion based on input type.

        Args:
            input_data (str): Text, pre-transcribed text, or path to audio file.
            input_type (str): One of ['text', 'audio', 'transcribed']

        Returns:
            dict: The emotion analysis result.
        """
        if input_type == "audio":
            return self.analyze_audio(input_data)
        elif input_type == "transcribed":
            return self.analyze_transcribed_text(input_data)
        else:
            return self.analyze_text(input_data)