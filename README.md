# Telegram Browser Agent

A modular, extensible Telegram-based browser automation agent that helps users perform tasks on LinkedIn and the web through natural conversation.

## Features

- **Natural Language Interface**: Chat with the bot to perform browser automation tasks
- **LinkedIn Automation**: Send connections, messages, search profiles, and more
- **Async Task Execution**: Bot can perform tasks while continuing the conversation
- **Learning System**: Stores successful workflows for future reference
- **Extensible Architecture**: Easy to add new tools and capabilities
- **Multi-User Support**: Designed for multiple users with individual preferences

## Architecture

```
┌─────────────────────────────────────────────────┐
│              Telegram Bot Layer                 │
│  (Receives messages, sends async updates)       │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│              Orchestrator Layer                  │
│  (Intent classification, task planning)         │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│              Memory Management                   │
│  (SQLite + embeddings for workflow storage)      │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│              Tool Execution Layer                │
│  (Browser automation, YouTube tools, etc.)       │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│              LLM Abstraction Layer               │
│  (OpenRouter, Anthropic, easy to swap)           │
└─────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose (recommended)
- Telegram Bot Token
- OpenRouter API Key

### Docker Setup (Recommended)

1. Clone the repository:
```bash
git clone <repository-url>
cd telegram-browser-agent
```

2. Copy the environment file:
```bash
cp .env.example .env
```

3. Edit `.env` with your credentials:
```env
TELEGRAM_BOT_TOKEN=your_bot_token
OPENROUTER_API_KEY=your_api_key
OPENROUTER_MODEL=openai/gpt-4o
```

4. Start the application:
```bash
docker-compose up -d
```

### Local Development Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate  # Windows
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
export TELEGRAM_BOT_TOKEN=your_bot_token
export OPENROUTER_API_KEY=your_api_key
export DATABASE_PATH=/app/data/agent.db
```

4. Run the application:
```bash
python -m src.main
```

## Project Structure

```
telegram-browser-agent/
├── src/
│   ├── main.py                 # Application entry point
│   ├── core/                   # Core agent logic
│   │   ├── orchestrator.py     # Main orchestrator
│   │   ├── state_manager.py    # Conversation state
│   │   └── async_task_manager.py
│   ├── llm/                    # LLM providers
│   │   ├── base.py            # Abstract base class
│   │   ├── openrouter.py      # OpenRouter implementation
│   │   └── anthropic.py       # Anthropic implementation
│   ├── memory/                 # Data storage
│   │   ├── database.py        # SQLite management
│   │   ├── embedding_store.py  # Semantic search
│   │   └── workflow_manager.py
│   ├── tools/                  # Tool implementations
│   │   ├── base.py            # Tool base class
│   │   ├── browser_use.py     # Browser automation
│   │   └── youtube_tools.py   # YouTube research
│   ├── telegram/               # Telegram integration
│   │   ├── bot.py             # Main bot
│   │   ├── message_router.py  # Message routing
│   │   └── async_sender.py    # Async messaging
│   ├── prompts/               # Prompt management
│   │   ├── system_prompts.py  # Static prompts
│   │   ├── dynamic_prompts.py # Dynamic prompts
│   │   └── linkedin_prompts.py
│   └── utils/                  # Utilities
│       ├── config.py          # Configuration
│       ├── logging.py         # Logging setup
│       └── helpers.py         # Helper functions
├── database/
│   └── schema.sql            # Database schema
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

## Usage

### LinkedIn Operations

```
User: Send connection requests to 5 product managers at Google

Bot: I'll help you find and connect with product managers at Google.
    Searching LinkedIn... Found 5 profiles.
    Sending connection requests...
    
    ✅ Sent 4/5 connection requests successfully
    - John Doe (Google) ✓
    - Jane Smith (Google) ✓
    - Bob Wilson (Google) - Already connected
    - Alice Brown (Google) ✓
    - Charlie Davis (Google) ✓
```

### Web Research

```
User: Research the latest AI trends on YouTube

Bot: I'll analyze recent AI-related videos for you.
    Downloading transcripts...
    Analyzing content...
    
    Key findings:
    1. "Introduction to LLMs" - 15K views, published 2 days ago
    2. "Building AI Agents" - 8K views, published 1 week ago
    3. "Future of AI in 2024" - 25K views, published 3 days ago
```

### Adding New Tools

1. Create a new tool class in `src/tools/`:
```python
from .base import BaseTool, ToolResult

class CustomTool(BaseTool):
    name = "custom_tool"
    description = "Custom tool description"
    category = "custom"
    
    async def execute(self, **kwargs) -> ToolResult:
        # Your implementation
        return ToolResult(success=True, data={})
```

2. Register the tool in `main.py`:
```python
tool_registry.register(CustomTool())
```

### Configuration

All configuration is managed through environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| TELEGRAM_BOT_TOKEN | Telegram bot token | Required |
| OPENROUTER_API_KEY | OpenRouter API key | Required |
| OPENROUTER_MODEL | Model to use | openai/gpt-4o |
| DATABASE_PATH | SQLite database path | /app/data/agent.db |
| HEADLESS_MODE | Browser headless mode | true |
| ENABLE_LEARNING | Enable workflow learning | true |
| ENABLE_YOUTUBE_TOOLS | Enable YouTube tools | false |

## Learning System

The agent learns from successful executions by:

1. **Recording Workflows**: Storing successful task patterns
2. **Keyword Extraction**: Extracting keywords for retrieval
3. **Embedding Storage**: Using semantic search for similarity
4. **Success Tracking**: Tracking success rates for each workflow

When a similar task is requested, the agent:
1. Checks the workflow database
2. Retrieves relevant successful workflows
3. Adapts the pattern to the current request
4. Executes and records the result

## Development

### Running Tests

```bash
pytest tests/
```

### Code Style

```bash
# Format code
black src/

# Lint code
ruff check src/

# Type checking
mypy src/
```

### Database Migrations

The database schema is in `database/schema.sql`. For new versions:

1. Create a new migration file
2. Apply migrations on startup
3. Update the schema.sql

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Support

For issues and questions:
- Open a GitHub issue
- Check the documentation
