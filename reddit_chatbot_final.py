from typing import List, Dict
import asyncio
import asyncpraw
from dataclasses import dataclass
import time
import threading
from openai import OpenAI
import random
import gradio as gr
import hashlib
from collections import OrderedDict
from datetime import datetime  # For timestamp conversion and dynamic dates

# OpenRouter API Configuration
OPENROUTER_API_KEY = "openrouter_api_key_here"
MODEL = "google/gemma-3-4b-it:free"
REQUEST_TIMEOUT = 60
CACHE_TIMEOUT = 3600

class LRUCache:
    def __init__(self, capacity=20):
        self.cache = OrderedDict()
        self.capacity = capacity
        self.expiration = {}
        
    def get(self, key):
        if key not in self.cache or time.time() > self.expiration.get(key, 0):
            if key in self.cache:
                self.cache.pop(key)
                self.expiration.pop(key)
            return None
        self.cache.move_to_end(key)
        return self.cache[key]
        
    def put(self, key, value, timeout=CACHE_TIMEOUT):
        self.cache[key] = value
        self.expiration[key] = time.time() + timeout
        self.cache.move_to_end(key)
        if len(self.cache) > self.capacity:
            oldest = next(iter(self.cache))
            self.cache.pop(oldest)
            self.expiration.pop(oldest)

@dataclass
class RedditCredentials:
    client_id: str
    client_secret: str
    user_agent: str

class RedditChatbot:
    def __init__(self, api_key=OPENROUTER_API_KEY, model=MODEL):
        self.client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
        self.model = model
        self.documents = []
        self.conversation_history = []
        self.topic = ""
        self.cache = LRUCache()
    
    def is_question_and_extract_topic(self, user_input: str) -> (bool, str): # type: ignore
        try:
            messages = [
                {
                    "role": "system",
                    "content": """Analyze the user's input and determine if it's requesting information or asking a question.
                    If it is, extract the main topic or search term.
                    Respond with:
                    - 'yes: [topic]' if it's a question or topic request
                    - 'no' if it's casual conversation
                    Examples:
                    - 'Tell me about Python' -> 'yes: Python'
                    - 'What's the weather like?' -> 'yes: weather'
                    - 'hello' -> 'no'
                    """
                },
                {"role": "user", "content": user_input}
            ]
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                timeout=REQUEST_TIMEOUT,
                max_tokens=50
            )
            response = completion.choices[0].message.content.strip().lower()
            if response.startswith('yes:'):
                return True, response[4:].strip()
            return False, ""
        except Exception as e:
            print(f"Error analyzing input: {str(e)}")
            return len(user_input.split()) > 1 or len(user_input) > 5, user_input
    
    def initialize_casual_conversation(self):
        current_date = datetime.now().strftime('%Y-%m-%d')
        self.conversation_history = [
            {
                "role": "system",
                "content": f"""You are a helpful and friendly assistant. Today's date is {current_date}. When the user asks about a topic or requests information, always use Reddit sources as your primary and preferred source by searching for relevant content and discussing the insights from the community. Use only the Reddit content provided in subsequent messages to generate your responses. If no relevant Reddit sources are found, use your general knowledge, mention that no Reddit sources were available, and note that your general knowledge may not reflect the very latest conditions as of {current_date}. For casual conversation, respond naturally."""
            }
        ]
    
    def set_documents(self, documents: List[Dict], topic: str):
        self.documents = documents
        self.topic = topic
        current_date = datetime.now().strftime('%Y-%m-%d')
        self.conversation_history.append({
            "role": "system",
            "content": f"""You now have access to Reddit knowledge about '{topic}'. The following content includes posts and comments with their creation dates, fetched as of today, {current_date}. Use this information as your sole source to discuss the topic in a conversational manner, addressing the user's input. Mention the dates when discussing the relevance or timeliness of the information.
{self._format_documents()}
Summarize the key points, insights, and common themes from the Reddit community. Only include source links if they enhance the discussion significantly. Do not use any other information beyond what's provided here."""
        })
    
    def _format_documents(self) -> str:
        if not self.documents:
            return "No documents available."
        formatted = ""
        for i, doc in enumerate(self.documents, 1):
            doc_type = "POST" if doc.get("type") == "post" else "COMMENT"
            formatted += f"[{i}] {doc_type}\n"
            if doc.get("type") == "post":
                formatted += f"Title: {doc.get('title', 'No title')}\n"
            else:
                formatted += f"On post: {doc.get('post_title', 'Unknown post')}\n"
            formatted += f"Author: {doc.get('author', 'Unknown')}\nCreated: {datetime.utcfromtimestamp(doc['created']).strftime('%Y-%m-%d') if 'created' in doc else 'Unknown date'}\nContent: {doc.get('content', 'No content')}\nURL: {doc.get('url', 'No URL')}\n\n"
        return formatted

