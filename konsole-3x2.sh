#!/bin/bash
# Konsole 3x2 layout using tmux with mouse support
# This script creates a 3-column by 2-row layout matching the iTerm2 configuration

# Ensure tmux is installed
if ! command -v tmux &> /dev/null; then
    echo "tmux is not installed. Please install it first:"
    echo "  sudo apt install tmux"
    exit 1
fi

# Create tmux config with mouse support if it doesn't exist
TMUX_CONF="$HOME/.tmux.conf"
if ! grep -q "set -g mouse on" "$TMUX_CONF" 2>/dev/null; then
    echo "Enabling mouse support in tmux..."
    echo "" >> "$TMUX_CONF"
    echo "# Enable mouse support for clicking and resizing panes" >> "$TMUX_CONF"
    echo "set -g mouse on" >> "$TMUX_CONF"
    echo "Mouse support added to $TMUX_CONF"
fi

# Session name
SESSION="mrva-3x2"

# Kill existing session if it exists
tmux kill-session -t $SESSION 2>/dev/null

# Create new session with the first pane (P11)
tmux new-session -d -s $SESSION -c ~/work-gh/mrva/mrvaserver/

# Split horizontally to create P21 (middle column, top row)
tmux split-window -h -t $SESSION:0 -c ~/work-gh/mrva/mrvaagent

# Split horizontally again to create P31 (right column, top row)
tmux split-window -h -t $SESSION:0.1 -c ~/work-gh/mrva/mrva-docker

# Now create the bottom row by splitting each top pane vertically
# Split P11 to create P12 (left column, bottom row)
tmux select-pane -t $SESSION:0.0
tmux split-window -v -c ~/work-gh/mrva/mrvacommander

# Split P21 to create P22 (middle column, bottom row)
tmux select-pane -t $SESSION:0.2
tmux split-window -v -c ~/work-gh/mrva/gh-mrva

# Split P31 to create P32 (right column, bottom row)
tmux select-pane -t $SESSION:0.4
tmux split-window -v -c ~/work-gh/mrva/vscode-codeql

# Adjust the layout to be even
tmux select-layout -t $SESSION:0 tiled

# Select the first pane
tmux select-pane -t $SESSION:0.0

# Launch Konsole with the tmux session
konsole -e tmux attach-session -t $SESSION