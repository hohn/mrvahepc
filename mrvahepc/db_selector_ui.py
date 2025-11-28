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


class DatabaseSelector:
    """Main GUI application for database selection and filtering."""
    
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
        
        # Initialize database connection
        self.conn = None
        self._connect_database()
        
        # Create UI components
        self._create_widgets()
        self._populate_dropdowns()
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
        
        # Create dropdowns in a grid layout (4 columns for better fit)
        for i, column in enumerate(self.columns):
            row = i // 4
            col = i % 4
            
            # Column label
            label = ttk.Label(header_frame, text=column.replace('_', ' ').title())
            label.grid(row=row*2, column=col, sticky=tk.W, padx=(0, 10), pady=(0, 2))
            
            # Dropdown combobox
            var = tk.StringVar()
            combobox = ttk.Combobox(header_frame, textvariable=var, state="readonly", width=20)
            combobox.grid(row=row*2+1, column=col, sticky=(tk.W, tk.E), padx=(0, 10), pady=(0, 10))
            
            # Store references
            self.dropdown_vars[column] = var
            self.dropdowns[column] = combobox
            
            # Configure column weights for header frame
            header_frame.columnconfigure(col, weight=1)
        
        # Clear filters button
        clear_btn = ttk.Button(header_frame, text="Clear All Filters", command=self._clear_filters)
        clear_btn.grid(row=(len(self.columns)-1)//4*2+2, column=0, columnspan=2, 
                      sticky=tk.W, pady=(10, 0))
        
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
                                text="Select dropdown values to filter results. Click on a result line to copy the file path to clipboard.",
                                font=("TkDefaultFont", 9))
        instructions.grid(row=3, column=0, sticky=tk.W, pady=(5, 0))
    
    def _populate_dropdowns(self):
        """Populate dropdown menus with unique values from database."""
        try:
            for column in self.columns:
                cursor = self.conn.execute(f"SELECT DISTINCT {column} FROM metadata ORDER BY {column}")
                values = [''] + [row[0] for row in cursor.fetchall() if row[0] is not None]
                self.dropdowns[column]['values'] = values
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to populate dropdowns:\n{e}")
    
    def _bind_events(self):
        """Bind event handlers to UI elements."""
        # Bind dropdown change events
        for column in self.columns:
            self.dropdown_vars[column].trace_add('write', self._on_filter_change)
        
        # Bind text widget click for copying paths
        self.results_text.bind('<Button-1>', self._on_result_click)
    
    def _on_filter_change(self, *args):
        """Handle dropdown selection changes."""
        self._update_results()
    
    def _clear_filters(self):
        """Clear all dropdown selections."""
        for var in self.dropdown_vars.values():
            var.set('')
        self._update_results()
    
    def _update_results(self):
        """Update results display based on current filter selections."""
        try:
            # Build WHERE clause from non-empty dropdown selections
            where_conditions = []
            params = []
            
            for column in self.columns:
                value = self.dropdown_vars[column].get().strip()
                if value:
                    where_conditions.append(f"{column} = ?")
                    params.append(value)
            
            # Construct SQL query
            query = "SELECT * FROM metadata"
            if where_conditions:
                query += " WHERE " + " AND ".join(where_conditions)
            query += " ORDER BY git_owner, git_repo, primary_language"
            
            # Execute query
            cursor = self.conn.execute(query, params)
            rows = cursor.fetchall()
            
            # Update results display
            self._display_results(rows)
            
            # Update status
            self.status_var.set(f"Found {len(rows)} matching databases")
            
        except sqlite3.Error as e:
            messagebox.showerror("Query Error", f"Database query failed:\n{e}")
            self.status_var.set("Query failed")
    
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