class RedditBot:
    def __init__(self, credentials: RedditCredentials):
        self.credentials = credentials
        self.reddit = None
        
    async def initialize(self):
        self.reddit = asyncpraw.Reddit(
            client_id=self.credentials.client_id,
            client_secret=self.credentials.client_secret,
            user_agent=self.credentials.user_agent
        )
    
    async def search_content(self, query: str, limit: int = 5) -> List[Dict]:
        if not self.reddit:
            await self.initialize()
        results = []
        try:
            subreddit = await self.reddit.subreddit("all")
            async for post in subreddit.search(query, limit=limit, sort="relevance"):
                if post.selftext.lower() in ("[deleted]", "[removed]"):
                    continue
                results.append({
                    "type": "post",
                    "id": post.id,
                    "title": post.title,
                    "content": post.selftext,
                    "author": str(post.author) if post.author else "[deleted]",
                    "score": post.score,
                    "num_comments": post.num_comments,
                    "url": f"https://www.reddit.com{post.permalink}",
                    "created": post.created_utc
                })
                submission = await self.reddit.submission(id=post.id)
                await submission.comments.replace_more(limit=1)
                for comment in submission.comments[:1]:
                    if comment.body.lower() in ("[deleted]", "[removed]"):
                        continue
                    results.append({
                        "type": "comment",
                        "id": comment.id,
                        "content": comment.body,
                        "author": str(comment.author) if comment.author else "[deleted]",
                        "score": comment.score,
                        "post_title": post.title,
                        "url": f"https://www.reddit.com{comment.permalink}",
                        "created": comment.created_utc
                    })
            results.sort(key=lambda x: x.get("score", 0) + x.get("num_comments", 0) * 0.5, reverse=True)
            return results[:5]
        except Exception as e:
            print(f"Error searching content: {str(e)}")
            return []
    
    async def close(self):
        if self.reddit:
            await self.reddit.close()

