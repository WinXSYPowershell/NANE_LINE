#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import shutil
import stat
import time
import getpass
import platform
import re
import math
from datetime import datetime
import socket
import threading
import queue
import logging
import tempfile

# --- Configuration ---
# Determine the script's location and user's home directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
USER_HOME = os.path.expanduser("~")
NANE_LINE_DIR = os.path.join(USER_HOME, "NANE_LINE")
CONFIG_FILE = os.path.join(NANE_LINE_DIR, "nane_line_config.txt")
HISTORY_FILE = os.path.join(NANE_LINE_DIR, "nane_line_history.txt")
LOG_FILE = os.path.join(SCRIPT_DIR, "nane_line.log") # Log file in script's directory
SELF_COPY_PATH = os.path.join(NANE_LINE_DIR, os.path.basename(__file__))

# --- Global Variables ---
current_directory = os.getcwd()
command_history = []
aliases = {}
env_vars = {}
prompt_color = "\033[0m"  # Default color
log_level = "INFO"  # Options: DEBUG, INFO, WARNING, ERROR
user_name = getpass.getuser()
startup_time = time.time()
prompt_string = "NANE_LINE" # Default prompt string

# --- Setup Logging ---
def setup_logging():
    """Sets up the logging configuration."""
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO
    logging.basicConfig(
        level=numeric_level,
        format='[%(levelname)s] [%(asctime)s] %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE, encoding='utf-8'),
            logging.StreamHandler(sys.stdout) # Also print to console if needed
        ]
    )

def log_message(level, message):
    """Logs a message using the logging module."""
    getattr(logging, level.lower())(message)

def ensure_nane_line_dir():
    """Ensures the NANE_LINE directory exists in the user's home folder."""
    if not os.path.exists(NANE_LINE_DIR):
        os.makedirs(NANE_LINE_DIR, exist_ok=True)
        log_message("INFO", f"Created NANE_LINE directory: {NANE_LINE_DIR}")

def copy_self_to_dir():
    """Copies the current script to the NANE_LINE directory."""
    if not os.path.exists(SELF_COPY_PATH):
        try:
            shutil.copy2(__file__, SELF_COPY_PATH)
            log_message("INFO", f"Copied script to NANE_LINE directory: {SELF_COPY_PATH}")
            print(f"Self-copied script to: {SELF_COPY_PATH}")
        except Exception as e:
            log_message("ERROR", f"Failed to copy script to NANE_LINE directory: {e}")
            print(f"Warning: Could not copy script to {NANE_LINE_DIR}: {e}")

def add_to_path_windows():
    """Attempts to add the NANE_LINE directory to the Windows PATH environment variable for the current user."""
    if platform.system() != "Windows":
        log_message("INFO", "Skipping PATH addition - not a Windows system.")
        return

    try:
        import winreg
        key_path = r"Environment"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
        try:
            current_path, _ = winreg.QueryValueEx(key, "PATH")
        except FileNotFoundError:
            current_path = ""

        if NANE_LINE_DIR not in current_path:
            if current_path:
                new_path = f"{current_path};{NANE_LINE_DIR}"
            else:
                new_path = NANE_LINE_DIR
            
            winreg.SetValueEx(key, "PATH", 0, winreg.REG_EXPAND_SZ, new_path)
            winreg.CloseKey(key)
            log_message("INFO", f"Added {NANE_LINE_DIR} to Windows PATH for current user.")
            print(f"Added {NANE_LINE_DIR} to Windows PATH. You may need to restart your terminal for changes to take effect.")
        else:
            winreg.CloseKey(key)
            log_message("INFO", f"{NANE_LINE_DIR} is already in Windows PATH.")
    except ImportError:
        log_message("WARNING", "winreg module not available, cannot modify PATH on Windows.")
        print("Warning: Cannot modify PATH automatically on Windows (requires winreg module).")
    except Exception as e:
        log_message("ERROR", f"Failed to add directory to PATH: {e}")
        print(f"Error: Could not add {NANE_LINE_DIR} to PATH: {e}")

