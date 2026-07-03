import sys
import io
import contextlib
import traceback
import math
import statistics
import json
import datetime
from typing import Dict, Any, List, Union
from khabrichacha.tools.base import BaseTool
from loguru import logger

# Try optional dependencies
try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import numpy as np
except ImportError:
    np = None

def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    """
    A restricted import hook that only allows whitelisted modules.
    """
    allowed_modules = {"math", "statistics", "json", "datetime", "pandas", "numpy"}
    base_module = name.split('.')[0]
    
    if base_module in allowed_modules:
        return __import__(name, globals, locals, fromlist, level)
    
    raise ImportError(f"Import of module '{name}' is strictly prohibited for security reasons.")

def _build_restricted_globals() -> Dict[str, Any]:
    """
    Constructs a completely isolated globals dictionary for exec().
    """
    # Exclude open, eval, exec, compile, globals, locals, memoryview, __import__ (raw)
    safe_builtins_list = [
        'abs', 'all', 'any', 'bin', 'bool', 'chr', 'divmod', 'enumerate', 'filter',
        'float', 'format', 'hash', 'hex', 'id', 'int', 'isinstance', 'issubclass',
        'iter', 'len', 'list', 'map', 'max', 'min', 'next', 'oct', 'ord', 'pow',
        'print', 'range', 'repr', 'reversed', 'round', 'set', 'slice', 'sorted',
        'str', 'sum', 'tuple', 'type', 'zip', 'Exception', 'ValueError', 'TypeError',
        'KeyError', 'IndexError', 'AttributeError', 'ZeroDivisionError', 'AssertionError',
        'ImportError', 'NameError', 'NotImplementedError', 'RuntimeError'
    ]
    
    restricted_builtins = {}
    for name in safe_builtins_list:
        if hasattr(__builtins__, name):
            restricted_builtins[name] = getattr(__builtins__, name)
        elif isinstance(__builtins__, dict) and name in __builtins__:
            restricted_builtins[name] = __builtins__[name]
            
    # Inject our safe import hook
    restricted_builtins['__import__'] = _safe_import
    
    restricted_globals = {
        "__builtins__": restricted_builtins,
        "math": math,
        "statistics": statistics,
        "json": json,
        "datetime": datetime,
    }
    
    if pd is not None:
        restricted_globals["pandas"] = pd
    if np is not None:
        restricted_globals["numpy"] = np
        
    return restricted_globals

class PythonExecutorTool(BaseTool):
    """
    Execute Python code safely for calculations and data analysis.
    """

    @property
    def name(self) -> str:
        return "python_executor"

    @property
    def description(self) -> str:
        return "Execute Python code safely for calculations and data analysis."

    @property
    def category(self) -> str:
        return "utility"

    @property
    def version(self) -> str:
        return "1.0"

    @property
    def inputs(self) -> List[str]:
        return ["code"]

    @property
    def outputs(self) -> List[str]:
        return ["stdout", "stderr", "success"]

    @property
    def supports_streaming(self) -> bool:
        return False

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Union[bool, str]]:
        """
        Executes Python code safely and captures output.
        """
        logger.info("PythonExecutorTool execution started.")
        
        if "code" not in arguments or not arguments["code"]:
            error_msg = "Missing or empty 'code' argument."
            logger.error(error_msg)
            raise ValueError(error_msg)

        code = str(arguments["code"])
        logger.info("Executing Python code inside isolated sandbox.")

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        restricted_globals = _build_restricted_globals()
        restricted_locals = {}
        
        success = False
        traceback_str = ""

        try:
            with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
                # We compile the code first to ensure it's valid syntax
                compiled_code = compile(code, "<string>", "exec")
                exec(compiled_code, restricted_globals, restricted_locals)
            success = True
        except Exception:
            success = False
            traceback_str = traceback.format_exc()
            logger.error("Python code execution failed with exception.")
            
        stdout_str = stdout_capture.getvalue()
        stderr_str = stderr_capture.getvalue()
        
        # Merge captured stderr with the traceback string
        if not success:
            if stderr_str:
                stderr_str += "\n" + traceback_str
            else:
                stderr_str = traceback_str

        logger.info(f"Python execution finished. Success: {success}")
        
        return {
            "success": success,
            "stdout": stdout_str,
            "stderr": stderr_str
        }