class RedditChatbotGradioInterface:
    def __init__(self):
        self.credentials = RedditCredentials(
            client_id="client_id_here",
            client_secret="client_secret_here",
            user_agent="user_agent_here"
        )
        self.bot = None
        self.chatbot = RedditChatbot()
        self.chatbot.initialize_casual_conversation()
        self.is_initialized = False
        self.current_topic = None
        self.follow_up_threshold = 2
        self.topic_message_count = 0
        
    async def initialize_reddit(self):
        if not self.is_initialized:
            self.bot = RedditBot(self.credentials)
            await self.bot.initialize()
            self.is_initialized = True
            yield "Reddit client initialized successfully"
    
    async def process_message(self, message, history):
        if not self.is_initialized:
            async for msg in self.initialize_reddit():
                yield msg
        is_search_command = "reddit" in message.lower() or "search" in message.lower()
        is_question, query = self.chatbot.is_question_and_extract_topic(message)
        is_question = is_question or is_search_command
        is_follow_up = self.current_topic and self.topic_message_count < self.follow_up_threshold
        if is_follow_up:
            self.topic_message_count += 1
        else:
            self.topic_message_count = 0
            self.current_topic = None
        if not is_search_command:
            cache_key = hashlib.sha256(message.encode()).hexdigest()
            if cached_response := self.chatbot.cache.get(cache_key):
                for i in range(len(cached_response) + 1):
                    yield cached_response[:i]
                    await asyncio.sleep(random.uniform(0.001, 0.003))
                self.chatbot.conversation_history.append({"role": "assistant", "content": cached_response})
                return
        if is_question and not is_follow_up:
            yield "Let me check out what Reddit has to say about that..."
            self.current_topic = query
            results = await self.bot.search_content(query)
            current_date = datetime.now().strftime('%Y-%m-%d')
            if not results:
                self.chatbot.conversation_history.append({
                    "role": "system",
                    "content": f"No relevant Reddit sources found for '{query}' as of {current_date}. Use your general knowledge to discuss the topic, mention that no Reddit sources were available, and note that your information may not reflect the very latest conditions as of {current_date}."
                })
                self.chatbot.conversation_history.append({"role": "user", "content": message})
                yield f"Couldn’t find anything on Reddit about that as of {current_date}, so I’ll share what I know based on my general knowledge."
            else:
                self.chatbot.set_documents(results, query)
                self.topic_message_count = 1
                self.chatbot.conversation_history.append({"role": "user", "content": message})
        else:
            self.chatbot.conversation_history.append({"role": "user", "content": message})
            if is_follow_up and is_question:
                self.chatbot.conversation_history.insert(-1, {
                    "role": "system",
                    "content": f"This is a follow-up question about {self.current_topic}. Continue the discussion using the existing Reddit data provided previously, focusing on the new aspect the user is asking about."
                })
        try:
            stream_response = self.chatbot.client.chat.completions.create(
                model=self.chatbot.model,
                messages=self.chatbot.conversation_history,
                timeout=REQUEST_TIMEOUT,
                stream=True
            )
            full_response = ""
            for chunk in stream_response:
                if hasattr(chunk.choices[0], 'delta') and hasattr(chunk.choices[0].delta, 'content'):
                    if content := chunk.choices[0].delta.content:
                        for char in content:
                            full_response += char
                            yield full_response
                            await asyncio.sleep(random.uniform(0.001, 0.003))
            if full_response:
                yield full_response
                self.chatbot.conversation_history.append({"role": "assistant", "content": full_response})
                if not is_search_command:
                    self.chatbot.cache.put(cache_key, full_response)
        except Exception as e:
            yield f"Error with OpenRouter API: {str(e)}"
            if self.chatbot.conversation_history and self.chatbot.conversation_history[-1]["role"] == "user":
                self.chatbot.conversation_history.pop()

async def launch_gradio():
    interface = RedditChatbotGradioInterface()
    with gr.Blocks(css="footer {visibility: hidden}") as demo:
        gr.Markdown("# Reddit Chatbot")
        gr.Markdown("Chat with me about any topic. I can search Reddit for information!")
        chatbot = gr.Chatbot(height=500, type="messages")
        msg = gr.Textbox(placeholder="Type your message here...", container=False)
        clear = gr.Button("Clear")
        async def user(message, history):
            return "", history + [{"role": "user", "content": message}]
        async def bot(history):
            async for response in interface.process_message(history[-1]["content"], history):
                if len(history) == 0 or history[-1].get("role") != "assistant":
                    history.append({"role": "assistant", "content": response})
                else:
                    history[-1]["content"] = response
                yield history
        msg.submit(user, [msg, chatbot], [msg, chatbot], queue=False).then(bot, chatbot, chatbot)
        clear.click(lambda: [], None, chatbot, queue=False)
    await demo.launch(share=True)
    await interface.bot.close()

if __name__ == "__main__":
    try:
        asyncio.run(launch_gradio())
    except KeyboardInterrupt:
        print("\nProgram terminated by user.")
    except Exception as e:
        print(f"\nAn error occurred: {str(e)}")