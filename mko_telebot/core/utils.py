from os import PathLike
from pathlib import Path
import logging
from typing import Any, Dict, Union, List, Tuple, Optional
import yaml

logger = logging.getLogger(__name__)


def list_files_in_directory(path: Union[str, PathLike],
                            extensions: Tuple[str, ...] = ('yaml', 'json'),
                            include_subfolders: bool = False) -> List[Path]:
    """
    Lists files in a directory with specific extensions.

    Args:
        path (Union[str, PathLike]): The directory path.
        extensions (Tuple[str, ...]): Allowed file extensions (default: ('csv', 'txt')).
        include_subfolders (bool): Whether to include subfolders (default: False).

    Returns:
        List[Path]: A list of file paths matching the given extensions.
    """
    try:
        files = []
        subfolder_pattern = '**/' if include_subfolders else ''
        for ext in extensions:
            files.extend(Path(path).glob(f'{subfolder_pattern}*.{ext.strip(".")}'))
        return files
    except Exception as err:
        logger.error(f"Error reading directory {path}: {err}")
        return []

def ensure_path_exists(path: Path) -> None:
    """
    Ensures that a given path exists, creating directories if necessary.

    Args:
        path (Path): Path to a file or directory.

    Raises:
        ValueError: If the path cannot be created.
    """
    try:
        if path.exists():
            return  # Path already exists, no action needed
        if path.suffix:  # If it's a file, create its parent directory
            path.parent.mkdir(parents=True, exist_ok=True)
        else:  # If it's a directory, create it
            path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise ValueError(f"Failed to create path {path}: {e}")


def resolve_path(path: Union[str, Path], base_dir: Union[Path, None] = None) -> Path:
    """
    Resolves an absolute path, creating it if necessary.

    If a relative path is given, it is resolved against `base_dir`.

    Args:
        path (Union[str, Path]): The path to resolve (can be absolute or relative).
        base_dir (Union[Path, None], optional): The base directory for resolving relative paths.
            Defaults to the parent directory of this script.

    Returns:
        Path: The resolved absolute path.

    Raises:
        ValueError: If the path cannot be found or created.
    """
    path = Path(path).expanduser()  # Expands `~` (home directory)

    # If the path is absolute and exists, return it immediately
    if path.is_absolute():
        if path.exists():
            return path
        ensure_path_exists(path)  # If not found, attempt to create it
        return path

    # Ensure base_dir is a valid Path
    base_dir = base_dir or Path(__file__).resolve().parent.parent
    resolved_path = (base_dir / path).resolve()

    if not resolved_path.exists():
        ensure_path_exists(resolved_path)  # Create the path if it does not exist

    return resolved_path

def load_config(path: Path) -> Dict[str, Any]:
    """
    Loads configuration from a YAML file.

    Args:
        path (Path): Path to the YAML configuration file.

    Returns:
        Dict[str, Any]: Parsed configuration dictionary, or an empty dict if the file does not exist or is invalid.
    """
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def merge_dicts(dict1: Dict[Any, Any], dict2: Dict[Any, Any]) -> Dict[Any, Any]:
    """
    Recursively merges two dictionaries.

    If both dictionaries have the same key and the value is also a dictionary, it merges them recursively.
    Otherwise, `dict2`'s value overwrites `dict1`'s value.

    Args:
        dict1 (Dict[Any, Any]): The first dictionary.
        dict2 (Dict[Any, Any]): The second dictionary.

    Returns:
        Dict[Any, Any]: The merged dictionary.
    """
    if not isinstance(dict1, dict) or not isinstance(dict2, dict):
        return dict2
    for k in dict2:
        if k in dict1:
            dict1[k] = merge_dicts(dict1[k], dict2[k])
        else:
            dict1[k] = dict2[k]
    return dict1