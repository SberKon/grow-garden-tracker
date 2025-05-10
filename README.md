# Garden Bot

Garden Bot is a Telegram bot that helps users track stock items in a virtual garden. Users can view current stock, track specific items, and receive notifications when tracked items become available.

## Project Structure

```
garden-bot
├── src
│   ├── bot.py          # Main logic for the GardenBot
│   └── constants.py    # Constants used throughout the bot
├── Dockerfile           # Instructions for building a Docker image
├── requirements.txt     # Python dependencies
├── fly.toml            # Configuration for deploying on Fly.io
├── .gitignore           # Files to ignore by Git
└── README.md            # Project documentation
```

## Setup Instructions

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd garden-bot
   ```

2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure your Telegram bot token in the `fly.toml` file.

4. Build and run the Docker container:
   ```bash
   docker build -t garden-bot .
   docker run garden-bot
   ```

## Usage

- Start the bot by sending the `/start` command in your Telegram chat.
- Use the `/menu` command to access the main menu and track items.

## Deployment

To deploy the bot on Fly.io, ensure you have the Fly CLI installed and run:
```bash
fly deploy
```

## License

This project is licensed under the MIT License.