#!/bin/bash
cd -- "$(dirname -- "$0")"
clear
echo "Simple Music Library Player - macOS Installer"
echo "==============================================="
echo
bash "./install.sh"
status=$?
echo
if [ $status -eq 0 ]; then
    echo "Installation finished successfully."
else
    echo "Installation stopped with an error (code $status)."
fi
echo
read -r -p "Press Return to close this window..." _
exit $status
