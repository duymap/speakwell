# BE-5: English Tutor System Prompt

**File:** `server/prompts.py`
**Depends on:** None
**Team:** Backend

---

## Objective

Create the system prompt that defines GPT-4o's behavior as an English conversation tutor. This prompt is used by the `OpenAILLMService` in the Pipecat pipeline.

---

## Requirements

### 1. Module Structure

Create `server/prompts.py` with a single constant:

```python
ENGLISH_TUTOR_PROMPT = """..."""
```

This will be imported in `bot.py` as:
```python
from prompts import ENGLISH_TUTOR_PROMPT
```

### 2. Prompt Design Guidelines

The prompt must account for the fact that this is a **voice conversation**, not text chat:

- **No markdown/formatting**: The LLM output goes directly to TTS. Bullet points, headers, asterisks, code blocks, etc. will be spoken literally. The prompt must explicitly forbid these.
- **Concise responses**: Long responses create bad UX — the user has to wait silently while TTS synthesizes and plays a paragraph. Target 1-3 sentences per turn.
- **Natural speech patterns**: Encourage filler words, contractions, and natural pauses that sound good when spoken.
- **No lists or enumerations**: "First, second, third..." is fine spoken aloud, but numbered/bulleted lists are not.

### 3. Tutor Behavior

The tutor should:

1. **Start the conversation**: Greet the user warmly and ask what they'd like to talk about or what they're practicing.
2. **Maintain natural conversation flow**: Respond to what the user says, ask follow-up questions, share opinions.
3. **Correct mistakes gently**: When the user makes a grammar or vocabulary error, naturally rephrase it correctly in the response. Don't lecture — model correct usage.
4. **Adapt to level**: If the user speaks simply, keep responses simple. If they're advanced, use richer vocabulary.
5. **Encourage speaking**: If the user gives very short answers, ask open-ended questions to encourage longer responses.
6. **Stay in English**: Even if the user speaks in another language, gently redirect to English.

### 4. Prompt Content

Write a system prompt that covers:

```python
ENGLISH_TUTOR_PROMPT = """You are a friendly, patient English conversation tutor having a real-time voice conversation.

Your role:
- Have natural, engaging conversations to help the user practice English
- Gently correct grammar and vocabulary mistakes by naturally rephrasing in your response
- Adjust your language complexity to match the user's level
- Ask follow-up questions to keep the conversation flowing
- Be encouraging and supportive

Voice conversation rules (IMPORTANT):
- Keep responses to 1-3 sentences. This is a spoken conversation, not a written essay.
- Never use markdown, bullet points, numbered lists, asterisks, or any text formatting
- Never use special characters like *, #, -, or []
- Speak naturally as you would in a real face-to-face conversation
- Use contractions (I'm, you're, don't) and natural speech patterns
- Do not spell out URLs, code, or technical syntax

Start by greeting the user warmly and asking what they'd like to talk about today."""
```

### 5. Optional: Prompt Variants

If time permits, consider adding alternative prompts for different scenarios:

```python
# For beginners — simpler language, more repetition
BEGINNER_TUTOR_PROMPT = """..."""

# For advanced learners — idioms, nuanced vocabulary
ADVANCED_TUTOR_PROMPT = """..."""

# For specific topics — business English, travel, etc.
BUSINESS_ENGLISH_PROMPT = """..."""
```

These are **not required** for the MVP but useful for future extensibility.

---

## Testing

Since this is a prompt (not executable code), testing means verifying the LLM behaves correctly:

### Manual Test Script

Create `server/test_prompt.py`:

```python
"""Quick test to verify the tutor prompt produces good voice-friendly responses."""
import openai
import os

client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])

ENGLISH_TUTOR_PROMPT = "..."  # import from prompts.py

test_messages = [
    # Test: Initial greeting
    [],
    # Test: Simple response
    [{"role": "user", "content": "Hi, I want to practice English."}],
    # Test: Grammar correction
    [{"role": "user", "content": "Yesterday I go to the store and buyed some food."}],
    # Test: Short answer encouragement
    [{"role": "user", "content": "Yes."}],
    # Test: Non-English input
    [{"role": "user", "content": "Je ne parle pas bien anglais."}],
]

for i, messages in enumerate(test_messages):
    full_messages = [{"role": "system", "content": ENGLISH_TUTOR_PROMPT}] + messages
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=full_messages,
        max_tokens=150,
    )
    text = response.choices[0].message.content
    print(f"\n--- Test {i + 1} ---")
    print(f"User: {messages[-1]['content'] if messages else '(conversation start)'}")
    print(f"Tutor: {text}")

    # Checks
    assert '*' not in text, "Response contains asterisks (markdown)"
    assert '#' not in text, "Response contains hash (markdown)"
    assert '\n-' not in text, "Response contains bullet points"
    word_count = len(text.split())
    print(f"Word count: {word_count}")
    if word_count > 80:
        print("WARNING: Response may be too long for voice")
```

### Verification Checklist

Run the test script and verify:
- [ ] Initial greeting is warm and asks a question
- [ ] Responses are 1-3 sentences (under ~50 words)
- [ ] No markdown formatting in any response
- [ ] Grammar corrections are natural, not lecturing
- [ ] Short user answers get follow-up questions
- [ ] Non-English input is redirected to English gently

---

## Acceptance Criteria

- [ ] `server/prompts.py` exists with `ENGLISH_TUTOR_PROMPT` constant
- [ ] Prompt explicitly forbids markdown/formatting
- [ ] Prompt instructs concise responses (1-3 sentences)
- [ ] Test script confirms LLM behaves as expected
- [ ] No special characters appear in LLM responses
