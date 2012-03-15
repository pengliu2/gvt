@echo off
@echo Waiting for device...
adb wait-for-device
adb devices
@echo pulling logs...
adb shell cat /proc/wakelocks > ./wakelocks.txt
adb logcat -d > main.txt
adb logcat -b events -d > events.txt
adb logcat -b system -d > system.txt
adb shell dmesg > dmesg.txt
@echo ...............DONE!
@echo please attach wakelocks.txt main.txt, events.txt system.txt and dmesg.txt in current folder to CR
