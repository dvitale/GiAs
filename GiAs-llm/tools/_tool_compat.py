"""
Compatibility shim per il decoratore ``@tool`` di LangChain.

Scopo:
  1. Fornire un decoratore ``tool`` valido sia quando ``langchain_core`` è
     installato (ritorna ``BaseTool``) sia in fallback puro Python.
  2. Eliminare i diagnostici Pyright ``reportAssignmentType`` causati dal
     mismatch fra l'Overload di ``langchain_core.tools.tool`` e lo stub
     locale. Tipizzando l'alias come ``Any`` l'overload viene appiattito
     e gli accessi a ``.func`` passano il type check.
  3. Esporre ``unwrap_tool(t)`` per chiamare in modo sicuro la funzione
     sottostante a un ``@tool`` decorato (usato dai tool-node orchestrator).

Uso tipico nei moduli ``tools/*.py``:

    from tools._tool_compat import tool, unwrap_tool

    @tool("my_tool")
    def my_tool(...):
        ...

    # Per chiamare il callable sottostante:
    raw = unwrap_tool(my_tool)
    result = raw(...)
"""

from typing import Any, Callable


def _fallback_tool(_name: Any = None) -> Any:
    """Stub puro-Python usato quando ``langchain_core`` non è installato."""
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        return func
    return decorator


# Declaration unica: ``tool: Any`` appiattisce l'Overload di
# ``langchain_core.tools.tool`` (che ha 4 forme e confonde Pyright) e
# assorbe anche il fallback stub nello stesso slot.
tool: Any
try:
    from langchain_core.tools import tool as _lc_tool  # type: ignore
    tool = _lc_tool
except ImportError:  # pragma: no cover
    tool = _fallback_tool


def unwrap_tool(t: Any) -> Callable[..., Any]:
    """
    Ritorna il callable sottostante a un ``@tool`` decorato.

    LangChain 0.1+ espone la funzione originale come ``BaseTool.func``.
    In fallback (no langchain) ``t`` è già la funzione stessa.
    """
    return getattr(t, "func", t)
