# systems-monitor
for my systems project

installer:
    make runnable: chmod +x installer.bash
    run: ./setup_face_tracker.sh

verify:
    make runnable: chmod +x verify_tracker_install.bash
    run: ./verify_tracker_install.bash

start program:
    ~/tracker-file/start_tracker.sh