def load_config():
    """Loads configuration from a file."""
    global aliases, env_vars, prompt_color, log_level, prompt_string
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            for line in lines:
                line = line.strip()
                if line.startswith("ALIAS:"):
                    parts = line[6:].split('=', 1)
                    if len(parts) == 2:
                        aliases[parts[0]] = parts[1]
                elif line.startswith("ENV:"):
                    parts = line[4:].split('=', 1)
                    if len(parts) == 2:
                        env_vars[parts[0]] = parts[1]
                elif line.startswith("PROMPT_COLOR:"):
                    prompt_color = line[13:]
                elif line.startswith("PROMPT_STRING:"):
                    prompt_string = line[15:]
                elif line.startswith("LOG_LEVEL:"):
                    log_level = line[10:]
            log_message("INFO", "Configuration loaded.")
    except Exception as e:
        log_message("ERROR", f"Could not load config file: {e}")

def save_config():
    """Saves configuration to a file."""
    global aliases, env_vars, prompt_color, log_level, prompt_string
    try:
        # Ensure the NANE_LINE directory exists before saving config
        ensure_nane_line_dir()
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            for alias, command in aliases.items():
                f.write(f"ALIAS:{alias}={command}\n")
            for var, value in env_vars.items():
                f.write(f"ENV:{var}={value}\n")
            f.write(f"PROMPT_COLOR:{prompt_color}\n")
            f.write(f"PROMPT_STRING:{prompt_string}\n")
            f.write(f"LOG_LEVEL:{log_level}\n")
        log_message("INFO", "Configuration saved.")
    except Exception as e:
        log_message("ERROR", f"Could not save config file: {e}")

def load_history():
    """Loads command history from a file."""
    global command_history
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                command_history = [line.strip() for line in f.readlines()]
            log_message("INFO", "Command history loaded.")
    except Exception as e:
        log_message("ERROR", f"Could not load history file: {e}")

def save_history():
    """Saves command history to a file."""
    try:
        # Ensure the NANE_LINE directory exists before saving history
        ensure_nane_line_dir()
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            f.write("\n".join(command_history) + "\n")
        log_message("INFO", "Command history saved.")
    except Exception as e:
        log_message("ERROR", f"Could not save history file: {e}")

def expand_env_vars(text):
    """Expands environment variables in a string."""
    def replace_var(match):
        var_name = match.group(1)
        return env_vars.get(var_name, os.environ.get(var_name, match.group(0)))
    return re.sub(r'\$\{(\w+)\}', replace_var, text)

def run_command(cmd):
    """Runs a system command safely."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=10
        )
        print(result.stdout)
        if result.stderr:
            print(f"Error: {result.stderr}", file=sys.stderr)
    except subprocess.TimeoutExpired:
        print("Command timed out after 10 seconds.")
    except Exception as e:
        print(f"An error occurred while running the command: {e}")

def get_size_format(size_bytes):
    """Formats bytes into a human-readable string."""
    if size_bytes == 0:
        return "0 B"
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"

def get_permissions_string(mode):
    """Converts file mode to a readable string."""
    perm_string = ""
    for i in range(2, -1, -1):
        perm_string += "r" if mode & (1 << (i * 3 + 2)) else "-"
        perm_string += "w" if mode & (1 << (i * 3 + 1)) else "-"
        perm_string += "x" if mode & (1 << (i * 3 + 0)) else "-"
    return perm_string

def display_help():
    """Displays the help message."""
    help_text = """
NANE_LINE - A Python Command-Line Code Editor

Commands:
  ls, list                    : Show files in current directory
  cd <path>                   : Change directory
  run <file.nlc/.nc>          : Run a .nlc or .nc file
  open <file>                 : Open a file in editor (or notepad on Windows)
  rm <file>                   : Delete a file
  new <file>                  : Create a new file
  info <file>                 : Check file information
  sudo                        : Attempt to elevate privileges (not implemented)
  whoami                      : Display user information
  notepad <file>              : Open file with system notepad/text editor
  nettest                     : Perform a network connectivity test
  version                     : Show version
  exit                        : Exit the program
  help                        : Show this help
  history                     : Display command history
  alias <name> <command>      : Set an alias
  unalias <name>              : Delete an alias
  env                         : Show environment variables
  setenv <var> <value>        : Set an environment variable
  unsetenv <var>              : Delete an environment variable
  setloglevel <level>         : Set log level (DEBUG, INFO, WARNING, ERROR)
  calc <expression>           : Calculate a mathematical expression
  setcolor <color_code>       : Set prompt color (e.g., 32 for green, 34 for blue)
  setprompt <prompt_text>     : Set custom prompt text (e.g., "MyShell> ")
  greet                       : Display a greeting message
  packexe <file.nlc> [output_name] : Pack .nlc file into an executable (.exe on Windows, no extension on Linux/Mac)
  setup_env                   : Manually attempt to set up environment (create dir, copy, add to PATH)
