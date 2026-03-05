# AI_Assistant
Python AI Assistant using OpenAI

# Project Setup Guide

## Important Notice

This project **does not include API keys**. For security reasons, API keys are stored as **environment variables** and are not uploaded to the repository.
To run this project successfully, you must **create your own API keys** and **set them as environment variables on your system**.

---

Generate Your API Keys

Create your own API keys from the following services:

Groq: https://console.groq.com/keys
Create API key - goto system environment variables, set variable name to groq_api and then insert your API key as the data.

Hugging Face: https://huggingface.co/settings/tokens
Create the API key the same, and set the environment variable to HF_TOKEN, and insert the API key as the data.

Next, create a folder in the same directory called models. 
In the model folder you can upload .gguf offline models that will be implemented into the application.
