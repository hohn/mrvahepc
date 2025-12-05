"""
MRVA Workflow UI - Interactive Tkinter GUI for managing MRVA workflow steps.

This module provides a graphical interface for executing the 7-step MRVA workflow:
1. Check gh-mrva tool
2. Setup configuration
3. Launch DB selector GUI
4. Select query file
5. Submit MRVA job
6. Check status
7. Download results
"""

import tkinter as tk
from tkinter import filedialog, ttk
import subprocess
import threading
import os
import re
from pathlib import Path
from datetime import datetime
from queue import Queue, Empty


class WorkflowUI:
    """Main UI class for MRVA workflow management."""

    def __init__(self, root, container_name="mrva-ghmrva"):
        """
        Initialize the workflow UI.

        Args:
            root: Tkinter root window
            container_name: Name of the Docker container to execute commands in
        """
        self.root = root
        self.container_name = container_name
        self.root.title("MRVA Workflow Manager")
        self.root.geometry("1200x600")

        # Data structures
        self.step_buttons = {}
        self.path_entries = {}
        self.selected_query_path = tk.StringVar()
        self.session_number = tk.StringVar()
        self.output_queue = Queue()

        # Initialize paths from environment
        self._init_paths()

        # Generate default session number
        self._generate_session_number()

        # Create UI layout
        self._create_widgets()

        # Start queue processor for thread-safe UI updates
        self._process_output_queue()

    def _init_paths(self):
        """Initialize path configuration from environment variables."""
        self.paths = {
            "GH-MRVA Dir": os.getenv("MRVA_GH_MRVA_DIR", "~/work-gh/mrva/gh-mrva"),
            "HEPC Dir": os.getenv("MRVA_HEPC_DIR", "~/work-gh/mrva/mrvahepc"),
            "Metadata DB": os.getenv(
                "MRVA_METADATA_DB", "db-collection-host.tmp/metadata.sql"
            ),
            "Selection JSON": os.getenv(
                "MRVA_SELECTION_JSON", "~/work-gh/mrva/gh-mrva/gh-mrva-selection.json"
            ),
        }

    def _generate_session_number(self):
        """Generate a timestamp-based session number."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.session_number.set(f"mirva-session-{timestamp}")

    def _create_widgets(self):
        """Create all UI widgets and layout."""
        # Main container
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Top panel: Configuration
        self._create_config_panel(main_frame)

        # Bottom container: Split into left (steps) and right (output)
        bottom_frame = tk.Frame(main_frame)
        bottom_frame.pack(fill=tk.BOTH, expand=True)

        # Left panel: Steps
        self._create_steps_panel(bottom_frame)

        # Separator
        separator = ttk.Separator(bottom_frame, orient=tk.VERTICAL)
        separator.pack(side=tk.LEFT, fill=tk.Y, padx=5)

        # Right panel: Output
        self._create_output_panel(bottom_frame)

    def _create_config_panel(self, parent):
        """Create the configuration panel with editable paths."""
        config_frame = tk.LabelFrame(
            parent, text="Configuration", padx=10, pady=10, relief=tk.GROOVE, borderwidth=2
        )
        config_frame.pack(fill=tk.X, padx=5, pady=5)

        for i, (label, default) in enumerate(self.paths.items()):
            tk.Label(config_frame, text=f"{label}:", anchor=tk.W, width=15).grid(
                row=i, column=0, sticky=tk.W, padx=5, pady=3
            )
            entry = tk.Entry(config_frame, width=70)
            entry.insert(0, default)
            entry.grid(row=i, column=1, sticky=tk.EW, padx=5, pady=3)
            self.path_entries[label] = entry

        config_frame.columnconfigure(1, weight=1)

    def _create_steps_panel(self, parent):
        """Create the left panel with step buttons and controls."""
        steps_frame = tk.Frame(parent, width=400)
        steps_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5)
        steps_frame.pack_propagate(False)

        # Title
        title_label = tk.Label(
            steps_frame, text="Workflow Steps", font=("Arial", 12, "bold")
        )
        title_label.pack(pady=(0, 10))

        # Step buttons
        self.button_frame = tk.Frame(steps_frame)
        self.button_frame.pack(fill=tk.X)

        steps = [
            ("Check Tool", self._step1_check_tool),
            ("Setup Config", self._step2_setup_config),
            ("Launch DB Selector", self._step3_launch_db_selector),
            ("Browse Queries", self._step4_browse_queries),
            ("Submit Job", self._step5_submit_job),
            ("Check Status", self._step6_check_status),
            ("Download Results", self._step7_download_results),
        ]

        for i, (label, command) in enumerate(steps, start=1):
            self._create_step_button(i, label, command)

        # Separator
        ttk.Separator(steps_frame, orient=tk.HORIZONTAL).pack(
            fill=tk.X, pady=10
        )

        # Session number
        session_frame = tk.LabelFrame(steps_frame, text="Session", padx=5, pady=5)
        session_frame.pack(fill=tk.X, pady=5)
        self.session_text = tk.Text(
            session_frame,
            height=2,
            wrap=tk.WORD,
            font=("TkDefaultFont", 9),
        )
        self.session_text.pack(fill=tk.X)
        # Initialize with default session number
        self.session_text.insert("1.0", self.session_number.get())
        self.session_text.bind("<<Modified>>", self._on_session_text_modified)

        # Query file display
        query_frame = tk.LabelFrame(steps_frame, text="Selected Query", padx=5, pady=5)
        query_frame.pack(fill=tk.X, pady=10)
        query_label = tk.Label(
            query_frame,
            textvariable=self.selected_query_path,
            anchor=tk.W,
            wraplength=370,
            justify=tk.LEFT,
            fg="blue",
            height=2,
        )
        query_label.pack(fill=tk.X)

    def _create_output_panel(self, parent):
        """Create the right panel with scrollable output text."""
        output_frame = tk.Frame(parent)
        output_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        # Title
        tk.Label(output_frame, text="Output", font=("Arial", 12, "bold")).pack(
            anchor=tk.W, pady=(0, 5)
        )

        # Text widget with scrollbar
        text_frame = tk.Frame(output_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.output_text = tk.Text(
            text_frame,
            wrap=tk.WORD,
            width=80,
            height=40,
            yscrollcommand=scrollbar.set,
            state=tk.DISABLED,
            font=("Courier", 9),
        )
        self.output_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.output_text.yview)

        # Configure text tags
        self.output_text.tag_config(
            "command", foreground="blue", font=("Courier", 9, "bold")
        )
        self.output_text.tag_config(
            "filepath", foreground="darkblue", underline=True
        )
        self.output_text.tag_config("error", foreground="red")

    def _create_step_button(self, step_num, label, command):
        """Create a step button with tracking."""
        button = tk.Button(
            self.button_frame,
            text=f"Step {step_num}: {label}",
            command=lambda: command(step_num),
            width=28,
            anchor=tk.W,
            padx=5,
            pady=5,
        )
        button.pack(fill=tk.X, pady=2)
        self.step_buttons[step_num] = button

    def _update_button_color(self, step_num, color):
        """Update button background color based on status."""
        if step_num in self.step_buttons:
            if color == "green":
                self.step_buttons[step_num].config(bg="#90EE90")
            elif color == "red":
                self.step_buttons[step_num].config(bg="#FFB6C6")
            else:
                self.step_buttons[step_num].config(bg="SystemButtonFace")

    def _get_path(self, key):
        """Get expanded path from configuration."""
        path = self.path_entries[key].get()
        return Path(path).expanduser().resolve()

    def _on_session_text_modified(self, _event=None):
        """Update session_number StringVar when Text widget is modified."""
        # Get current text content (strip trailing newline)
        session_text = self.session_text.get("1.0", "end-1c").strip()
        self.session_number.set(session_text)
        # Reset the modified flag
        self.session_text.edit_modified(False)

    def _log_command(self, command):
        """Log command to output area with highlighting."""
        self.output_queue.put(("command", f"\n$ {command}\n"))

    def _append_output(self, text, tag=None):
        """Queue output text for display."""
        self.output_queue.put((tag or "normal", text))

    def _process_output_queue(self):
        """Process queued output updates (thread-safe)."""
        try:
            while True:
                tag, text = self.output_queue.get_nowait()
                self.output_text.config(state=tk.NORMAL)

                if tag == "command":
                    self.output_text.insert(tk.END, text, "command")
                elif tag == "filepath":
                    self.output_text.insert(tk.END, text, "filepath")
                elif tag == "error":
                    self.output_text.insert(tk.END, text, "error")
                else:
                    self.output_text.insert(tk.END, text)
                    # Highlight file paths in normal text
                    self._highlight_file_paths_in_last_insert(text)

                self.output_text.see(tk.END)
                self.output_text.config(state=tk.DISABLED)
        except Empty:
            pass
        finally:
            self.root.after(100, self._process_output_queue)

    def _highlight_file_paths_in_last_insert(self, text):
        """Apply filepath highlighting to recently inserted text."""
        pattern = r"(?:~/[^\s]+|/[^\s]+|[a-zA-Z0-9_.-]+\.(?:json|sql|ql|yml|yaml))"
        for match in re.finditer(pattern, text):
            # Calculate position in text widget
            start_pos = f"end-{len(text)}c+{match.start()}c"
            end_pos = f"end-{len(text)}c+{match.end()}c"
            self.output_text.tag_add("filepath", start_pos, end_pos)

    def _execute_command(self, command, step_num, shell_command=None):
        """
        Execute a command in a separate thread and update UI.

        Args:
            command: Display command (for logging)
            step_num: Step number for button color update
            shell_command: Actual shell command to execute (if different from command)
        """
        self._log_command(command)
        actual_command = shell_command if shell_command else command

        def run():
            try:
                process = subprocess.Popen(
                    actual_command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )

                for line in process.stdout:
                    self._append_output(line)

                process.wait()

                if process.returncode == 0:
                    self.root.after(0, self._update_button_color, step_num, "green")
                    self._append_output(
                        f"\n[Step {step_num} completed successfully]\n", "command"
                    )
                else:
                    self.root.after(0, self._update_button_color, step_num, "red")
                    self._append_output(
                        f"\n[Step {step_num} failed with exit code {process.returncode}]\n",
                        "error",
                    )
            except Exception as e:
                self.root.after(0, self._update_button_color, step_num, "red")
                self._append_output(f"\nError: {str(e)}\n", "error")

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

    def _execute_background_command(self, command, step_num):
        """Execute a command in background without waiting."""
        self._log_command(f"{command} &")
        try:
            subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self._append_output(f"[Launched in background]\n")
            self._update_button_color(step_num, "green")
        except Exception as e:
            self._append_output(f"\nError: {str(e)}\n", "error")
            self._update_button_color(step_num, "red")

    # Step implementations

    def _step1_check_tool(self, step_num):
        """Step 1: Check gh-mrva tool availability and create directory structure."""
        # First create the directory structure in the container
        setup_command = (
            f"docker exec -i {self.container_name} bash -c "
            f'"mkdir -p ~/work-gh/mrva/gh-mrva && gh-mrva -h"'
        )
        self._execute_command(setup_command, step_num)

    def _step2_setup_config(self, step_num):
        """Step 2: Setup gh-mrva configuration."""
        config_content = """codeql_path: not-used/codeql-path
