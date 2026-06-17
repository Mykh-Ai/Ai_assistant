from __future__ import annotations

import ast
from dataclasses import dataclass
from datetime import date
import json
import multiprocessing as mp
import sys
from queue import Empty
from typing import Any

import pandas as pd


class AnalyticsCodeValidationError(ValueError):
    pass


class AnalyticsExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class AnalyticsExecutionResult:
    result: dict[str, Any]
    warnings: tuple[str, ...] = ()


_FORBIDDEN_NAMES = {
    'eval',
    'exec',
    'compile',
    'open',
    'input',
    'globals',
    'locals',
    'vars',
    'dir',
    'getattr',
    'setattr',
    'delattr',
    '__import__',
    'os',
    'sys',
    'subprocess',
    'socket',
    'requests',
    'pathlib',
    'sqlite3',
    'shutil',
}
_ALLOWED_INITIAL_NAMES = {'invoices_df', 'pd', 'current_date'}
_ALLOWED_BUILTINS = {
    'len': len,
    'int': int,
    'float': float,
    'str': str,
    'bool': bool,
    'round': round,
    'min': min,
    'max': max,
    'sum': sum,
    'list': list,
    'dict': dict,
    'set': set,
    'tuple': tuple,
    'sorted': sorted,
    'range': range,
}
_MAX_RESULT_JSON_BYTES = 12000


def _assigned_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            names.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
    return names


class _AnalyticsAstValidator(ast.NodeVisitor):
    def __init__(self) -> None:
        self.assigned: set[str] = set()

    def validate(self, tree: ast.AST) -> None:
        self.assigned = _assigned_names(tree)
        self.visit(tree)

    def visit_Import(self, node: ast.Import) -> None:
        raise AnalyticsCodeValidationError('imports_not_allowed')

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        raise AnalyticsCodeValidationError('imports_not_allowed')

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        raise AnalyticsCodeValidationError('function_definitions_not_allowed')

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        raise AnalyticsCodeValidationError('function_definitions_not_allowed')

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        raise AnalyticsCodeValidationError('class_definitions_not_allowed')

    def visit_Global(self, node: ast.Global) -> None:
        raise AnalyticsCodeValidationError('global_not_allowed')

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        raise AnalyticsCodeValidationError('nonlocal_not_allowed')

    def visit_Lambda(self, node: ast.Lambda) -> None:
        raise AnalyticsCodeValidationError('lambda_not_allowed')

    def visit_While(self, node: ast.While) -> None:
        raise AnalyticsCodeValidationError('while_not_allowed')

    def visit_For(self, node: ast.For) -> None:
        raise AnalyticsCodeValidationError('for_not_allowed')

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        raise AnalyticsCodeValidationError('for_not_allowed')

    def visit_With(self, node: ast.With) -> None:
        raise AnalyticsCodeValidationError('with_not_allowed')

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        raise AnalyticsCodeValidationError('with_not_allowed')

    def visit_ListComp(self, node: ast.ListComp) -> None:
        raise AnalyticsCodeValidationError('comprehension_not_allowed')

    def visit_DictComp(self, node: ast.DictComp) -> None:
        raise AnalyticsCodeValidationError('comprehension_not_allowed')

    def visit_SetComp(self, node: ast.SetComp) -> None:
        raise AnalyticsCodeValidationError('comprehension_not_allowed')

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        raise AnalyticsCodeValidationError('comprehension_not_allowed')

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith('__') or node.attr.endswith('__'):
            raise AnalyticsCodeValidationError('dunder_attribute_not_allowed')
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id.startswith('__') or node.id in _FORBIDDEN_NAMES:
            raise AnalyticsCodeValidationError(f'forbidden_name:{node.id}')
        if isinstance(node.ctx, ast.Load):
            allowed_loads = _ALLOWED_INITIAL_NAMES | set(_ALLOWED_BUILTINS) | self.assigned | {'True', 'False', 'None'}
            if node.id not in allowed_loads:
                raise AnalyticsCodeValidationError(f'name_not_allowed:{node.id}')
        elif isinstance(node.ctx, (ast.Store, ast.Del)) and node.id.startswith('_'):
            raise AnalyticsCodeValidationError('private_name_assignment_not_allowed')

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id in _FORBIDDEN_NAMES:
            raise AnalyticsCodeValidationError(f'forbidden_call:{node.func.id}')
        if isinstance(node.func, ast.Attribute):
            if node.func.attr.startswith('__') or node.func.attr.endswith('__'):
                raise AnalyticsCodeValidationError('dunder_call_not_allowed')
            if node.func.attr in {
                'read_csv',
                'read_excel',
                'read_feather',
                'read_fwf',
                'read_hdf',
                'read_html',
                'read_json',
                'read_orc',
                'read_parquet',
                'read_pickle',
                'read_sas',
                'read_spss',
                'read_sql',
                'read_sql_query',
                'read_sql_table',
                'read_stata',
                'read_table',
                'to_clipboard',
                'to_csv',
                'to_excel',
                'to_feather',
                'to_gbq',
                'to_hdf',
                'to_html',
                'to_json',
                'to_latex',
                'to_markdown',
                'to_orc',
                'to_parquet',
                'to_pickle',
                'to_sql',
                'to_stata',
            }:
                raise AnalyticsCodeValidationError(f'io_call_not_allowed:{node.func.attr}')
        self.generic_visit(node)


