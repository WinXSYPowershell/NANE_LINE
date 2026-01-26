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
import json
import winsound # For Windows audio (pip install pypiwin32 might be needed, but often built-in)
import wave
import io
import base64
import importlib.util
import importlib.machinery  # 新增：用于打包后动态加载模块
import zipfile
import hashlib

# --- Configuration ---
# 基础路径定义（后续会根据是否打包进行适配）
USER_HOME = os.path.expanduser("~")
SCRIPT_DIR = ""
NANE_LINE_DIR = ""
CONFIG_FILE = ""
HISTORY_FILE = ""
LOG_FILE = ""
SELF_COPY_PATH = ""
MODULES_DIR = ""
MODULES_PY_DIR = ""  # 新增：存放模块源码的目录

# --- PyInstaller 打包适配核心逻辑 ---
# 判断是否是打包后的 exe 运行环境
if getattr(sys, 'frozen', False):
    # 打包后的 exe 路径
    EXE_DIR = os.path.dirname(sys.executable)
    # 所有核心目录强制指向 exe 同目录（真实路径）
    NANE_LINE_DIR = EXE_DIR
    MODULES_DIR = os.path.join(EXE_DIR, "modules")
    MODULES_PY_DIR = os.path.join(EXE_DIR, "modulesPY")  # 新增：模块源码目录
    CONFIG_FILE = os.path.join(NANE_LINE_DIR, "nane_line_config.txt")
    HISTORY_FILE = os.path.join(NANE_LINE_DIR, "nane_line_history.txt")
    LOG_FILE = os.path.join(NANE_LINE_DIR, "nane_line.log")
    SELF_COPY_PATH = os.path.join(NANE_LINE_DIR, os.path.basename(sys.executable))
else:
    # 原生 Python 环境，保持原有路径逻辑
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    NANE_LINE_DIR = os.path.join(USER_HOME, "NANE_LINE")
    MODULES_DIR = os.path.join(NANE_LINE_DIR, "modules")
    MODULES_PY_DIR = os.path.join(NANE_LINE_DIR, "modulesPY")  # 新增：模块源码目录
    CONFIG_FILE = os.path.join(NANE_LINE_DIR, "nane_line_config.txt")
    HISTORY_FILE = os.path.join(NANE_LINE_DIR, "nane_line_history.txt")
    LOG_FILE = os.path.join(SCRIPT_DIR, "nane_line.log")
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

# --- New Global Variables for Functions, Variables, Lists/Dictionaries ---
functions = {}
variables = {}
lists_dicts = {}
loaded_modules = {}  # Dictionary to store loaded modules

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
        
    # Create modules directory
    if not os.path.exists(MODULES_DIR):
        os.makedirs(MODULES_DIR, exist_ok=True)
        log_message("INFO", f"Created modules directory: {MODULES_DIR}")
    
    # Create modulesPY directory
    if not os.path.exists(MODULES_PY_DIR):
        os.makedirs(MODULES_PY_DIR, exist_ok=True)
        log_message("INFO", f"Created modulesPY directory: {MODULES_PY_DIR}")

def copy_self_to_dir():
    """Copies the current script to the NANE_LINE directory."""
    if not os.path.exists(SELF_COPY_PATH):
        try:
            if getattr(sys, 'frozen', False):
                # 打包后复制 exe 文件
                shutil.copy2(sys.executable, SELF_COPY_PATH)
            else:
                shutil.copy2(__file__, SELF_COPY_PATH)
            log_message("INFO", f"Copied script/exe to NANE_LINE directory: {SELF_COPY_PATH}")
            print(f"Self-copied to: {SELF_COPY_PATH}")
        except Exception as e:
            log_message("ERROR", f"Failed to copy script/exe to NANE_LINE directory: {e}")
            print(f"Warning: Could not copy to {NANE_LINE_DIR}: {e}")

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
    global aliases, env_vars, prompt_color, log_level, prompt_string, functions, variables, lists_dicts
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
                elif line.startswith("FUNCTION:"):
                    parts = line[9:].split('=', 1)
                    if len(parts) == 2:
                        func_name = parts[0]
                        try:
                            func_data = json.loads(parts[1])
                            functions[func_name] = func_data
                        except json.JSONDecodeError:
                            log_message("WARNING", f"Could not decode function data for {func_name}")
                elif line.startswith("VARIABLE:"):
                    parts = line[9:].split('=', 1)
                    if len(parts) == 2:
                        var_name = parts[0]
                        # Store as string, let expansion handle types later
                        variables[var_name] = parts[1]
                elif line.startswith("LISTDICT:"):
                    parts = line[9:].split('=', 1)
                    if len(parts) == 2:
                        ld_name = parts[0]
                        try:
                            ld_data = json.loads(parts[1])
                            lists_dicts[ld_name] = ld_data
                        except json.JSONDecodeError:
                            log_message("WARNING", f"Could not decode list/dict data for {ld_name}")
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
    global aliases, env_vars, prompt_color, log_level, prompt_string, functions, variables, lists_dicts
    try:
        # Ensure the NANE_LINE directory exists before saving config
        ensure_nane_line_dir()
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            for alias, command in aliases.items():
                f.write(f"ALIAS:{alias}={command}\n")
            for var, value in env_vars.items():
                f.write(f"ENV:{var}={value}\n")
            for func_name, func_data in functions.items():
                f.write(f"FUNCTION:{func_name}={json.dumps(func_data)}\n")
            for var_name, var_value in variables.items():
                f.write(f"VARIABLE:{var_name}={var_value}\n")
            for ld_name, ld_data in lists_dicts.items():
                f.write(f"LISTDICT:{ld_name}={json.dumps(ld_data)}\n")
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

