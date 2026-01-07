import google.generativeai as genai
import os

# Replace with your actual key
api_key = "AIzaSyDidSB-GfBPuSA3JrCfiS7wEQYcT_vBiTA" 

genai.configure(api_key=api_key)

print("List of available models:")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(m.name)