def validate_analytics_code(code: str) -> ast.Module:
    try:
        tree = ast.parse(code, mode='exec')
    except SyntaxError as exc:
        raise AnalyticsCodeValidationError('syntax_error') from exc
    _AnalyticsAstValidator().validate(tree)
    if not any(isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'result' for target in node.targets) for node in tree.body):
        raise AnalyticsCodeValidationError('missing_result_assignment')
    return tree


def execute_invoice_analytics_code(
    *,
    code: str,
    invoices_df: pd.DataFrame,
    current_date: date,
    timeout_seconds: float = 10.0,
) -> AnalyticsExecutionResult:
    validate_analytics_code(code)
    context = _execution_context()
    output_queue = context.Queue(maxsize=1)
    process = context.Process(
        target=_analytics_worker,
        args=(
            code,
            invoices_df.copy(),
            current_date.isoformat(),
            output_queue,
        ),
    )
    process.start()
    process.join(timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join(1)
        if process.is_alive():
            process.kill()
            process.join(1)
        _close_process(process)
        raise AnalyticsExecutionError('execution_timeout')

    try:
        status, payload, warnings = output_queue.get(timeout=1)
    except Empty as exc:
        _close_process(process)
        raise AnalyticsExecutionError('execution_failed') from exc
    finally:
        output_queue.close()
        output_queue.join_thread()

    _close_process(process)
    if status == 'validation_error':
        raise AnalyticsCodeValidationError(str(payload))
    if status != 'ok':
        raise AnalyticsExecutionError(str(payload))
    return AnalyticsExecutionResult(result=payload, warnings=tuple(warnings))


def _analytics_worker(
    code: str,
    invoices_df: pd.DataFrame,
    current_date_iso: str,
    output_queue: mp.Queue,
) -> None:
    try:
        tree = validate_analytics_code(code)
        globals_dict = {
            '__builtins__': dict(_ALLOWED_BUILTINS),
            'pd': pd,
            'current_date': date.fromisoformat(current_date_iso),
            'invoices_df': invoices_df.copy(),
        }
        locals_dict: dict[str, Any] = {}
        exec(compile(tree, '<invoice_analytics>', 'exec'), globals_dict, locals_dict)
        if 'result' not in locals_dict:
            raise AnalyticsExecutionError('missing_result')
        prepared = _prepare_result(locals_dict['result'])
        output_queue.put(('ok', prepared.result, prepared.warnings))
    except AnalyticsCodeValidationError as exc:
        output_queue.put(('validation_error', str(exc), ()))
    except AnalyticsExecutionError as exc:
        output_queue.put(('execution_error', str(exc), ()))
    except Exception:
        output_queue.put(('execution_error', 'execution_failed', ()))


def _execution_context() -> mp.context.BaseContext:
    if sys.platform != 'win32':
        try:
            return mp.get_context('fork')
        except ValueError:
            pass
    return mp.get_context('spawn')


def _close_process(process: mp.Process) -> None:
    try:
        process.close()
    except ValueError:
        pass


def _prepare_result(raw_result: Any) -> AnalyticsExecutionResult:
    result = _json_safe(raw_result)
    if not isinstance(result, dict):
        raise AnalyticsExecutionError('result_must_be_dict')
    result.setdefault('summary', {})
    result.setdefault('tables', {})
    result.setdefault('warnings', [])
    result.setdefault('answer_hints', [])
    encoded = json.dumps(result, ensure_ascii=False, default=str)
    warnings: list[str] = []
    if len(encoded.encode('utf-8')) > _MAX_RESULT_JSON_BYTES:
        result = _limit_result_size(result)
        warnings.append('result_truncated')
    return AnalyticsExecutionResult(result=result, warnings=tuple(warnings))


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(_json_safe(key)): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, 'item'):
        try:
            return _json_safe(value.item())
        except Exception:
            pass
    if hasattr(value, 'to_dict'):
        return _json_safe(value.to_dict(orient='records') if hasattr(value, 'columns') else value.to_dict())
    return str(value)


def _limit_result_size(result: dict[str, Any]) -> dict[str, Any]:
    limited = dict(result)
    tables = limited.get('tables')
    if isinstance(tables, dict):
        limited_tables: dict[str, Any] = {}
        for key, value in tables.items():
            if isinstance(value, list):
                limited_tables[key] = value[:20]
            else:
                limited_tables[key] = value
        limited['tables'] = limited_tables
    warnings = list(limited.get('warnings') or [])
    warnings.append('Výsledok bol skrátený na bezpečný rozsah.')
    limited['warnings'] = warnings
    encoded = json.dumps(limited, ensure_ascii=False, default=str)
    if len(encoded.encode('utf-8')) > _MAX_RESULT_JSON_BYTES:
        limited['tables'] = {}
        limited['answer_hints'] = list(limited.get('answer_hints') or [])[:20]
    return limited