def expand_variables(text):
    """Expands user-defined variables in a string."""
    def replace_var(match):
        var_name = match.group(1)
        # Recursively expand nested variables within the value
        val = variables.get(var_name, match.group(0))
        if isinstance(val, str) and '{' in val and '}' in val:
             # Prevent infinite recursion by limiting depth or using a different method
             # For simplicity, a single level of recursion is handled here.
             # A more robust solution might use a stack or iterative approach.
             expanded_val = expand_variables(val)
             return expanded_val
        return str(val)
    # Match {variable_name}
    return re.sub(r'\{(\w+)\}', replace_var, text)

def expand_list_dict_refs(text):
    """Expands list/dict references in a string."""
    def replace_ref(match):
        ref_name = match.group(1)
        return str(lists_dicts.get(ref_name, match.group(0)))
    # Match (list_name)
    return re.sub(r'\((\w+)\)', replace_ref, text)

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

def play_beep():
    """Plays a simple beep sound."""
    try:
        if platform.system() == "Windows":
            winsound.Beep(1000, 200)  # Frequency 1000Hz, Duration 200ms
        else:
            # On Unix-like systems, try using system bell or aplay if available
            sys.stdout.write('\a') # ASCII Bell character
            sys.stdout.flush()
            # Alternative: os.system("beep") # Requires 'beep' package on Linux
    except Exception as e:
        print(f"Could not play sound: {e}")

