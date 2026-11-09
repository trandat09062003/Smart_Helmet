#!/bin/bash
systemctl --user start smart_helmet.service
echo "[OK] Da khoi dong dich vu Smart Helmet 360."
echo "Web Dashboard: http://$(hostname -I | awk '{print $1}'):5000"
echo "Xem log: journalctl --user -u smart_helmet.service -f"
