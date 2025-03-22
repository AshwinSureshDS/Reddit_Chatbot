# Reddit Chatbot

A conversational AI assistant that searches Reddit for information and provides responses based on Reddit content. This chatbot uses the OpenRouter API to power its conversational capabilities and the Reddit API to fetch relevant posts and comments.

## Features

- Search Reddit for information on any topic
- Conversational interface powered by OpenRouter API (using Google's Gemma 3 4B model)
- Caching system for faster responses to repeated questions
- Follow-up question handling to maintain context in conversations
- Modern web interface using Gradio
- Streaming responses for a more natural conversation experience

## Requirements

This project requires Python 3.10+ and the following packages:

```
asyncpraw>=7.7.1
aiohttp>=3.8.5
numpy>=1.24.0
scikit-learn>=1.3.0
openai>=1.3.0
gradio>=4.0.0
```

You can install all required packages using the included `requirements.txt` file:

```bash
pip install -r requirements.txt
```

## Setup

### 1. Reddit API Credentials

To use this chatbot, you'll need to create a Reddit application to get API credentials:

1. Go to [Reddit's App Preferences](https://www.reddit.com/prefs/apps)
2. Click "Create App" or "Create Another App"
3. Fill in the following:
   - Name: RedditChatbot (or any name you prefer)
   - App type: Script
   - Description: A chatbot that searches Reddit for information
   - About URL: (leave blank)
   - Redirect URI: http://localhost:8000
4. Click "Create app"
5. Note your `client_id` (the string under your app name) and `client_secret`

### 2. OpenRouter API Key

This chatbot uses OpenRouter to access various language models:

1. Create an account at [OpenRouter](https://openrouter.ai/)
2. Generate an API key from your dashboard
3. Copy your API key for configuration

### 3. Configure the Chatbot

Open `reddit_chatbot_final.py` and update the following variables:

```python
# OpenRouter API Configuration
OPENROUTER_API_KEY = "your_openrouter_api_key_here"
```

And in the `RedditChatbotGradioInterface` class, update the Reddit credentials:

```python
self.credentials = RedditCredentials(
    client_id="your_reddit_client_id_here",
    client_secret="your_reddit_client_secret_here",
    user_agent="python:reddit-chatbot:v1.0 (by /u/your_username)"
)
```

## Running the Chatbot

To start the chatbot, run:

```bash
python reddit_chatbot_final.py
```

This will launch a Gradio web interface that you can access in your browser. The terminal will display the URL (typically http://127.0.0.1:7860).

## Usage

1. Type your question or topic in the text input field
2. The chatbot will search Reddit for relevant information
3. If Reddit content is found, the chatbot will summarize the key points and insights
4. If no relevant Reddit content is found, the chatbot will use its general knowledge
5. You can ask follow-up questions to get more details about the topic

## How It Works

1. The chatbot analyzes your input to determine if it's a question or information request
2. If it is, it extracts the main topic and searches Reddit for relevant posts and comments
3. It retrieves the most relevant content, including post titles, content, authors, and creation dates
4. The chatbot then uses OpenRouter API to generate a response based on the Reddit content
5. For follow-up questions, it maintains context about the current topic

## Customization

- **Model**: You can change the AI model by updating the `MODEL` variable
- **Cache Size**: Adjust the `capacity` parameter in the `LRUCache` class
- **Cache Timeout**: Modify the `CACHE_TIMEOUT` variable (in seconds)
- **Follow-up Threshold**: Change the `follow_up_threshold` in the `RedditChatbotGradioInterface` class

## Troubleshooting

- **Reddit API Rate Limits**: If you encounter rate limit errors, reduce the frequency of your requests
- **OpenRouter API Errors**: Check your API key and ensure you have sufficient credits
- **Missing Dependencies**: Make sure all required packages are installed using the requirements.txt file

## License

This project is available for educational purposes. Please respect Reddit's API terms of service when using this application.