controller: not-used/mirva-controller
list_file: $HOME/work-gh/mrva/gh-mrva/gh-mrva-selection.json"""

        command = (
            f"docker exec -i {self.container_name} bash -c '"
            f"mkdir -p ~/.config/gh-mrva && "
            f"cat > ~/.config/gh-mrva/config.yml <<EOF\n{config_content}\nEOF\n"
            f"echo \"Configuration created at ~/.config/gh-mrva/config.yml\"'"
        )

        display_command = f"docker exec -i {self.container_name} bash -c 'mkdir -p ~/.config/gh-mrva && cat > ~/.config/gh-mrva/config.yml <<EOF...'"
        self._execute_command(display_command, step_num, shell_command=command)

    def _step3_launch_db_selector(self, step_num):
        """Step 3: Launch DB selector GUI in background and copy selection to container."""
        hepc_dir = self._get_path("HEPC Dir")
        metadata_db = self._get_path("Metadata DB")
        selection_json = self._get_path("Selection JSON")

        # Store selection path for later use
        self.selection_json_path = selection_json

        command = (
            f"{hepc_dir}/bin/db-selector-gui "
            f"--metadata_db_path {metadata_db} "
            f"--gh_mrva_output {selection_json}"
        )

        self._execute_background_command(command, step_num)

        # Note to user about copying the file
        self._append_output(
            "\nNote: After making your selection and clicking 'Export GH-MRVA Format',\n"
            "the selection file will be written to the host. You'll need to proceed to\n"
            "the next step to copy it to the container.\n",
            "normal"
        )

    def _step4_browse_queries(self, step_num):
        """Step 4: Browse and select query file."""
        gh_mrva_dir = self._get_path("GH-MRVA Dir")

        # Ensure sample queries exist
        self._ensure_sample_queries(gh_mrva_dir)

        # Open file dialog
        initial_dir = gh_mrva_dir
        query_file = filedialog.askopenfilename(
            title="Select CodeQL Query",
            initialdir=initial_dir,
            filetypes=[("CodeQL Query", "*.ql"), ("All Files", "*.*")],
        )

        if query_file:
            self.selected_query_path.set(query_file)
            self._log_command(f"Selected query: {query_file}")
            self._append_output(f"Query selected: {query_file}\n")
            self._update_button_color(step_num, "green")
        else:
            self._append_output("No query file selected\n", "error")

    def _ensure_sample_queries(self, base_dir):
        """Create sample query files if they don't exist."""
        queries = {
            "FlatBuffersFunc.ql": '''/**
 * @name pickfun
 * @description Pick function from FlatBuffers
 * @kind problem
 * @id cpp-flatbuffer-func
 * @problem.severity warning
 */

import cpp

from Function f
where
  f.getName() = "MakeBinaryRegion" or
  f.getName() = "microprotocols_add"
select f, "definition of MakeBinaryRegion"
''',
            "Fprintf.ql": '''/**
 * @name findPrintf
 * @description Find calls to plain fprintf
 * @kind problem
 * @id cpp-fprintf-call
 * @problem.severity warning
 */

import cpp

from FunctionCall fc
where
  fc.getTarget().getName() = "fprintf"
select fc, "call of fprintf"
''',
        }

        for filename, content in queries.items():
            query_path = base_dir / filename
            if not query_path.exists():
                try:
                    query_path.write_text(content)
                    self._append_output(f"Created sample query: {query_path}\n")
                except Exception as e:
                    self._append_output(
                        f"Warning: Could not create {filename}: {e}\n", "error"
                    )

    def _step5_submit_job(self, step_num):
        """Step 5: Submit MRVA job - copy files to container then submit."""
        query_path = self.selected_query_path.get()
        session = self.session_number.get()
        selection_json = self._get_path("Selection JSON")

        if not query_path:
            self._append_output("Error: No query file selected\n", "error")
            self._update_button_color(step_num, "red")
            return

        if not session:
            self._append_output("Error: No session number provided\n", "error")
            self._update_button_color(step_num, "red")
            return

        # Get just the filename for the query
        query_filename = Path(query_path).name
        container_query_path = f"~/work-gh/mrva/gh-mrva/{query_filename}"

        # Multi-step command:
        # 1. Copy selection JSON to container
        # 2. Copy query file to container
        # 3. Submit the job
        command = (
            f"cat '{selection_json}' | "
            f"docker exec -i {self.container_name} bash -c 'cat > ~/work-gh/mrva/gh-mrva/gh-mrva-selection.json' && "
            f"cat '{query_path}' | "
            f"docker exec -i {self.container_name} bash -c 'cat > {container_query_path}' && "
            f"docker exec -i {self.container_name} bash -c '"
            f"cd ~/work-gh/mrva/gh-mrva/ && "
            f"gh-mrva submit --language cpp --session {session} "
            f"--list mirva-list --query {container_query_path}'"
        )

        display_command = (
            f"# Copy selection file and query to container, then submit\n"
            f"cat {selection_json} | docker exec -i {self.container_name} ... && \n"
            f"cat {query_path} | docker exec -i {self.container_name} ... && \n"
            f"docker exec -i {self.container_name} bash -c 'cd ~/work-gh/mrva/gh-mrva/ && gh-mrva submit ...'"
        )

        self._execute_command(display_command, step_num, shell_command=command)

    def _step6_check_status(self, step_num):
        """Step 6: Check job status."""
        session = self.session_number.get()

        if not session:
            self._append_output("Error: No session number provided\n", "error")
            self._update_button_color(step_num, "red")
            return

        command = (
            f"docker exec -i {self.container_name} bash -c "
            f'"gh-mrva status --session {session}"'
        )

        self._execute_command(command, step_num)

    def _step7_download_results(self, step_num):
        """Step 7: Download results."""
        session = self.session_number.get()

        if not session:
            self._append_output("Error: No session number provided\n", "error")
            self._update_button_color(step_num, "red")
            return

        command = (
            f"docker exec -i {self.container_name} bash -c '"
            f"cd ~/work-gh/mrva/gh-mrva/ && "
            f"gh-mrva download --session {session} --download-dbs "
            f"--output-dir {session}'"
        )

        self._execute_command(command, step_num)


def create_gui(container_name="mrva-ghmrva"):
    """
    Create and run the workflow GUI.

    Args:
        container_name: Name of the Docker container
    """
    root = tk.Tk()
    app = WorkflowUI(root, container_name)
    root.mainloop()