def parse_nlm_file(file_path):
    """Parse an .nlm file and return a list of (line_number, code) tuples."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if it's a valid NLM file
    if not content.startswith("/. NaneLineModFile"):
        raise ValueError("Not a valid NLM file: missing header")
    
    # Find all sections
    sections = []
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("/. ") and not line.startswith("/. NaneLineModFile") and not line.endswith("end"):
            # Found a section start
            section_start_idx = i
            section_name = line[3:]  # Remove "/. "
            # Find the end of this section
            j = i + 1
            while j < len(lines):
                if lines[j].strip() == f"/. {section_name}end":
                    break
                j += 1
            if j >= len(lines):
                raise ValueError(f"Unclosed section: {section_name}")
            
            # Extract the content between this section start and its end
            section_content = lines[section_start_idx+1:j]
            # Parse Insert.Line and Code
            insert_line = None
            code_lines = []
            k = 0
            while k < len(section_content):
                content_line = section_content[k].strip()
                if content_line.startswith("Insert.Line="):
                    insert_line = int(content_line.split("=", 1)[1])
                elif content_line == "Code=":
                    # Collect all lines until next section starts or end of section
                    k += 1
                    while k < len(section_content):
                        inner_line = section_content[k].strip()
                        if inner_line.startswith("Insert.Line=") or inner_line == f"/. {section_name}end":
                            break
                        code_lines.append(inner_line)
                        k += 1
                    continue  # Don't increment k again at the end of loop
                k += 1
            
            if insert_line is not None and code_lines:
                sections.append((insert_line, "\n".join(code_lines)))
            
            i = j + 1  # Move past this section
        elif line == "/. end":
            break
        else:
            i += 1
    
    return sections

def generate_modules_py_with_insertions(nlm_files):
    """Generate modules.py with code from multiple NLM files inserted."""
    # Read the original script
    with open(__file__, 'r', encoding='utf-8') as f:
        original_content = f.read()
    
    # For each NLM file, apply modifications to the content
    modified_content = original_content
    for nlm_file in nlm_files:
        nlm_sections = parse_nlm_file(nlm_file)
        # Sort sections by line number in descending order to avoid index shifting issues
        nlm_sections.sort(key=lambda x: x[0], reverse=True)
        
        # Split content into lines
        lines = modified_content.splitlines(keepends=True)
        
        for line_num, code in nlm_sections:
            # Adjust line number to 0-based index and clamp to valid range
            idx = max(0, min(line_num - 1, len(lines)))
            # Insert the code after the specified line
            code_lines = code.splitlines(keepends=True)
            # Add the new code lines after the specified line
            lines[idx:idx] = code_lines
        
        # Update modified content for next iteration
        modified_content = "".join(lines)
    
    # Generate the modules.py file in modulesPY directory
    modules_py_path = os.path.join(MODULES_PY_DIR, "modules.py")
    with open(modules_py_path, 'w', encoding='utf-8') as f:
        f.write(modified_content)
    
    return modules_py_path

def load_nlm_module(nlm_file_path):
    """Load an .nlm module by generating modules.py and packing it to executable."""
    try:
        # First check if it's a valid NLM file
        parse_nlm_file(nlm_file_path)  # This will raise an exception if invalid
        
        # Get list of currently loaded NLM files (for multi-module support)
        current_nlm_files = [f for f in os.listdir(MODULES_DIR) if f.endswith('.nlm')]
        nlm_paths = [os.path.join(MODULES_DIR, f) for f in current_nlm_files]
        
        # Add the new NLM file if not already present
        nlm_filename = os.path.basename(nlm_file_path)
        target_nlm_path = os.path.join(MODULES_DIR, nlm_filename)
        
        if not os.path.exists(target_nlm_path):
            shutil.copy2(nlm_file_path, target_nlm_path)
            print(f"Copied NLM file to: {target_nlm_path}")
        
        # Add to list of NLM files to process
        if target_nlm_path not in nlm_paths:
            nlm_paths.append(target_nlm_path)
        
        # Generate modules.py with all NLM modifications
        modules_py_path = generate_modules_py_with_insertions(nlm_paths)
        print(f"Generated modules.py with all NLM modifications: {modules_py_path}")
        
        # Pack modules.py to executable
        module_exe_name = os.path.splitext(nlm_filename)[0]
        pack_to_executable_from_source(modules_py_path, module_exe_name)
        
        # Inform user and exit current instance
        print("Module loaded successfully. The updated executable has been created.")
        print("Press any key to exit the current instance...")
        input()
        sys.exit(0)
        
    except Exception as e:
        print(f"Error loading NLM module: {e}")
        return False

def unload_nlm_module(nlm_file_path):
    """Unload an .nlm module by removing its files."""
    try:
        nlm_filename = os.path.basename(nlm_file_path)
        target_nlm_path = os.path.join(MODULES_DIR, nlm_filename)
        
        if os.path.exists(target_nlm_path):
            os.remove(target_nlm_path)
            print(f"Removed NLM file: {target_nlm_path}")
        else:
            print(f"NLM file not found: {target_nlm_path}")
        
        # Also remove corresponding generated files
        module_exe_name = os.path.splitext(nlm_filename)[0]
        exe_path = os.path.join(NANE_LINE_DIR, f"{module_exe_name}.exe")
        modules_py_path = os.path.join(MODULES_PY_DIR, "modules.py")
        
        if os.path.exists(exe_path):
            os.remove(exe_path)
            print(f"Removed generated executable: {exe_path}")
        
        # Regenerate modules.py without this module if other modules still exist
        remaining_nlm_files = [f for f in os.listdir(MODULES_DIR) if f.endswith('.nlm')]
        if remaining_nlm_files:
            remaining_nlm_paths = [os.path.join(MODULES_DIR, f) for f in remaining_nlm_files]
            generate_modules_py_with_insertions(remaining_nlm_paths)
            print("Regenerated modules.py without the uninstalled module")
        else:
            # If no modules left, remove the modules.py file
            if os.path.exists(modules_py_path):
                os.remove(modules_py_path)
                print(f"Removed modules.py as no modules remain: {modules_py_path}")
        
        return True
    except Exception as e:
        print(f"Error unloading NLM module: {e}")
        return False

def pack_to_executable_from_source(source_py_path, output_name):
    """Pack a Python source file to executable using PyInstaller."""
    if not os.path.isfile(source_py_path):
        print(f"Error: Source file not found: {source_py_path}")
        return

    print(f"Packing '{source_py_path}' into an executable named '{output_name}.exe'...")
    log_message("INFO", f"Starting to pack {source_py_path} into executable {output_name}")

    # Check if PyInstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print("Error: PyInstaller is not installed.")
        print("Please install it using: pip install pyinstaller")
        return

    # Determine PyInstaller command arguments
    pyinstaller_cmd = [
        "pyinstaller",
        "--onefile",      # Create a single executable file
        "--name", output_name, # Set the name of the executable
        "--distpath", NANE_LINE_DIR,    # Output the executable to the NANE_LINE directory
        "--workpath", os.path.join(NANE_LINE_DIR, "build_temp"), # Use a temporary build directory
        "--specpath", os.path.join(NANE_LINE_DIR, "build_temp"), # Use the same temp dir for spec file
        source_py_path
    ]

    # Run PyInstaller
    try:
        result = subprocess.run(pyinstaller_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"PyInstaller failed:\n{result.stderr}")
            log_message("ERROR", f"PyInstaller failed: {result.stderr}")
        else:
            print(f"Successfully packed '{source_py_path}' into '{output_name}.exe'")
            log_message("INFO", f"Successfully packed {source_py_path} into {output_name}.exe")
    except Exception as e:
        print(f"An error occurred during the packing process: {e}")
        log_message("ERROR", f"Error during packing: {e}")
    finally:
        # Clean up the temporary PyInstaller directories if they exist
        try:
            build_temp_path = os.path.join(NANE_LINE_DIR, "build_temp")
            if os.path.exists(build_temp_path):
                shutil.rmtree(build_temp_path)
        except OSError as e:
            print(f"Warning: Could not clean up temporary build directory: {e}")
            log_message("WARNING", f"Could not clean up temporary build directory: {e}")

def list_loaded_modules():
    """List all loaded modules."""
    print("Loaded NLM modules:")
    nlm_files = [f for f in os.listdir(MODULES_DIR) if f.endswith('.nlm')]
    if nlm_files:
        for nlm_file in nlm_files:
            print(f"  - {nlm_file}")
    else:
        print("  No modules loaded")

def load_module(module_name):
    """Load a module from the modules directory (适配打包后环境)"""
    # 强制使用真实文件系统的模块路径（打包后指向 exe 同目录的 modules）
    module_path = os.path.join(MODULES_DIR, f"{module_name}.py")
    
    if not os.path.exists(module_path):
        print(f"Module '{module_name}' not found in {MODULES_DIR}")
        print(f"请确保 {module_path} 文件存在！")
        return False
    
    try:
        # 打包后环境：强制从真实文件路径加载，而非虚拟目录
        spec = importlib.util.spec_from_file_location(
            module_name, 
            module_path,
            # 强制使用文件系统加载器
            loader=importlib.machinery.SourceFileLoader(module_name, module_path)
        )
        module = importlib.util.module_from_spec(spec)
        # 手动添加模块到 sys.modules，避免重复加载
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        
        # 存储加载的模块
        loaded_modules[module_name] = module
        
        print(f"Module '{module_name}' loaded successfully from: {module_path}")
        log_message("INFO", f"Loaded module {module_name} from {module_path}")
        return True
    except Exception as e:
        print(f"Error loading module '{module_name}': {e}")
        log_message("ERROR", f"Error loading module {module_name}: {e}")
        return False

def unload_module(module_name):
    """Unload a module."""
    if module_name in loaded_modules:
        del loaded_modules[module_name]
        # 同时从 sys.modules 中移除，避免缓存
        if module_name in sys.modules:
            del sys.modules[module_name]
        print(f"Module '{module_name}' unloaded")
        log_message("INFO", f"Unloaded module {module_name}")
        return True
    else:
        print(f"Module '{module_name}' is not currently loaded")
        return False

def install_module(module_file_path):
    """Install a module from a file."""
    if not os.path.exists(module_file_path):
        print(f"Module file '{module_file_path}' does not exist")
        return False
    
    module_name = os.path.basename(module_file_path)
    
    # If it's a zip file, extract it
    if module_file_path.endswith('.zip'):
        with zipfile.ZipFile(module_file_path, 'r') as zip_ref:
            zip_ref.extractall(MODULES_DIR)
        print(f"Module '{module_name}' extracted to {MODULES_DIR}")
        log_message("INFO", f"Installed module {module_name} from zip")
        return True
    else:
        # Copy the file to modules directory
        dest_path = os.path.join(MODULES_DIR, module_name)
        try:
            shutil.copy2(module_file_path, dest_path)
            print(f"Module '{module_name}' installed to {MODULES_DIR}")
            log_message("INFO", f"Installed module {module_name}")
            return True
        except Exception as e:
            print(f"Error installing module '{module_name}': {e}")
            log_message("ERROR", f"Error installing module {module_name}: {e}")
            return False

def list_modules():
    """List all available modules in the modules directory."""
    print("Available modules in", MODULES_DIR)
    print("-" * 40)
    
    # List all .py files in the modules directory
    if not os.path.exists(MODULES_DIR):
        print("Modules directory does not exist!")
        return
    
    for file in os.listdir(MODULES_DIR):
        if file.endswith('.py'):
            module_name = file[:-3]  # Remove .py extension
            status = "LOADED" if module_name in loaded_modules else "NOT LOADED"
            print(f"{module_name:<20} [{status}]")
    
    # Also list .nlm files
    nlm_files = [f for f in os.listdir(MODULES_DIR) if f.endswith('.nlm')]
    if nlm_files:
        print("\nNLM Modules:")
        for file in nlm_files:
            module_name = file[:-4]  # Remove .nlm extension
            print(f"{module_name:<20} [NLM]")

def execute_module_function(module_name, function_name, *args):
    """Execute a function from a loaded module."""
    if module_name not in loaded_modules:
        print(f"Module '{module_name}' is not loaded. Use 'load <module>' first.")
        return False
    
    module = loaded_modules[module_name]
    
    if hasattr(module, function_name):
        try:
            func = getattr(module, function_name)
            result = func(*args)
            print(f"Result: {result}")
            return True
        except Exception as e:
            print(f"Error executing function '{function_name}' from module '{module_name}': {e}")
            return False
    else:
        print(f"Function '{function_name}' not found in module '{module_name}'")
        return False

def display_help():
    """Displays the help message."""
    help_text = """