"""
    print(help_text)

def display_greeting():
    """Displays a greeting message."""
    uptime = time.time() - startup_time
    days = int(uptime // 86400)
    hours = int((uptime % 86400) // 3600)
    minutes = int((uptime % 3600) // 60)
    seconds = int(uptime % 60)
    print(f"\nHello, {user_name}! Welcome to NANE_LINE.")
    print(f"Current directory: {current_directory}")
    print(f"Uptime: {days}d {hours}h {minutes}m {seconds}s")
    print(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"NANE_LINE directory: {NANE_LINE_DIR}")
    print(f"Log file: {LOG_FILE}")
    print(f"Self-copy path: {SELF_COPY_PATH}\n")

def net_test():
    """Performs a simple network connectivity test."""
    try:
        print("Testing network connectivity to google.com (port 80)...")
        sock = socket.create_connection(("google.com", 80), timeout=5)
        sock.close()
        print("Network test passed. Connected to google.com.")
        log_message("INFO", "Network test successful.")
    except socket.error:
        print("Network test failed. Could not connect to google.com.")
        log_message("WARNING", "Network test failed.")

def calculate(expression):
    """Calculates a mathematical expression."""
    try:
        # A safer eval alternative using ast and a restricted set of functions
        allowed_names = {
            k: v for k, v in math.__dict__.items() if not k.startswith("__")
        }
        allowed_names.update({"abs": abs, "round": round})
        code = compile(expression, "<string>", "eval")
        for node in code.co_names:
            if node not in allowed_names:
                raise NameError(f"Use of {node} is not allowed")
        result = eval(code, {"__builtins__": {}}, allowed_names)
        print(f"Result: {result}")
        log_message("INFO", f"Calculated '{expression}' = {result}")
    except Exception as e:
        print(f"Error calculating expression: {e}")

def pack_to_executable(nlc_file, output_name=None):
    """Packs a .nlc file into a standalone executable using PyInstaller."""
    if not os.path.isfile(nlc_file):
        print(f"Error: .nlc file not found: {nlc_file}")
        return

    if not nlc_file.endswith('.nlc'):
        print("Error: Input file must have .nlc extension.")
        return

    if output_name is None:
        output_name = os.path.splitext(os.path.basename(nlc_file))[0]

    # Check if PyInstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print("Error: PyInstaller is not installed.")
        print("Please install it using: pip install pyinstaller")
        return

    print(f"Packing '{nlc_file}' into an executable named '{output_name}'...")
    log_message("INFO", f"Starting to pack {nlc_file} into executable {output_name}")

    # Create a temporary Python script that loads and runs the .nlc file
    temp_script_name = f"temp_runner_{output_name}.py"
    try:
        with open(nlc_file, 'r', encoding='utf-8') as f:
            nlc_content = f.read()

        # Filter out comment lines (lines starting with '*')
        code_lines = []
        for line in nlc_content.splitlines(keepends=True): # keepends=True to preserve newlines
            stripped_line = line.lstrip() # Remove leading whitespace before checking
            if not stripped_line.startswith('*'):
                code_lines.append(line)
        
        filtered_code = "".join(code_lines)

        temp_script_content = f"""
# Auto-generated script to run packed .nlc file
import sys
import os

# Get the directory where the executable is located
exec_dir = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__)
nlc_file_path = os.path.join(exec_dir, r'{nlc_file}')

# Execute the filtered .nlc code
exec_code = r'''{filtered_code}'''
if exec_code.strip():
    try:
        exec(exec_code)
    except Exception as e:
        print(f"An error occurred while running the packed code: {{e}}")
        input("Press Enter to exit...")
else:
    print("No executable code found in the .nlc file after filtering comments.")
    input("Press Enter to exit...")

