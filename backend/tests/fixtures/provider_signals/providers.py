from anthropic import Anthropic
from openai import OpenAI

anthropic_client = Anthropic()
openai_client = OpenAI()
anthropic_client.messages.create(model="claude-sonnet-4-6", messages=[])
openai_client.responses.create(model="gpt-4.1", input="hello")