NANE_LINE - A Python Command-Line Code Editor

Commands:
  ls, list                    : Show files in current directory
  cd <path>                   : Change directory
  scp <path>                  : Set command path (alias for 'cd')
  run <file.nlc/.nc>          : Run a .nlc or .nc file
  open <file>                 : Open a file in editor (or notepad on Windows)
  rm <file>                   : Delete a file
  new <file>                  : Create a new empty file
  new -file --name=<file> --content=(<line1>,<line2>,...) : Create a new file with specified content (lines separated by commas).
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
  setup_env                   : Manually attempt to set up environment (create dir, copy, add to PATH)

  print <text> [-a, --audio]  : Print text. Use -a or --audio to play a beep sound with it.
  def name=<func_name> command=(<cmd1>, <cmd2>, ...) : Define a function with a list of commands.
  def -o --name=<func_name>   : Execute a defined function.
  <var_name>={<value}>        : Define a variable. Example: my_name={Alice}
  <command> -p/<var_name>     : Use a variable in a command. Example: echo -p/my_name
  (<list_name>/<item1>, <item2>, ...) : Define a list/dict. Example: (my_list/item1,item2)
  list n=<list_name>          : Print the contents of a list/dict.

  file -see --command=<file>  : View file content in (line1,line2,...) format.
  file -see --row=<file>      : View file content line by line.
  file -see --ups=<N> --command=<file> : View file content in base-N (hexadecimal N=16) format, (line1,line2,...).
  file -see --ups=<N> --row=<file> : View file content in base-N (hexadecimal N=16) format, line by line.

  Module Commands:
  modules                     : List all available modules
  load <module_name>          : Load a module from the modules directory
  unload <module_name>        : Unload a module
  install <module_file>       : Install a module from a file (.py or .zip)
  runmod <module> <function> [args...] : Execute a function from a loaded module

  NLM Module Commands:
  mod -load=ModName.nlm       : Load a .nlm module file - generates modules.py with inserted code and creates executable
  mod -unload=ModName.nlm    : Unload a .nlm module file - removes the module and regenerates modules.py
  loadedmods                  : List all currently loaded NLM modules

  Additional Commands:
  openfile <file>             : Open a file with the default system application
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
    print(f"|\\  | /\\|\\  |----")
    print(f"| \\ |---| \\ |----")
    print(f"|  \\|   |  \\|____  Editor")
    print(f"Current directory: {current_directory}")
    print(f"Uptime: {days}d {hours}h {minutes}m {seconds}s")
    print(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"NANE_LINE directory: {NANE_LINE_DIR}")
    print(f"Modules directory: {MODULES_DIR}")
    print(f"ModulesPY directory: {MODULES_PY_DIR}")
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

