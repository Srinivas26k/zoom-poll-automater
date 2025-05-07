# Zoom Poll Automator

Automatically generate and post polls in your Zoom meetings based on ongoing discussions!

## 🚀 Quick Start (For Everyone!)

### One-Time Setup:

1. Download and install these two programs:
   - [Python](https://www.python.org/downloads/) (Click "Add Python to PATH" during installation!)
   - [Ollama](https://ollama.ai/)

2. Get your Zoom credentials:
   - Go to [Zoom Marketplace](https://marketplace.zoom.us/)
   - Click "Develop" → "Build App"
   - Choose "OAuth" type app
   - Set Redirect URL to: `http://localhost:8000/oauth/callback`
   - Copy your Client ID and Client Secret

3. Download this project:
   - Click the green "Code" button above
   - Choose "Download ZIP"
   - Extract the ZIP file anywhere on your computer

### Every Time You Want to Run:

1. Make sure Ollama is running (Start Ollama from your applications)
2. Just double-click:
   - Windows: `start.bat`
   - Mac/Linux: `start.sh`

That's it! The script will:
- Set everything up automatically
- Ask for your Zoom credentials (first time only)
- Start generating polls in your meeting!

## 📝 What It Does

1. Records your meeting audio
2. Converts speech to text
3. Creates relevant polls based on the discussion
4. Posts them automatically to your Zoom meeting

## ⚙️ Troubleshooting

If you see:
- "Python is not installed" → Install Python and check "Add Python to PATH"
- "Ollama is not running" → Open Ollama before running the script
- Audio device not found → Check your microphone is connected
- Can't connect to Zoom → Make sure your Client ID and Secret are correct

## 🎥 Need Help?

Check out our video tutorial: [Link to your tutorial video]

## 📜 License

MIT License