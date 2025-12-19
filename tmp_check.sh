#!/bin/bash
sshpass -p 'reJect' ssh -o StrictHostKeyChecking=no gueee@192.168.1.232 'ls -la ~/gschpoozi/templates/toolboards/ | head -25'
echo "---"
sshpass -p 'reJect' ssh -o StrictHostKeyChecking=no gueee@192.168.1.232 'cat ~/gschpoozi/templates/toolboards/btt-ebb36-42-v1-2.json | head -5 || echo "FILE NOT FOUND"'

