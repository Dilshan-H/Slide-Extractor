# Lecture Slide Extractor

SlideExtractor is a lightweight desktop tool that automatically detects and extracts slide screenshots to PDF/JPEGs from screen-recorded lecture videos.
It removes duplicate frames, then lets you review everything in a visual grid before exporting your selection as a PDF or a folder of images. Built for students who are tired of rewinding a two-hour recording just to catch what was on slide 47!

## How to use (on Windows only)

1. Download the latest release from [here](https://github.com/Dilshan-H/Slide-Extractor/releases/latest).
2. Extract the zip archive and run `SlideExtractor.exe`
3. Click **Browse** and select a lecture video (`.mp4`, `.mkv`, `.avi`, etc.)
4. Adjust **Scene sensitivity** with the slider:
   - Move left → more frames captured (better recall, more false positives to review afterwards)
   - Move right → only big changes captured (fewer false positives, may miss some slides!)
   - **0.25–0.40** is a good starting point for most screen recordings
5. Adjust **Duplicate removal strictness** with the slider:
   - Move left → remove more duplicates  (may delete similar looking slides!)
   - Move right → keeps more frames (you may have to manually remove slides in the review screen)
   - **0.80–0.95** is a good starting point for most screen recordings
3. Click **▶ Extract Slides** and wait for FFmpeg to analyze the video
4. The **Review window** opens — all detected slides are shown as thumbnails
   - **Click a slide** to toggle it (dimmed = excluded)
   - Use **Select All / Deselect All** as needed
5. Click **📄 Generate PDF** — to save the slides as a PDF document OR click **🖼  Save Images** — to save all the selected slides as images to a folder.

> Based on the screen recording quality, transitions/animations in slides, other elements visible on video (ex: video feeds) you may have to test with multiple iterations while adjusting the sliders.

## Running from source (with Python)

1. Make sure you have [Python](https://www.python.org/downloads/) installed (Python 3.10 or higher recommended)
2. Download source code zip archive from [releases](https://github.com/Dilshan-H/Slide-Extractor/releases) OR clone the repository.
3. Use terminal/command prompt to navigate to the directory.

```bash
cd extracted-folder-name
```

```bash
# 1. Create and activate a virtual environment
python -m venv venv

# on Windows
venv\Scripts\activate
# on macOS/Linux
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
python slide_extractor.py
```

## Development

If you want to make changes to the script or build it from source follow these instructions.

### Setup development environment

Follow above mentioned steps in `Running from source` and use an editor like `VS Code` to make any code changes.

### Packaging as a standalone EXE

Install PyInstaller in your venv first:

```bash
pip install pyinstaller
```

Then build:

```bash
pyinstaller SlideExtractor.spec
```

The output will be in the `dist\` folder: `dist\SlideExtractor.exe`


## Tips & Troubleshooting

| Problem | Solution |
|---|---|
| Too many duplicate slides | Drag scene sensitivity slider right & Duplicate removal slider left |
| Some slides are missing | Drag scene sensitivity slider left & Adjust second slider as fits |
| Animations triggering extra frames | Slightly increase thresholds; remove extras in review |
| EXE is flagged by antivirus | Common with PyInstaller; add an exclusion or build it by yourself if you're worried |


---
<br/>
<footer>
<center>
Made with ❤ by Dilshan-H & Claude AI
<br/>
─── Because some lecturers teach everything and share nothing ───
</center>
</footer>
