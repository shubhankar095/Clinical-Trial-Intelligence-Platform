import os,time
from typing import Callable,TypeVar
T=TypeVar("T")

def required_environment(*names: str) -> dict[str,str]:
    missing=[name for name in names if not os.getenv(name)]
    if missing: raise RuntimeError("Missing environment variables: "+", ".join(missing))
    return {name:os.environ[name] for name in names}

def wait_until(probe: Callable[[], T|None], *, timeout: float=120.0, interval: float=2.0) -> T:
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        result=probe()
        if result is not None:return result
        time.sleep(interval)
    raise TimeoutError(f"Condition not met within {timeout} seconds")
