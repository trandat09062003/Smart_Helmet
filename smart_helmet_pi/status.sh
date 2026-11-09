#!/bin/bash
systemctl --user status smart_helmet.service --no-pager
echo ""
echo "API Status (http://$(hostname -I | awk '{print $1}'):5000):"
curl -s http://localhost:5000/api/status | python3 -m json.tool 2>/dev/null
