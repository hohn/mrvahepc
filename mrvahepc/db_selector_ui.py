#!/usr/bin/env python3
"""
Database Selector UI for MRVA HEPC

Provides a Tkinter-based GUI for filtering and selecting CodeQL databases
from the SQLite metadata database created by host-hepc-init.
"""

import sqlite3
import sys
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import re
import json


class DatabaseSelector:
    """Main GUI application for database selection and filtering.
    
    Provides dropdown filters for all metadata columns and displays matching
    results in a text widget. Click on result lines to copy file paths to clipboard.
    Export buttons generate repository lists in GH-MRVA and VS Code formats.
    """
    
    def __init__(self, metadata_db_path: str):
        self.metadata_db_path = Path(metadata_db_path)
        self.root = tk.Tk()
        self.root.title("MRVA HEPC Database Selector")
        self.root.geometry("1200x800")
        
        # Column definitions matching the metadata table schema
        self.columns = [
            "git_branch", "git_commit_id", "git_owner", "git_repo",
            "ingestion_datetime_utc", "primary_language", "result_url", 
            "tool_name", "tool_version", "projname", "db_file_size"
        ]
        
        # Storage for dropdown widgets and their values
        self.dropdowns: Dict[str, ttk.Combobox] = {}
        self.dropdown_vars: Dict[str, tk.StringVar] = {}
        self.regex_entries: Dict[str, ttk.Entry] = {}
        self.regex_vars: Dict[str, tk.StringVar] = {}
        
        # Storage for all available values per column (for regex filtering)
        self.all_values: Dict[str, List[str]] = {}
        
        # Storage for current query results
        self.current_results: List[sqlite3.Row] = []
        
        # Initialize database connection
        self.conn = None
        self._connect_database()
        
        # Create UI components
        self._create_widgets()
        self._populate_dropdowns()
        self._initialize_regex_placeholders()
        self._bind_events()
        
        # Initial display of all records
        self._update_results()
    
    def _connect_database(self):
        """Connect to the SQLite metadata database."""
        try:
            self.conn = sqlite3.connect(str(self.metadata_db_path))
            self.conn.row_factory = sqlite3.Row  # Enable column access by name
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", 
                               f"Cannot connect to database {self.metadata_db_path}:\n{e}")
            sys.exit(1)
    
    def _create_widgets(self):
        """Create and layout all UI widgets."""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure root grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Header frame for dropdowns
        header_frame = ttk.LabelFrame(main_frame, text="Filter Options", padding="10")
        header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Create dropdowns in a grid layout (3 columns for better fit with regex entries)
        for i, column in enumerate(self.columns):
            row = i // 3
            col = i % 3
            
            # Column label
            label = ttk.Label(header_frame, text=column.replace('_', ' ').title())
            label.grid(row=row*3, column=col, sticky=tk.W, padx=(0, 10), pady=(0, 2))
            
            # Dropdown combobox
            var = tk.StringVar()
            combobox = ttk.Combobox(header_frame, textvariable=var, state="readonly", width=25)
            combobox.grid(row=row*3+1, column=col, sticky=(tk.W, tk.E), padx=(0, 10), pady=(0, 2))
            
            # Regex entry box
            regex_var = tk.StringVar()
            regex_entry = ttk.Entry(header_frame, textvariable=regex_var, width=25, 
                                   font=("TkDefaultFont", 9))
            regex_entry.grid(row=row*3+2, column=col, sticky=(tk.W, tk.E), padx=(0, 10), pady=(0, 10))
            
            # Add placeholder text
            regex_entry.insert(0, "regex filter...")
            regex_entry.bind('<FocusIn>', lambda e, entry=regex_entry: self._on_regex_focus_in(e, entry))
            regex_entry.bind('<FocusOut>', lambda e, entry=regex_entry: self._on_regex_focus_out(e, entry))
            
            # Store references
            self.dropdown_vars[column] = var
            self.dropdowns[column] = combobox
            self.regex_vars[column] = regex_var
            self.regex_entries[column] = regex_entry
            
            # Configure column weights for header frame
            header_frame.columnconfigure(col, weight=1)
        
        # Control buttons frame
        buttons_row = (len(self.columns)-1)//3*3+3
        
        # Clear filters button
        clear_btn = ttk.Button(header_frame, text="Clear All Filters", command=self._clear_filters)
        clear_btn.grid(row=buttons_row, column=0, sticky=tk.W, pady=(10, 0), padx=(0, 5))
        
        # Export buttons
        export_gh_btn = ttk.Button(header_frame, text="Export GH-MRVA Format", command=self._export_gh_mrva)
        export_gh_btn.grid(row=buttons_row, column=1, sticky=tk.W, pady=(10, 0), padx=(0, 5))
        
        export_vscode_btn = ttk.Button(header_frame, text="Export VS Code Format", command=self._export_vscode)
        export_vscode_btn.grid(row=buttons_row, column=2, sticky=tk.W, pady=(10, 0))
        
        # Results frame
        results_frame = ttk.LabelFrame(main_frame, text="Results", padding="10")
        results_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        # Results text widget with scrollbars
        self.results_text = scrolledtext.ScrolledText(
            results_frame, 
            wrap=tk.NONE,
            font=("Monaco", 10),
            state=tk.DISABLED
        )
        self.results_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        
        # Instructions label
        instructions = ttk.Label(main_frame, 
                                text="Select dropdown values to filter results. Use regex entries for pattern matching. Click on a result line to copy the file path to clipboard. Use export buttons to generate repository lists in different formats.",
                                font=("TkDefaultFont", 9))
        instructions.grid(row=3, column=0, sticky=tk.W, pady=(5, 0))
    
    def _populate_dropdowns(self):
        """Populate dropdown menus with unique values from database."""
        try:
            for column in self.columns:
                cursor = self.conn.execute(f"SELECT DISTINCT {column} FROM metadata ORDER BY {column}")
                values = [row[0] for row in cursor.fetchall() if row[0] is not None]
                self.all_values[column] = values
                
                # Initialize dropdown with all values plus empty option
                dropdown_values = [''] + values
                self.dropdowns[column]['values'] = dropdown_values
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to populate dropdowns:\n{e}")
    
    def _initialize_regex_placeholders(self):
        """Initialize regex entry boxes with placeholder styling."""
        for entry in self.regex_entries.values():
            entry.config(foreground='grey')
    
    def _bind_events(self):
        """Bind event handlers to UI elements."""
        # Bind dropdown change events
        for column in self.columns:
            self.dropdown_vars[column].trace_add('write', self._on_filter_change)
            self.regex_vars[column].trace_add('write', self._on_regex_change)
        
        # Bind text widget click for copying paths
        self.results_text.bind('<Button-1>', self._on_result_click)
    
    def _on_filter_change(self, *args):
        """Handle dropdown selection changes."""
        self._update_dropdown_from_regex()
        self._update_results()
    
    def _on_regex_change(self, *args):
        """Handle regex entry changes."""
        self._update_dropdown_from_regex()
        self._update_results()
    
    def _on_regex_focus_in(self, event, entry):
        """Handle focus in for regex entry (clear placeholder)."""
        if entry.get() == "regex filter...":
            entry.delete(0, tk.END)
            entry.config(foreground='black')
    
    def _on_regex_focus_out(self, event, entry):
        """Handle focus out for regex entry (restore placeholder if empty)."""
        if not entry.get().strip():
            entry.delete(0, tk.END)
            entry.insert(0, "regex filter...")
            entry.config(foreground='grey')
    
    def _update_dropdown_from_regex(self):
        """Update dropdown options based on regex filters."""
        for column in self.columns:
            regex_text = self.regex_vars[column].get().strip()
            
            # Skip if placeholder text or empty
            if not regex_text or regex_text == "regex filter...":
                # Show all values
                filtered_values = [''] + self.all_values[column]
            else:
                try:
                    # Compile regex and filter values
                    pattern = re.compile(regex_text, re.IGNORECASE)
                    filtered_values = [''] + [
                        value for value in self.all_values[column] 
                        if pattern.search(str(value))
                    ]
                except re.error:
                    # Invalid regex, show all values
                    filtered_values = [''] + self.all_values[column]
            
            # Update dropdown values
            current_selection = self.dropdown_vars[column].get()
            self.dropdowns[column]['values'] = filtered_values
            
            # Preserve selection if it's still valid
            if current_selection not in filtered_values:
                self.dropdown_vars[column].set('')
    
    def _clear_filters(self):
        """Clear all dropdown selections and regex entries."""
        for var in self.dropdown_vars.values():
            var.set('')
        for column in self.columns:
            entry = self.regex_entries[column]
            entry.delete(0, tk.END)
            entry.insert(0, "regex filter...")
            entry.config(foreground='grey')
        self._update_dropdown_from_regex()
        self._update_results()
    
    def _update_results(self):
        """Update results display based on current filter selections and regex patterns."""
        try:
            # Build WHERE clause from dropdown selections and regex patterns
            where_conditions = []
            params = []
            
            for column in self.columns:
                # Check dropdown selection
                dropdown_value = self.dropdown_vars[column].get().strip()
                regex_value = self.regex_vars[column].get().strip()
                
                # Skip if regex is placeholder text
                if regex_value == "regex filter...":
                    regex_value = ""
                
                if dropdown_value:
                    # Exact match from dropdown
                    where_conditions.append(f"{column} = ?")
                    params.append(dropdown_value)
                elif regex_value:
                    # Regex pattern matching
                    where_conditions.append(f"{column} REGEXP ?")
                    params.append(regex_value)
            
            # Construct SQL query
            query = "SELECT * FROM metadata"
            if where_conditions:
                query += " WHERE " + " AND ".join(where_conditions)
            query += " ORDER BY git_owner, git_repo, primary_language"
            
            # Execute query with custom REGEXP function
            self._setup_regexp_function()
            cursor = self.conn.execute(query, params)
            rows = cursor.fetchall()
            
            # Store current results for export
            self.current_results = rows
            
            # Update results display
            self._display_results(rows)
            
            # Update status
            self.status_var.set(f"Found {len(rows)} matching databases")
            
        except sqlite3.Error as e:
            messagebox.showerror("Query Error", f"Database query failed:\n{e}")
            self.status_var.set("Query failed")
        except re.error as e:
            # Handle invalid regex gracefully
            self.status_var.set(f"Invalid regex pattern: {e}")
    
    def _setup_regexp_function(self):
        """Set up custom REGEXP function for SQLite."""
        def regexp(pattern, text):
            if text is None:
                return False
            try:
                return re.search(pattern, str(text), re.IGNORECASE) is not None
            except re.error:
                return False
        
        self.conn.create_function("REGEXP", 2, regexp)
    
    def _display_results(self, rows: List[sqlite3.Row]):
        """Display query results in the text widget."""
        self.results_text.config(state=tk.NORMAL)
        self.results_text.delete(1.0, tk.END)
        
        if not rows:
            self.results_text.insert(tk.END, "No matching databases found.")
            self.results_text.config(state=tk.DISABLED)
            return
        
        # Create header
        header = f"{'Owner':<15} {'Repo':<20} {'Language':<10} {'Tool Ver':<10} {'Size (MB)':<10} {'Path'}\n"
        header += "-" * 120 + "\n"
        self.results_text.insert(tk.END, header)
        
        # Add data rows
        for row in rows:
            size_mb = round(row['db_file_size'] / (1024 * 1024), 1) if row['db_file_size'] else 0
            line = (f"{row['git_owner']:<15} {row['git_repo']:<20} {row['primary_language']:<10} "
                   f"{row['tool_version']:<10} {size_mb:<10} {row['result_url']}\n")
            self.results_text.insert(tk.END, line)
        
        self.results_text.config(state=tk.DISABLED)
    
    def _on_result_click(self, event):
        """Handle clicks on result lines to copy paths to clipboard."""
        # Get the clicked line
        index = self.results_text.index(tk.CURRENT)
        line_start = f"{index.split('.')[0]}.0"
        line_end = f"{index.split('.')[0]}.end"
        line_content = self.results_text.get(line_start, line_end)
        
        # Skip header lines and empty lines
        if not line_content.strip() or line_content.startswith(('-', 'Owner', 'No matching')):
            return
        
        # Extract file path (last field in the line)
        parts = line_content.strip().split()
        if len(parts) >= 6:  # Ensure we have enough parts
            file_path = parts[-1]  # Last part is the file path
            
            # Copy to clipboard
            self.root.clipboard_clear()
            self.root.clipboard_append(file_path)
            self.root.update()  # Required for clipboard to work
            
            self.status_var.set(f"Copied to clipboard: {file_path}")
        else:
            self.status_var.set("Could not extract file path from selected line")
    
    def _get_repository_list(self) -> List[str]:
        """Extract repository list from current results in owner/repo format."""
        repositories = []
        for row in self.current_results:
            if row['git_owner'] and row['git_repo']:
                repo_name = f"{row['git_owner']}/{row['git_repo']}"
                if repo_name not in repositories:
                    repositories.append(repo_name)
        return sorted(repositories)
    
    def _export_gh_mrva(self):
        """Export current selection in GH-MRVA format."""
        if not self.current_results:
            messagebox.showwarning("No Results", "No databases to export. Please apply filters first.")
            return
        
        repositories = self._get_repository_list()
        
        export_data = {
            "mirva-list": repositories
        }
        
        # Format as pretty JSON
        json_output = json.dumps(export_data, indent=4)
        
        # Copy to clipboard
        self.root.clipboard_clear()
        self.root.clipboard_append(json_output)
        self.root.update()
        
        # Show in a dialog
        self._show_export_dialog("GH-MRVA Export Format", json_output)
        self.status_var.set(f"Exported {len(repositories)} repositories in GH-MRVA format (copied to clipboard)")
    
    def _export_vscode(self):
        """Export current selection in VS Code format."""
        if not self.current_results:
            messagebox.showwarning("No Results", "No databases to export. Please apply filters first.")
            return
        
        repositories = self._get_repository_list()
        
        export_data = {
            "version": 1,
            "databases": {
                "variantAnalysis": {
                    "repositoryLists": [
                        {
                            "name": "mirva-list",
                            "repositories": repositories
                        }
                    ],
                    "owners": [],
                    "repositories": []
                }
            },
            "selected": {
                "kind": "variantAnalysisUserDefinedList",
                "listName": "mirva-list"
            }
        }
        
        # Format as pretty JSON
        json_output = json.dumps(export_data, indent=4)
        
        # Copy to clipboard
        self.root.clipboard_clear()
        self.root.clipboard_append(json_output)
        self.root.update()
        
        # Show in a dialog
        self._show_export_dialog("VS Code Export Format", json_output)
        self.status_var.set(f"Exported {len(repositories)} repositories in VS Code format (copied to clipboard)")
    
    def _show_export_dialog(self, title: str, content: str):
        """Show export content in a dialog window."""
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("600x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Create text widget with scrollbars
        frame = ttk.Frame(dialog, padding="10")
        frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        
        text_widget = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=("Monaco", 10))
        text_widget.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        text_widget.insert(tk.END, content)
        text_widget.config(state=tk.DISABLED)
        
        # Close button
        close_btn = ttk.Button(frame, text="Close", command=dialog.destroy)
        close_btn.grid(row=1, column=0, pady=(10, 0))
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
    
    def run(self):
        """Start the GUI main loop."""
        try:
            self.root.mainloop()
        finally:
            if self.conn:
                self.conn.close()


def create_gui(metadata_db_path: str):
    """Create and run the database selector GUI."""
    app = DatabaseSelector(metadata_db_path)
    app.run()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python db_selector_ui.py <metadata_db_path>", file=sys.stderr)
        sys.exit(1)
    
    create_gui(sys.argv[1])