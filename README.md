Urban Ebot Voice Controller
1. Project overview
Urban Ebot Voice Controller is a Windows desktop application for controlling an Urban Ebot / RoArm-M2 robotic arm using voice commands and a local web dashboard.
The application uses:
Python for controller logic.
Vosk for offline speech recognition.
PyAudio to capture microphone audio.
Flask and Flask-CORS for the local dashboard/API.
Requests to send commands to the robot HTTP API.
NumPy for audio/data processing where used.
PyInstaller to package the Python program as a Windows executable.
The goal is to recognize supported spoken commands, map them to predefined actions/gestures, and send movement commands to the robot. The dashboard provides another way to interact with the controller.
> This README describes the intended design and setup. Actual commands and robot behavior depend on the current Python code and robot configuration.
2. What the project is intended to do
Listen for supported voice commands through the computer microphone.
Recognize speech locally using the downloaded Vosk model; after setup, speech recognition does not require an internet connection.
Trigger command and gesture handlers implemented in the Python application.
Send supported movement requests to the robot at the configured IP address.
Provide a local browser dashboard, expected at `http://127.0.0.1:5000` when configured that way.
Allow the controller to be started by double-clicking a Windows `.exe`.
Possible future improvements include adding more commands, refining gestures, and improving status/error feedback. Treat only features present in the current source code as implemented.
3. Project folder layout
The project folder used in this guide is `D:\arm_bot`.
Before building:
```text
D:\arm_bot\
├── UrbanEbotController_app.py
├── build_urban_ebot_exe.bat
└── model\
    └── [Vosk model files and subfolders]
```
After building, PyInstaller typically creates:
```text
D:\arm_bot\
├── build\
├── dist\
│   └── UrbanEbotController\
│       ├── UrbanEbotController.exe
│       └── [supporting files]
├── model\
├── UrbanEbotController_app.py
├── build_urban_ebot_exe.bat
└── UrbanEbotController.spec
```
Keep the entire `dist\UrbanEbotController` folder together when using the folder-based (`--onedir`) build. Do not copy only the EXE to another location.
4. Software and dependencies
To run the packaged EXE
A compatible 64-bit Windows computer.
A working microphone and permission for desktop apps to access it.
The robot and computer connected to a network from which the configured robot IP is reachable.
The complete `dist\UrbanEbotController` folder, not just the `.exe`.
PyInstaller generally bundles Python and Python packages, but audio drivers, microphone permissions, model files, and network access still matter.
To edit the source or rebuild the EXE
Install:
Python 3.11 64-bit is a reasonable starting point; use a Python version compatible with the project's dependencies.
`flask`
`flask-cors`
`requests`
`numpy`
`vosk`
`pyaudio`
`pyinstaller`
The build script installs these packages with pip. Internet access is needed for initial package installation unless the packages are already available locally.
The Vosk model is a separate local model folder. Keep it named exactly `model` beside the Python source and build script.
5. Build or rebuild the EXE
Check that `UrbanEbotController_app.py`, `build_urban_ebot_exe.bat`, and `model\` are inside `D:\arm_bot`.
Double-click `build_urban_ebot_exe.bat`.
Wait for pip and PyInstaller to finish.
If the command window reports an error, capture the error and troubleshoot it before using the result.
Test the resulting file:
`D:\arm_bot\dist\UrbanEbotController\UrbanEbotController.exe`
The current build script uses PyInstaller's folder-based (`--onedir`) mode. It is easier to troubleshoot than a single-file build and requires the full generated folder to run.
6. Create a desktop shortcut
Open File Explorer.
Navigate to `D:\arm_bot\dist\UrbanEbotController`.
Find `UrbanEbotController.exe`.
Right-click it. On Windows 11, select Show more options if needed.
Choose Send to → Desktop (create shortcut). If that option is unavailable, choose Create shortcut and move the shortcut to the Desktop.
Double-click the desktop shortcut to start the controller.
The shortcut points to the EXE inside `dist`. Do not delete or move the target folder after creating the shortcut, or the shortcut may stop working.
7. Using the application
Connect the computer to the correct robot Wi-Fi/network.
Power on the robot and place it on a stable surface.
Make sure the arm's movement area is clear.
Launch the desktop shortcut.
If the application starts a local dashboard, open `http://127.0.0.1:5000` in a browser if it does not open automatically.
Grant microphone access if Windows asks.
Try only commands implemented in the current Python source. Start with a low-risk command and observe the robot closely.
The configured robot IP must match the actual robot address. The known setup previously used `192.168.4.1`; verify this before use if the robot's network has changed.
8. Safety notes
Keep hands, cables, tools, and other objects away from the arm's movement area.
Test new gestures with the arm unloaded and at a safe distance from people.
Do not assume a software STOP control is a hardware emergency stop. Software stop logic may only block later software commands and is not certified safety equipment.
Know how to use the robot's verified physical stop or power switch before testing.
Do not expose the local Flask dashboard or robot API to an untrusted network. The local dashboard is expected to use `127.0.0.1`; changing its bind address can expose it to other devices.
If a letter-A drawing motion is present, treat it as experimental joint-angle motion, not calibrated Cartesian drawing. Test with the pen off the paper and verify joint limits before attempting to draw.
9. Troubleshooting
Voice recognition does not work
Check Windows microphone privacy settings and microphone selection.
Confirm the `model` directory contains the expected Vosk model files and was included in the build.
Try a supported command clearly in a quiet environment.
The dashboard does not open
Try `http://127.0.0.1:5000` manually.
Check whether another program is using port 5000.
Look for errors in the application console, if one is shown.
The robot does not move
Confirm the robot is powered on and the computer is connected to its network.
Verify the robot IP address in the Python source.
Confirm the command is supported by the current code.
Check the robot API and network connection. Avoid repeatedly issuing movement commands when the cause is unknown.
The EXE or build fails
Keep the command window open and read the first error message.
Re-run `build_urban_ebot_exe.bat` after correcting the dependency or path issue.
If needed, test the Python source directly before rebuilding.
10. Current status and next improvements
The application has been packaged and the user has confirmed that the EXE starts. This confirms startup, but does not prove that every voice command, dashboard control, microphone path, or robot gesture works correctly.
Recommended next steps:
Test microphone recognition.
Test dashboard controls.
Test robot movement with the workspace clear and physical stop accessible.
Verify each gesture and joint limit.
Add one new voice command at a time and retest.
Keep a backup of the Python source, build script, and Vosk model.
11. Quick reference
Project source: `D:\arm_bot\UrbanEbotController_app.py`
Build script: `D:\arm_bot\build_urban_ebot_exe.bat`
Vosk model: `D:\arm_bot\model\`
Built app: `D:\arm_bot\dist\UrbanEbotController\UrbanEbotController.exe`
Local dashboard: `http://127.0.0.1:5000`
Robot IP used in the known setup: `192.168.4.1` (verify before use)