"""
        with open(temp_script_name, 'w', encoding='utf-8') as temp_f:
            temp_f.write(temp_script_content)

        # Determine PyInstaller command arguments
        pyinstaller_cmd = [
            "pyinstaller",
            "--onefile",      # Create a single executable file
            "--name", output_name, # Set the name of the executable
            "--distpath", ".",    # Output the executable to the current directory
            "--workpath", os.path.join(".", "build_temp"), # Use a temporary build directory
            "--specpath", os.path.join(".", "build_temp"), # Use the same temp dir for spec file
            temp_script_name
        ]

        # Run PyInstaller
        result = subprocess.run(pyinstaller_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"PyInstaller failed:\n{result.stderr}")
            log_message("ERROR", f"PyInstaller failed: {result.stderr}")
        else:
            print(f"Successfully packed '{nlc_file}' into '{output_name}'")
            log_message("INFO", f"Successfully packed {nlc_file} into {output_name}")

    except Exception as e:
        print(f"An error occurred during the packing process: {e}")
        log_message("ERROR", f"Error during packing: {e}")
    finally:
        # Clean up the temporary script
        try:
            if os.path.exists(temp_script_name):
                os.remove(temp_script_name)
            # Clean up temporary PyInstaller directories if they exist
            if os.path.exists("build_temp"):
                shutil.rmtree("build_temp")
        except OSError as e:
            print(f"Warning: Could not clean up temporary files: {e}")
            log_message("WARNING", f"Could not clean up temporary files: {e}")

# --- Main Program Class ---
class NaneLine:
    def __init__(self):
        self.running = True
        # Initial setup: ensure directory, copy script, setup logging
        ensure_nane_line_dir()
        copy_self_to_dir()
        setup_logging() # Setup logging after ensuring log file location is known
        add_to_path_windows() # Attempt to add to PATH on Windows
        load_config()
        load_history()
        display_greeting()
        log_message("INFO", "NANE_LINE started.")

    def run(self):
        while self.running:
            # Build the prompt
            prompt = f"{prompt_color}{prompt_string}@{current_directory}$ \033[0m"
            try:
                user_input = input(prompt).strip()
            except (EOFError, KeyboardInterrupt):
                print("\nReceived interrupt signal. Exiting...")
                self.running = False
                continue

            if not user_input:
                continue

            # Add to history
            command_history.append(user_input)

            # Check for alias
            parts = user_input.split(maxsplit=1)
            command = parts[0]
            args_str = parts[1] if len(parts) > 1 else ""
            if command in aliases:
                user_input = aliases[command]
                if args_str: # If original command had args, append them to the alias target
                    user_input += " " + args_str
                command, *arg_parts = user_input.split()
                args_str = " ".join(arg_parts) if arg_parts else ""

            # Process the command
            if command in ['exit', 'quit']:
                self.running = False
            elif command in ['ls', 'list']:
                self.cmd_ls()
            elif command == 'cd':
                self.cmd_cd(args_str)
            elif command == 'run':
                self.cmd_run(args_str)
            elif command == 'open':
                self.cmd_open(args_str)
            elif command == 'rm':
                self.cmd_rm(args_str)
            elif command == 'new':
                self.cmd_new(args_str)
            elif command == 'info':
                self.cmd_info(args_str)
            elif command == 'sudo':
                self.cmd_sudo()
            elif command == 'whoami':
                self.cmd_whoami()
            elif command == 'notepad':
                self.cmd_notepad(args_str)
            elif command == 'nettest':
                self.cmd_nettest()
            elif command == 'version':
                self.cmd_version()
            elif command in ['help', '?']:
                display_help()
            elif command == 'history':
                self.cmd_history()
            elif command == 'alias':
                self.cmd_alias(args_str)
            elif command == 'unalias':
                self.cmd_unalias(args_str)
            elif command == 'env':
                self.cmd_env()
            elif command == 'setenv':
                self.cmd_setenv(args_str)
            elif command == 'unsetenv':
                self.cmd_unsetenv(args_str)
            elif command == 'setloglevel':
                self.cmd_setloglevel(args_str)
            elif command == 'calc':
                self.cmd_calc(args_str)
            elif command == 'setcolor':
                self.cmd_setcolor(args_str)
            elif command == 'setprompt':
                self.cmd_setprompt(args_str)
            elif command == 'greet':
                display_greeting()
            elif command == 'packexe':
                self.cmd_packexe(args_str)
            elif command == 'setup_env':
                self.cmd_setup_env()
            else:
                print(f"Unknown command: {command}. Type 'help' for a list of commands.")

        # Save on exit
        save_config()
        save_history()
        log_message("INFO", "NANE_LINE exited.")
        print("\nGoodbye!")

    def cmd_ls(self):
        try:
            items = os.listdir(current_directory)
            for item in sorted(items):
                path = os.path.join(current_directory, item)
                size = get_size_format(os.path.getsize(path))
                mod_time = datetime.fromtimestamp(os.path.getmtime(path)).strftime('%Y-%m-%d %H:%M:%S')
                is_dir = "DIR" if os.path.isdir(path) else "FILE"
                print(f"{is_dir:<4} {size:>10} {mod_time} {item}")
            log_message("INFO", f"Listed directory contents of {current_directory}")
        except PermissionError:
            print("Permission denied to list directory contents.")
            log_message("ERROR", f"Permission denied for ls in {current_directory}")

    def cmd_cd(self, path):
        if not path:
            print("Usage: cd <path>")
            return
        try:
            global current_directory
            path = os.path.expanduser(path) # Handle ~
            path = os.path.abspath(path) # Convert to absolute path
            os.chdir(path)
            current_directory = os.getcwd()
            print(f"Changed directory to: {current_directory}")
            log_message("INFO", f"Changed directory to {current_directory}")
        except FileNotFoundError:
            print(f"Directory not found: {path}")
            log_message("ERROR", f"Failed to change directory to {path}")
        except PermissionError:
            print(f"Permission denied to change to directory: {path}")
            log_message("ERROR", f"Permission denied for cd to {path}")
        except Exception as e:
            print(f"An error occurred: {e}")

    def cmd_run(self, filename):
        if not filename:
            print("Usage: run <file.nlc/.nc>")
            return
        if not (filename.endswith('.nlc') or filename.endswith('.nc')):
            print("Error: File must have .nlc or .nc extension.")
            return
        
        full_path = os.path.join(current_directory, filename)
        if not os.path.isfile(full_path):
            print(f"File not found: {full_path}")
            return

        print(f"Running {filename}...")
        log_message("INFO", f"Running script {full_path}")
        try:
            if filename.endswith('.nlc'):
                # Read the .nlc file, filter out comments, and execute as Python
                with open(full_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                # Filter out lines starting with '*'
                code_lines = []
                for line_num, line in enumerate(lines, 1):
                    stripped_line = line.strip()
                    if not stripped_line.startswith('*'):
                        code_lines.append(line)
                    # Note: We no longer print the comment
                
                code_to_run = "".join(code_lines)
                
                if code_to_run.strip(): # Only execute if there's actual code
                    exec(code_to_run, {"__file__": full_path, "__name__": "__main__"})
                else:
                    print("No executable code found after filtering comments.")
                    
            elif filename.endswith('.nc'):
                # Example: run as shell script (Linux/Mac) or batch (Windows)
                if platform.system() == "Windows":
                    run_command(f'cmd /c "{full_path}"')
                else:
                    # Make executable first
                    st = os.stat(full_path)
                    os.chmod(full_path, st.st_mode | stat.S_IEXEC)
                    run_command(f'"{full_path}"')
        except SyntaxError as e:
            print(f"Syntax error in {filename}: {e}")
            log_message("ERROR", f"Syntax error in {full_path}: {e}")
        except Exception as e:
            print(f"An error occurred while running the file: {e}")
            log_message("ERROR", f"Error running {full_path}: {e}")

    def cmd_open(self, filename):
        if not filename:
            print("Usage: open <file>")
            return
        full_path = os.path.join(current_directory, filename)
        try:
            # This is a simple file opener, could be enhanced
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            print("--- Content of", filename, "---")
            print(content)
            print("--- End of", filename, "---")
            log_message("INFO", f"Opened file {full_path}")
        except FileNotFoundError:
            print(f"File not found: {full_path}")
            log_message("ERROR", f"File not found for opening: {full_path}")
        except UnicodeDecodeError:
            print(f"Could not open {filename} as text. It might be a binary file.")
            log_message("WARNING", f"Attempted to open binary file as text: {full_path}")

    def cmd_rm(self, filename):
        if not filename:
            print("Usage: rm <file>")
            return
        full_path = os.path.join(current_directory, filename)
        try:
            if os.path.isfile(full_path):
                os.remove(full_path)
                print(f"File deleted: {full_path}")
                log_message("INFO", f"Deleted file {full_path}")
            elif os.path.isdir(full_path):
                shutil.rmtree(full_path)
                print(f"Directory deleted: {full_path}")
                log_message("INFO", f"Deleted directory {full_path}")
            else:
                print(f"Path not found: {full_path}")
        except PermissionError:
            print(f"Permission denied to delete: {full_path}")
            log_message("ERROR", f"Permission denied for rm {full_path}")
        except Exception as e:
            print(f"An error occurred while deleting: {e}")
            log_message("ERROR", f"Error deleting {full_path}: {e}")

    def cmd_new(self, filename):
        if not filename:
            print("Usage: new <file>")
            return
        full_path = os.path.join(current_directory, filename)
        try:
            if os.path.exists(full_path):
                print(f"File already exists: {full_path}")
                return
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write("") # Create an empty file
            print(f"New file created: {full_path}")
            log_message("INFO", f"Created new file {full_path}")
        except PermissionError:
            print(f"Permission denied to create file: {full_path}")
            log_message("ERROR", f"Permission denied for new {full_path}")
        except Exception as e:
            print(f"An error occurred while creating the file: {e}")
            log_message("ERROR", f"Error creating {full_path}: {e}")

    def cmd_info(self, filename):
        if not filename:
            print("Usage: info <file>")
            return
        full_path = os.path.join(current_directory, filename)
        try:
            stat_info = os.stat(full_path)
            is_dir = os.path.isdir(full_path)
            print(f"Path: {full_path}")
            print(f"Type: {'Directory' if is_dir else 'File'}")
            print(f"Size: {get_size_format(stat_info.st_size)}")
            print(f"Permissions: {get_permissions_string(stat_info.st_mode)}")
            print(f"Last Modified: {datetime.fromtimestamp(stat_info.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Last Accessed: {datetime.fromtimestamp(stat_info.st_atime).strftime('%Y-%m-%d %H:%M:%S')}")
            log_message("INFO", f"Checked info for {full_path}")
        except FileNotFoundError:
            print(f"File not found: {full_path}")
            log_message("ERROR", f"File not found for info: {full_path}")
        except Exception as e:
            print(f"An error occurred: {e}")
            log_message("ERROR", f"Error getting info for {full_path}: {e}")

    def cmd_sudo(self):
        print("Sudo command is a placeholder. Real privilege escalation is complex and OS-specific.")
        print("On Unix-like systems, you would typically re-run the script with 'sudo'.")
        print("On Windows, you might need to run the terminal as administrator.")
        log_message("WARNING", "Sudo command called (not implemented)")

    def cmd_whoami(self):
        print(f"Username: {user_name}")
        print(f"Hostname: {platform.node()}")
        print(f"Platform: {platform.platform()}")
        print(f"Python Version: {platform.python_version()}")
        log_message("INFO", "Whoami command executed")

    def cmd_notepad(self, filename):
        if not filename:
            print("Usage: notepad <file>")
            return
        full_path = os.path.join(current_directory, filename)
        try:
            if platform.system() == "Windows":
                os.startfile(full_path)
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", "-t", full_path])
            else:  # Linux
                subprocess.run(["xdg-open", full_path])
            print(f"Opened {filename} in system editor.")
            log_message("INFO", f"Opened {full_path} in system editor")
        except FileNotFoundError:
            print(f"File not found: {full_path}")
            log_message("ERROR", f"File not found for notepad: {full_path}")
        except Exception as e:
            print(f"Could not open file in system editor: {e}")
            log_message("ERROR", f"Error opening {full_path} in system editor: {e}")

    def cmd_nettest(self):
        net_test()

    def cmd_version(self):
        print("NANE_LINE v1.0.0 - Python Command-Line Editor")
        log_message("INFO", "Version command executed")

    def cmd_history(self):
        for i, cmd in enumerate(command_history, 1):
            print(f"{i:4d}: {cmd}")
        log_message("INFO", "History command executed")

    def cmd_alias(self, args_str):
        if not args_str:
            print("Usage: alias <name> <command>")
            return
        parts = args_str.split(maxsplit=1)
        if len(parts) != 2:
            print("Usage: alias <name> <command>")
            return
        name, command = parts
        aliases[name] = command
        print(f"Alias '{name}' set to '{command}'")
        log_message("INFO", f"Set alias '{name}' -> '{command}'")

    def cmd_unalias(self, name):
        if not name:
            print("Usage: unalias <name>")
            return
        if name in aliases:
            del aliases[name]
            print(f"Alias '{name}' removed.")
            log_message("INFO", f"Removed alias '{name}'")
        else:
            print(f"No alias named '{name}' found.")

    def cmd_env(self):
        print("--- Environment Variables ---")
        for key, value in env_vars.items():
            print(f"{key}={value}")
        print("--- System Environment Variables ---")
        for key, value in os.environ.items():
            print(f"{key}={value}")
        log_message("INFO", "Env command executed")

    def cmd_setenv(self, args_str):
        if not args_str:
            print("Usage: setenv <var> <value>")
            return
        parts = args_str.split(maxsplit=1)
        if len(parts) != 2:
            print("Usage: setenv <var> <value>")
            return
        var, value = parts
        env_vars[var] = expand_env_vars(value) # Allow expansion of other vars in the value
        os.environ[var] = env_vars[var] # Also set it for subprocesses
        print(f"Environment variable '{var}' set to '{env_vars[var]}'")
        log_message("INFO", f"Set environment variable '{var}' to '{env_vars[var]}'")

    def cmd_unsetenv(self, var):
        if not var:
            print("Usage: unsetenv <var>")
            return
        if var in env_vars:
            del env_vars[var]
        if var in os.environ:
            del os.environ[var]
        print(f"Environment variable '{var}' removed.")
        log_message("INFO", f"Removed environment variable '{var}'")

    def cmd_setloglevel(self, level):
        if level.upper() in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            global log_level
            log_level = level.upper()
            setup_logging() # Re-initialize logging with new level
            print(f"Log level set to {log_level}")
            log_message("INFO", f"Log level changed to {log_level}")
        else:
            print("Invalid log level. Use: DEBUG, INFO, WARNING, ERROR")

    def cmd_calc(self, expression):
        if not expression:
            print("Usage: calc <expression>")
            return
        calculate(expression)

    def cmd_setcolor(self, color_code):
        if not color_code:
            print("Usage: setcolor <color_code>")
            print("Example: setcolor 32 (Green), 34 (Blue), 31 (Red), 0 (Reset)")
            return
        try:
            code = int(color_code)
            if 0 <= code <= 255:
                global prompt_color
                prompt_color = f"\033[{code}m"
                print(f"Prompt color set to code {code}.")
                log_message("INFO", f"Prompt color set to {code}")
            else:
                print("Color code must be between 0 and 255.")
        except ValueError:
            print("Color code must be an integer.")

    def cmd_setprompt(self, prompt_text):
        if not prompt_text:
            print("Usage: setprompt <prompt_text>")
            print("Example: setprompt 'MyShell> '")
            print("You can use ANSI codes like setprompt '\\033[35mMyPrompt>\\033[0m ' for color.")
            return
        global prompt_string
        prompt_string = prompt_text
        print(f"Prompt text set to: {prompt_text}")
        log_message("INFO", f"Prompt string set to: {prompt_text}")

    def cmd_packexe(self, args_str):
        if not args_str:
            print("Usage: packexe <file.nlc> [output_name]")
            return
        
        parts = args_str.split(maxsplit=1)
        nlc_file = parts[0]
        output_name = parts[1] if len(parts) > 1 else None
        
        pack_to_executable(nlc_file, output_name)

    def cmd_setup_env(self):
        """Manually attempts to set up the NANE_LINE environment."""
        print("Manually running environment setup...")
        ensure_nane_line_dir()
        copy_self_to_dir()
        add_to_path_windows()
        print("Environment setup process completed (or attempted).")
        log_message("INFO", "Manual environment setup command executed.")


# --- Main Execution ---
if __name__ == "__main__":
    editor = NaneLine()
    editor.run()