import json
import logging
import random
import re
import string
import subprocess
from json import JSONDecodeError
from typing import Dict, List, Union, Any, Tuple, Sequence
from urllib.error import HTTPError

import requests

from benji.helpers.settings import benji_log_level

logger = logging.getLogger()


def setup_logging() -> None:
    # Don't raise exceptions occurring during logging
    logging.raiseExceptions = False
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(benji_log_level)


def _one_line_stderr(stderr: str):
    stderr = re.sub(r'\n(?!$)', ' | ', stderr)
    stderr = re.sub(r'\s+', ' ', stderr)
    return stderr


def subprocess_run(args: List[str],
                   input: str = None,
                   timeout: int = None,
                   decode_json: bool = False) -> Union[Dict, List, str]:
    logger.debug('Running process: {}'.format(' '.join(args)))
    try:

        result = subprocess.run(args=args,
                                input=input,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                encoding='utf-8',
                                errors='ignore',
                                timeout=timeout)
    except subprocess.TimeoutExpired as exception:
        stderr = _one_line_stderr(exception.stderr)
        raise RuntimeError(f'{args[0]} invocation failed due to timeout with output: ' + stderr) from None
    except Exception as exception:
        raise RuntimeError(f'{args[0]} invocation failed with a {type(exception).__name__} exception: {str(exception)}') from None

    if result.stderr != '':
        for line in result.stderr.splitlines():
            logger.info(line)

    if result.returncode == 0:
        logger.debug('Process finished successfully.')
        if decode_json:
            try:
                stdout_json = json.loads(result.stdout)
            except JSONDecodeError:
                raise RuntimeError(f'{args[0]} invocation was successful but did not return valid JSON. Output on stderr was: {_one_line_stderr(result.stderr)}.')

            if stdout_json is None or not isinstance(stdout_json, (dict, list)):
                raise RuntimeError(f'{args[0]} invocation was successful but did return null or empty JSON dictonary. Output on stderr was: {_one_line_stderr(result.stderr)}.')

            return stdout_json
        else:
            return result.stdout
    else:
        raise RuntimeError(f'{args[0]} invocation failed with return code {result.returncode} and output: {_one_line_stderr(result.stderr)}')


def api_request(api_endpoint: str,
                path: str,
                method: str = 'GET',
                body: Any = None,
                params: Dict[str, Any] = None,
                timeout: Tuple[int, int] = (2, 30)) -> Dict[str, Any]:
    response = requests.request(method,
                                f'{api_endpoint}{path}',
                                headers={'Content-Type': 'application/json; charset=utf-8'},
                                params=params,
                                json=body,
                                timeout=timeout)
    response.raise_for_status()

    if response.status_code not in (200, 201):
        raise HTTPError(f'API call failed with status code {response.status_code}.', response=response)

    return response.json()


def keys_exist(obj: Any, keys: Sequence[str]) -> bool:
    split_keys = [attr.split('.') for attr in keys]

    for split_key in split_keys:
        position = obj
        for component in split_key:
            try:
                position = position.get(component, None)
            except AttributeError:
                return False
            if position is None:
                return False

    return True
