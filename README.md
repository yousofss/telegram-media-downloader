# Telegram Media Downloader

This Python script allows you to download media (videos, photos, and documents) from Telegram channels using a user-friendly command-line interface.

## Features

- Download videos, photos, and documents from Telegram channels
- User-friendly command-line interface with colored output
- Continuous media selection without exiting
- Color-coded list showing already downloaded media
- Ability to switch between channels
- Resume interrupted downloads
- Configurable concurrent download limit and rate limiting
- Logging for better tracking and debugging

## Prerequisites

- Python 3.7 or higher
- Telegram API credentials (api_id and api_hash)

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yousofss/telegram-media-downloader.git
   cd telegram-media-downloader
   ```

2. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

3. Copy `config.yaml.example` to `config.yaml` and fill in your Telegram API credentials and preferences:
   ```
   cp config.yaml.example config.yaml
   ```
   Then edit `config.yaml` with your actual Telegram API credentials and desired settings.

## Usage

```
python main.py
```

Follow the on-screen prompts to:
1. Enter a channel ID or username
2. Select media to download
3. Choose a download directory
4. Continue downloading or switch to a different channel

## Contributing

Contributions, issues, and feature requests are welcome. Feel free to check the [issues page](https://github.com/yousofss/telegram-media-downloader/issues) if you want to contribute.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This tool is for educational purposes only. Make sure you have the right to download and use the media from the channels you access. The developers are not responsible for any misuse of this tool.