# PyInstaller 打包适配：强制使用 exe 同目录的真实路径
if getattr(sys, 'frozen', False):
    EXE_DIR = os.path.dirname(sys.executable)
    sys.path.append(EXE_DIR)  # 添加 exe 目录到 Python 路径
    # 确保 modules 目录存在
    MODULES_DIR = os.path.join(EXE_DIR, "modules")
    if not os.path.exists(MODULES_DIR):
        os.makedirs(MODULES_DIR, exist_ok=True)
    sys.path.append(MODULES_DIR)  # 添加模块目录到 Python 路径

# 执行过滤后的 .nlc 代码
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

def open_file_with_default_app(filepath):
    """Open a file with the default system application."""
    try:
        if platform.system() == "Windows":
            os.startfile(filepath)
        elif platform.system() == "Darwin":  # macOS
            subprocess.run(["open", filepath])
        else:  # Linux
            subprocess.run(["xdg-open", filepath])
        print(f"Opened '{filepath}' with default application.")
        log_message("INFO", f"Opened file {filepath} with default application")
    except FileNotFoundError:
        print(f"File not found: {filepath}")
        log_message("ERROR", f"File not found for opening: {filepath}")
    except Exception as e:
        print(f"Could not open file with default application: {e}")
        log_message("ERROR", f"Error opening {filepath} with default application: {e}")

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

            # --- NEW: Handle variable assignment (e.g., my_var={value}) ---
            if '=' in command and command.startswith('{') and command.endswith('}'):
                var_name = command.split('=', 1)[0]
                var_value = command.split('=', 1)[1][1:-1] # Extract value inside {}
                if var_name and var_value:
                    variables[var_name] = var_value
                    print(f"Variable '{var_name}' set to '{var_value}'")
                    continue # Skip further processing for this line

            # --- NEW: Handle list/dict assignment (e.g., (list_name/item1,item2)) ---
            if user_input.startswith('(') and ')' in user_input:
                match = re.match(r'\((\w+)/(.*)\)', user_input)
                if match:
                    ld_name = match.group(1)
                    ld_items_str = match.group(2)
                    ld_items = [item.strip() for item in ld_items_str.split(',')]
                    lists_dicts[ld_name] = ld_items
                    print(f"List/Dict '{ld_name}' set to {ld_items}")
                    continue # Skip further processing for this line

            # --- NEW: Handle function definition (def name=func_name command=(...)) ---
            if command == 'def' and args_str:
                if args_str.startswith('name='):
                    # Definition part
                    func_match = re.match(r'name=(\w+)\s+command=\((.*)\)', args_str)
                    if func_match:
                        func_name = func_match.group(1)
                        commands_str = func_match.group(2)
                        # Split commands by comma, handling potential spaces
                        func_commands = [cmd.strip().strip('"\'') for cmd in commands_str.split(',')]
                        functions[func_name] = func_commands
                        print(f"Function '{func_name}' defined with commands: {func_commands}")
                        continue
                elif args_str.startswith('-o') or '--name=' in args_str:
                    # Execution part: def -o --name=func_name
                    exec_match = re.match(r'-o\s+--name=(\w+)', args_str)
                    if exec_match:
                        func_name = exec_match.group(1)
                        if func_name in functions:
                            print(f"Executing function '{func_name}'...")
                            for cmd in functions[func_name]:
                                # Expand variables and list/dict refs within the command before execution
                                expanded_cmd = expand_variables(cmd)
                                expanded_cmd = expand_list_dict_refs(expanded_cmd)
                                print(f"  -> Running: {expanded_cmd}")
                                # This is a simplified execution, it doesn't handle complex command parsing
                                # within the function commands. For a full shell, a proper parser is needed.
                                # Here, we just split the expanded command string.
                                sub_parts = expanded_cmd.split(maxsplit=1)
                                sub_cmd = sub_parts[0]
                                sub_args = sub_parts[1] if len(sub_parts) > 1 else ""
                                self.execute_internal_command(sub_cmd, sub_args)
                        else:
                            print(f"Function '{func_name}' not found.")
                        continue

            # --- NEW: Handle list/dict access (list n=list_name) ---
            if command == 'list' and args_str.startswith('n='):
                list_name = args_str[2:] # Get name after 'n='
                if list_name in lists_dicts:
                    print(f"Contents of '{list_name}': {lists_dicts[list_name]}")
                else:
                    print(f"List/Dict '{list_name}' not found.")
                continue


            # Process the command
            if command in ['exit', 'quit']:
                self.running = False
            elif command in ['ls', 'list'] and not args_str.startswith('n='): # Exclude 'list n=...'
                self.cmd_ls()
            elif command in ['cd', 'scp']: # Add 'scp' here
                self.cmd_cd(args_str)
            elif command == 'run':
                self.cmd_run(args_str)
            elif command == 'open':
                self.cmd_open(args_str)
            elif command == 'rm':
                self.cmd_rm(args_str)
            elif command == 'new':
                # Handle new command with optional -file flag
                self.cmd_new_with_content(args_str)
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
            elif command == 'print':
                self.cmd_print(args_str)
            elif command == 'file' and args_str.startswith('-see'):
                # Handle file -see command
                self.cmd_file_see(args_str)
            elif command == 'openfile':
                # Handle openfile command
                self.cmd_openfile(args_str)
            
            # Module commands
            elif command == 'modules':
                list_modules()
            elif command == 'load':
                module_name = args_str.strip()
                if module_name:
                    load_module(module_name)
                else:
                    print("Usage: load <module_name>")
            elif command == 'unload':
                module_name = args_str.strip()
                if module_name:
                    unload_module(module_name)
                else:
                    print("Usage: unload <module_name>")
            elif command == 'install':
                module_path = args_str.strip()
                if module_path:
                    install_module(module_path)
                else:
                    print("Usage: install <module_file_path>")
            elif command == 'runmod':
                # Usage: runmod <module> <function> [args...]
                parts = args_str.split()
                if len(parts) < 2:
                    print("Usage: runmod <module> <function> [args...]")
                else:
                    module_name = parts[0]
                    function_name = parts[1]
                    args = parts[2:]  # Remaining parts are arguments
                    execute_module_function(module_name, function_name, *args)
            
            # NLM Module commands
            elif command == 'mod':
                if args_str.startswith('-load='):
                    nlm_file = args_str[7:]  # Remove "-load="
                    if not nlm_file.endswith('.nlm'):
                        print("Error: NLM file must have .nlm extension")
                    else:
                        full_path = os.path.join(current_directory, nlm_file)
                        if os.path.exists(full_path):
                            load_nlm_module(full_path)
                        else:
                            print(f"Error: NLM file not found: {full_path}")
                elif args_str.startswith('-unload='):
                    nlm_file = args_str[10:]  # Remove "-unload="
                    if not nlm_file.endswith('.nlm'):
                        print("Error: NLM file must have .nlm extension")
                    else:
                        full_path = os.path.join(current_directory, nlm_file)
                        if os.path.exists(full_path):
                            unload_nlm_module(full_path)
                        else:
                            print(f"Error: NLM file not found: {full_path}")
                else:
                    print("Usage: mod -load=ModName.nlm OR mod -unload=ModName.nlm")
            
            # List loaded modules
            elif command == 'loadedmods':
                list_loaded_modules()
            
            else:
                # Check if it's a defined function call (not handled by 'def -o')
                if command in functions:
                    print(f"Executing function '{command}'...")
                    for cmd in functions[command]:
                        expanded_cmd = expand_variables(cmd)
                        expanded_cmd = expand_list_dict_refs(expanded_cmd)
                        print(f"  -> Running: {expanded_cmd}")
                        sub_parts = expanded_cmd.split(maxsplit=1)
                        sub_cmd = sub_parts[0]
                        sub_args = sub_parts[1] if len(sub_parts) > 1 else ""
                        self.execute_internal_command(sub_cmd, sub_args)
                    continue
                # Otherwise, unknown command
                print(f"Unknown command: {command}. Type 'help' for a list of commands.")

        # Save on exit
        save_config()
        save_history()
        log_message("INFO", "NANE_LINE exited.")
        print("Goodbye!")

    def cmd_print(self, args_str):
        """Handles the print command with optional audio."""
        audio_flag = False
        text_to_print = args_str

        if '-a' in args_str or '--audio' in args_str:
            audio_flag = True
            # Remove the flag from the text to print
            text_to_print = re.sub(r'(-a|--audio)\s*', '', args_str).strip()

        # Expand variables and list/dict refs within the text to print
        text_to_print = expand_variables(text_to_print)
        text_to_print = expand_list_dict_refs(text_to_print)

        print(text_to_print)
        if audio_flag:
            play_beep()

    def execute_internal_command(self, cmd, args_str):
        """Helper to execute commands internally, e.g., from a function."""
        # This is a simplified version. A full implementation would need to
        # handle all possible commands and their arguments precisely.
        # For now, it handles a few basic ones.
        if cmd == 'print':
            self.cmd_print(args_str)
        elif cmd == 'calc':
            self.cmd_calc(args_str)
        elif cmd == 'whoami':
            self.cmd_whoami()
        elif cmd == 'ls':
            self.cmd_ls()
        elif cmd == 'cd':
            self.cmd_cd(args_str)
        elif cmd == 'scp':
            self.cmd_cd(args_str) # scp is alias for cd
        else:
            # For other commands, try to run them as system commands
            run_command(f"{cmd} {args_str}")

    def cmd_file_see(self, args_str):
        """Handles the file -see command for viewing file content."""
        # Parse arguments using regex
        ups_match = re.search(r'--ups=(\d+)', args_str)
        command_match = re.search(r'--command=(\S+)', args_str)
        row_match = re.search(r'--row=(\S+)', args_str)

        # Check for --ups validity (must be used with --command or --row)
        if ups_match and not (command_match or row_match):
            print("Error: --ups option must be used with --command or --row.")
            return

        base = int(ups_match.group(1)) if ups_match else 10 # Default base is 10, but hex viewing is more common
        filename = None
        view_type = None

        if command_match:
            filename = command_match.group(1)
            view_type = "command"
        elif row_match:
            filename = row_match.group(1)
            view_type = "row"
        else:
            print("Usage: file -see --command=<file> OR file -see --row=<file> OR file -see --ups=<N> --command=<file> OR file -see --ups=<N> --row=<file>")
            return

        full_path = os.path.join(current_directory, filename)
        if not os.path.isfile(full_path):
            print(f"File not found: {full_path}")
            return

        try:
            if ups_match:
                # --- Hex View ---
                if base != 16:
                    # For other bases, we still read bytes and convert to hex, as that's the standard for raw data
                    print(f"Note: --ups={base} is specified, but viewing raw bytes in hex format.")
                
                with open(full_path, 'rb') as f:
                    content_bytes = f.read()
                
                hex_string = content_bytes.hex()
                # Format hex string into pairs (bytes)
                hex_pairs = [hex_string[i:i+2] for i in range(0, len(hex_string), 2)]
                
                if view_type == "command":
                    # Join hex pairs with commas, wrap in parentheses
                    print(f"({','.join(hex_pairs)})")
                elif view_type == "row":
                    # Print each hex pair on a new line
                    for pair in hex_pairs:
                        print(pair)
            else:
                # --- Text View (Original Logic) ---
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if view_type == "command":
                    # Split content into lines, escape commas if needed, join with commas, wrap in parentheses
                    lines = content.splitlines()
                    # Escape commas in lines to prevent breaking the format
                    escaped_lines = [line.replace(',', ',,') for line in lines]
                    print(f"({','.join(escaped_lines)})")
                elif view_type == "row":
                    # Print each line separately
                    print(content)

        except UnicodeDecodeError:
            print(f"Could not read {filename} as text. It might be a binary file. Use --ups=16 to view in hex.")
            log_message("WARNING", f"Attempted to read binary file as text: {full_path}")
        except Exception as e:
            print(f"An error occurred while reading the file: {e}")
            log_message("ERROR", f"Error reading file {full_path}: {e}")

    def cmd_openfile(self, args_str):
        """Handles the openfile command to open a file with the default system application."""
        if not args_str:
            print("Usage: openfile <file>")
            return
        full_path = os.path.join(current_directory, args_str)
        if not os.path.exists(full_path):
            print(f"File not found: {full_path}")
            return
        if os.path.isdir(full_path):
            print(f"Path is a directory: {full_path}")
            return
        open_file_with_default_app(full_path)

    def cmd_new_with_content(self, args_str):
        """Handles the new command, including the new -file --name --content syntax."""
        # Check if it's the new syntax: new -file --name=<name> --content=(...)
        if args_str.startswith('-file'):
            # Use regex to extract name and content
            match = re.match(r'-file\s+--name=(\S+)\s+--content=\((.*)\)', args_str)
            if match:
                filename = match.group(1)
                content_str = match.group(2)
                # Split content by comma, handling potential spaces
                content_lines = [line.strip() for line in content_str.split(',')]
                content = "\n".join(content_lines)

                full_path = os.path.join(current_directory, filename)
                try:
                    if os.path.exists(full_path):
                        print(f"File already exists: {full_path}")
                        return
                    with open(full_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print(f"New file created with content: {full_path}")
                    log_message("INFO", f"Created new file with content {full_path}")
                except PermissionError:
                    print(f"Permission denied to create file: {full_path}")
                    log_message("ERROR", f"Permission denied for new {full_path}")
                except Exception as e:
                    print(f"An error occurred while creating the file: {e}")
                    log_message("ERROR", f"Error creating {full_path}: {e}")
                return # Exit after handling the new syntax

        # If it's not the new syntax, fall back to the old one (creating an empty file)
        if not args_str:
            print("Usage: new <file> (creates empty file) or new -file --name=<file> --content=(<line1>,<line2>)")
            return
        
        # Old behavior: create an empty file
        self.cmd_new_old(args_str)

    def cmd_new_old(self, filename): # Renamed from cmd_new to avoid conflict
        """Creates a new empty file (old behavior)."""
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
            print("Usage: cd <path> or scp <path>")
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
            log_message("ERROR", f"Permission denied for cd/scp to {path}")
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
        print("NANE_LINE v1.0.0 - Python Command-Line Editor (EXE适配版)")
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
            print("You can use ANSI codes like setprompt '\033[35mMyPrompt>\033[0m ' for color.")
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

