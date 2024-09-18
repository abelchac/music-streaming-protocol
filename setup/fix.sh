#!/bin/bash

# Print script commands.
set -x
# Exit on errors.
set -e

sudo apt-get update
sudo apt-get install -y linux-modules-extra-`uname -r` alsa alsa-utils pulseaudio pulseaudio-utils
sudo modprobe snd
sudo modprobe snd-hda-intel
sudo alsa force-reload
sudo alsactl init
amixer set Master 100%
amixer set Master unmute

